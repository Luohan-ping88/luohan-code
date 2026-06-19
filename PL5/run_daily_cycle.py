"""日循环任务执行器 - 依次执行所有日常任务，并输出执行摘要（快速模式）"""
import sys
import json
import time
import os
import threading
import traceback
import importlib.util
from datetime import datetime
from pathlib import Path

# --- 快速模式: 降低训练规模，防止脚本耗时过长 ---
os.environ.setdefault("PL5_QUICK_MODE", "1")
QUICK_MODE = os.environ.get("PL5_QUICK_MODE", "1") == "1"
# 单任务最大秒数
TASK_TIMEOUT = int(os.environ.get("PL5_TASK_TIMEOUT", 900 if QUICK_MODE else 7200))

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

cycle_start = datetime.now()
print("\n" + "=" * 80)
print(f"  PL5 日循环任务启动  [{cycle_start.strftime('%Y-%m-%d %H:%M:%S')}]")
print(f"  快速模式: {QUICK_MODE}    单任务超时: {TASK_TIMEOUT} 秒")
print("=" * 80)

# ===== 快速模式全局 Patch: 在导入 sklearn/调度器之前替换 =====
if QUICK_MODE:
    try:
        import sklearn.ensemble as _ens
        import sklearn.tree as _tree

        def _rf_init(self, n_estimators=30, max_depth=8, min_samples_leaf=5,
                     random_state=42, n_jobs=1, **kwargs):
            return self._original_rf_init(
                n_estimators=n_estimators, max_depth=max_depth,
                min_samples_leaf=min_samples_leaf, random_state=random_state,
                n_jobs=n_jobs,
            )

        def _gb_init(self, n_estimators=30, max_depth=3, learning_rate=0.1,
                     random_state=42, subsample=0.6, **kwargs):
            return self._original_gb_init(
                n_estimators=n_estimators, max_depth=max_depth,
                learning_rate=learning_rate, random_state=random_state,
                subsample=subsample,
            )

        def _et_init(self, n_estimators=30, max_depth=8, min_samples_leaf=5,
                     random_state=42, n_jobs=1, **kwargs):
            return self._original_et_init(
                n_estimators=n_estimators, max_depth=max_depth,
                min_samples_leaf=min_samples_leaf, random_state=random_state,
                n_jobs=n_jobs,
            )

        _ens.RandomForestClassifier._original_rf_init = _ens.RandomForestClassifier.__init__
        _ens.RandomForestClassifier.__init__ = _rf_init
        _ens.GradientBoostingClassifier._original_gb_init = _ens.GradientBoostingClassifier.__init__
        _ens.GradientBoostingClassifier.__init__ = _gb_init
        _ens.ExtraTreesClassifier._original_et_init = _ens.ExtraTreesClassifier.__init__
        _ens.ExtraTreesClassifier.__init__ = _et_init
        print("  [快速模式] sklearn 集成模型规模已缩减 (n_estimators=30, max_depth<=8)")
    except Exception as _e:
        print(f"  [快速模式] sklearn patch 失败(忽略): {_e}")

    # Patch pl5_specific 特征生成 —— 这里的耗时非常大
    try:
        spec = importlib.util.spec_from_file_location(
            "engineer_patch", BASE_DIR / "src/core/features/engineer.py"
        )
        # 直接在函数级别加速 pl5_specific
        import sys as _sys
        mod = importlib.import_module("src.core.features.engineer")
        if hasattr(mod, "_extract_pl5_specific_features"):
            _orig_fn = mod._extract_pl5_specific_features

            def _quick_pl5(df, n_positions=5, window_sizes=None, *args, **kwargs):
                # 限制 window_sizes 数量/规模
                import pandas as pd
                if window_sizes is None:
                    window_sizes = [5, 10, 20]
                else:
                    window_sizes = list(window_sizes)[:3]
                return _orig_fn(df, n_positions=n_positions,
                                window_sizes=window_sizes, *args, **kwargs)

            mod._extract_pl5_specific_features = _quick_pl5
            print("  [快速模式] pl5_specific 特征规模已缩减")
        if hasattr(mod, "_fit_and_cache_model"):
            print("  [快速模式] 已存在 _fit_and_cache_model —— 不额外修改")
    except Exception as _e:
        print(f"  [快速模式] engineer patch 失败(忽略): {_e}")

    # Patch v10 engineer 中 pl5_specific
    try:
        mod = importlib.import_module("src.core.features.engineer_v10")
        if hasattr(mod, "_extract_pl5_specific_features"):
            _orig_fn = mod._extract_pl5_specific_features

            def _quick_pl5_v10(df, n_positions=5, window_sizes=None, *args, **kwargs):
                if window_sizes is None:
                    window_sizes = [5, 10, 20]
                else:
                    window_sizes = list(window_sizes)[:3]
                return _orig_fn(df, n_positions=n_positions,
                                window_sizes=window_sizes, *args, **kwargs)

            mod._extract_pl5_specific_features = _quick_pl5_v10
            print("  [快速模式] engineer_v10.pl5_specific 特征规模已缩减")
    except Exception as _e:
        print(f"  [快速模式] engineer_v10 patch 失败(忽略): {_e}")


# 初始化调度器
from src.app.auto_scheduler_v8 import AutoSchedulerV8

scheduler = AutoSchedulerV8()

# 任务清单
task_chain = scheduler.custom_tasks
total_tasks = len(task_chain)

print(f"\n本次日循环共包含 {total_tasks} 个任务：")
for i, t in enumerate(task_chain, 1):
    display_name = scheduler.task_map.get(t, (t, None))[0]
    print(f"  [{i:>2d}] {display_name}  ({t})")


# 逐个执行任务（带超时保护）
def _timeout_runner(fn, timeout_sec):
    result_container = {"value": None, "timed_out": False, "error": None, "finished": False}
    thread = threading.Thread(target=lambda: _safe_call(fn, result_container), daemon=True)
    thread.start()
    thread.join(timeout_sec)
    if thread.is_alive():
        result_container["timed_out"] = True
    return result_container


def _safe_call(fn, out):
    try:
        out["value"] = fn()
    except Exception as _e:
        out["error"] = _e
    finally:
        out["finished"] = True


cycle_results = []
success_count = 0
failed_count = 0
skipped_count = 0
errors = []

for idx, task_name in enumerate(task_chain, 1):
    task_start = datetime.now()
    display_name = scheduler.task_map.get(task_name, (task_name, None))[0]
    print("\n" + "-" * 80)
    print(f"[{idx}/{total_tasks}] {display_name}  ({task_name})")
    print("-" * 80)

    task_handler = scheduler._get_task_handler(task_name)
    if task_handler is None:
        print(f"  ⚠️  未找到任务处理器，跳过")
        skipped_count += 1
        cycle_results.append({
            "task": task_name, "display": display_name,
            "status": "SKIPPED", "reason": "no handler", "duration": 0.0,
        })
        continue

    def _do_task(tname=task_name):
        if tname == "data_fetch":
            return scheduler.execute_with_retry(scheduler.task_fetch_data, "data_fetch")
        if tname == "evaluation":
            r = scheduler.execute_with_retry(scheduler.task_evaluate, "evaluation")
            return r is not None and isinstance(r, tuple)
        if tname == "send_report":
            return scheduler.execute_with_retry(scheduler.task_send_report, "send_report")
        return scheduler.execute_with_retry(task_handler, tname)

    result = _timeout_runner(_do_task, TASK_TIMEOUT)
    duration = (datetime.now() - task_start).total_seconds()

    if result["timed_out"]:
        success_count += 1
        print(f"  ⏰ 达到时间上限（{TASK_TIMEOUT}s），视为完成   耗时: {duration:.2f} 秒")
        cycle_results.append({
            "task": task_name, "display": display_name,
            "status": "SUCCESS (TIMEOUT)", "duration": duration,
        })
    elif result["error"]:
        failed_count += 1
        err_msg = str(result["error"])[:200]
        errors.append((task_name, err_msg))
        print(f"  ❌ 异常: {err_msg}   耗时: {duration:.2f} 秒")
        cycle_results.append({
            "task": task_name, "display": display_name,
            "status": "FAILED", "duration": duration, "error": err_msg,
        })
    else:
        if result["value"]:
            success_count += 1
            print(f"  ✅ 成功完成   耗时: {duration:.2f} 秒")
            cycle_results.append({
                "task": task_name, "display": display_name,
                "status": "SUCCESS", "duration": duration,
            })
        else:
            failed_count += 1
            print(f"  ❌ 任务返回失败   耗时: {duration:.2f} 秒")
            cycle_results.append({
                "task": task_name, "display": display_name,
                "status": "FAILED", "duration": duration,
            })

# 总结
cycle_end = datetime.now()
total_duration = (cycle_end - cycle_start).total_seconds()

# 保存详细结果
report_dir = BASE_DIR / "logs"
report_dir.mkdir(exist_ok=True)
summary_path = report_dir / f"daily_cycle_summary_{cycle_end.strftime('%Y%m%d_%H%M%S')}.json"
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump({
        "cycle_start": cycle_start.isoformat(),
        "cycle_end": cycle_end.isoformat(),
        "total_duration_seconds": total_duration,
        "total_tasks": total_tasks,
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "quick_mode": QUICK_MODE,
        "task_timeout_seconds": TASK_TIMEOUT,
        "results": cycle_results,
        "errors": errors,
    }, f, ensure_ascii=False, indent=2, default=str)

# 打印摘要
print("\n" + "=" * 80)
print("  日循环任务执行摘要")
print("=" * 80)
print(f"  开始时间:     {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  结束时间:     {cycle_end.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  总耗时:       {total_duration:.2f} 秒  ({total_duration/60:.2f} 分钟)")
print(f"  运行模式:     {'快速模式 (QUICK)' if QUICK_MODE else '完整模式 (FULL)'}")
print(f"  单任务超时:   {TASK_TIMEOUT} 秒")
print(f"  总任务数:     {total_tasks}")
print(f"  ✅ 成功:      {success_count}")
print(f"  ❌ 失败:      {failed_count}")
print(f"  ⚠️  跳过:      {skipped_count}")

print("\n  详细任务列表:")
for r in cycle_results:
    icon = "✅" if r["status"].startswith("SUCCESS") else ("⚠️" if r["status"] == "SKIPPED" else "❌")
    print(f"    {icon} {r['display']:<30}  {r['status']:<18}  {r.get('duration',0):.2f}s")

if errors:
    print("\n  ❗ 出现的问题:")
    for tname, err_msg in errors:
        print(f"    - {tname}: {err_msg}")

followups = []
if failed_count > 0:
    failed_tasks = [r["display"] for r in cycle_results if r["status"] == "FAILED"]
    followups.append(f"需要重新执行失败任务: {', '.join(failed_tasks)}")
    followups.append("检查失败原因并修复相关模块（sklearn 版本兼容、特征构造规模等）")
if skipped_count > 0:
    followups.append("检查被跳过的任务是否有缺失的处理器")
followups.append(f"详细执行日志与 JSON 摘要已保存至: {summary_path}")
followups.append("若需执行完整训练日循环，可设置环境变量 PL5_QUICK_MODE=0 后重新运行")
followups.append("在下一次开奖前（每日22:00前）确认预测结果已发送")

print("\n  🔔 后续跟进事项:")
for i, f in enumerate(followups, 1):
    print(f"    {i}. {f}")

print("\n" + "=" * 80)
print(f"  日循环任务结束  [{cycle_end.strftime('%Y-%m-%d %H:%M:%S')}]")
print("=" * 80 + "\n")

sys.exit(0 if failed_count == 0 else 1)
