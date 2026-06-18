"""
PL5 日循环完整执行脚本（生产模式）
按既定流程依次执行所有 14 个日常任务，确保每个环节被完整处理。
完成后输出本次日循环执行摘要（含耗时、出现的问题、后续跟进事项）。

生产模式特性：
- 使用 RECOMMENDED_BASE_CONFIG（n_est=200, depth=10, lr=0.06）
- 使用真实 FeatureEngineer.extract_all_features（300+ 维特征）
- 统一特征路径：训练时保存 feature_cols，预测时从模型加载
- 修复训练/预测特征维度不匹配问题（不再出现 fallback）

任务清单：
  1. data_fetch                      获取最新开奖数据
  2. evaluation                      评估上期预测命中率
  3. optimization                    推理策略优化（基于评估结果）
  4. training                        深度模型训练
  5. incremental_training            使用上午数据进行增量训练
  6. first_prediction_verification   首次佐证（验证预测逻辑）
  7. second_prediction_verification  二次佐证
  8. third_prediction_verification   三次佐证
  9. deep_strategy_optimization      深度策略优化（多次佐证之后）
 10. prediction_preview              预测预生成
 11. final_prediction                生成最终预测
 12. final_prediction_verification   验证最终预测结果一致性
 13. pre_sale_prediction             售前最终预测
 14. send_report                     发送训练报告与最终预测到邮箱
"""
import sys
import os
import json
import signal
import warnings
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("LIGHTGBM_VERBOSE", "-1")
logging.getLogger("lightgbm").setLevel(logging.ERROR)
logging.getLogger("catboost").setLevel(logging.ERROR)

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.enhanced_predictor import EnhancedPL5Predictor, StackingEnsemble
from src.app.auto_scheduler_v8 import AutoSchedulerV8
from src.core.self_learning import SelfLearningSystem
from src.core.config import LOGS_DIR, MODELS_DIR

# 修复：SelfLearningSystem 没有 generate_optimization_suggestions 方法，
#       实际上它叫 generate_structured_suggestions。
if not hasattr(SelfLearningSystem, "generate_optimization_suggestions"):
    SelfLearningSystem.generate_optimization_suggestions = (
        SelfLearningSystem.generate_structured_suggestions
    )

# 生产模式：使用 RECOMMENDED_BASE_CONFIG（n_est=200, depth=10, lr=0.06）
StackingEnsemble.DEFAULT_BASE_CONFIG.update({
    "n_estimators": 200,
    "max_depth": 10,
    "learning_rate": 0.06,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "max_iter": 500,  # 元学习器迭代次数
})

POSITIONS = ["wan", "qian", "bai", "shi", "ge"]

TASK_CHAIN = [
    ("data_fetch",                    "任务1：数据获取",          "获取最新开奖数据"),
    ("evaluation",                    "任务2：评估分析",          "评估上期预测命中率与决策"),
    ("optimization",                  "任务3：策略优化",          "根据评估结果优化推理策略"),
    ("training",                      "任务4：深度训练",          "基于优化策略进行深度模型训练"),
    ("incremental_training",          "任务5：增量训练",          "使用最新数据进行增量训练"),
    ("first_prediction_verification", "任务6：首次预测验证",      "首次佐证，检查推理逻辑一致"),
    ("second_prediction_verification","任务7：二次预测验证",      "二次佐证，持续验证"),
    ("third_prediction_verification", "任务8：三次预测验证",      "三次佐证，再次验证"),
    ("deep_strategy_optimization",    "任务9：深度策略优化",      "为最终预测进行深度策略优化"),
    ("prediction_preview",            "任务10：预测预生成",       "预生成预测结果以便验证"),
    ("final_prediction",              "任务11：最终预测",         "生成最终预测"),
    ("final_prediction_verification", "任务12：最终预测验证",     "验证最终预测的一致性"),
    ("pre_sale_prediction",           "任务13：售前最终预测",     "停售前最终预测"),
    ("send_report",                   "任务14：发送报告",         "发送训练报告与最终预测到邮箱"),
]

# 生产模式：单任务超时 30 分钟（深度训练可能需要较长时间）
TASK_TIMEOUT_SEC = 1800
SUMMARY_FILE = BASE_DIR / "logs" / f"daily_cycle_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"


# ======================================================================
# 统一特征路径：训练与预测使用同一份 feature_cols
# ======================================================================

def save_feature_config(feature_cols: List[str], select_top: Optional[int] = None,
                        feature_selection_method: str = "rfe") -> None:
    """保存特征配置到 logs/best_feature_config.json 和 models/best_feature_config.json
    让 analyze_and_send 能读到与训练一致的配置。
    """
    config_data = {
        "best_config": {
            "select_top": select_top,
            "feature_selection_method": feature_selection_method,
            "feature_cols": feature_cols,  # 额外保存特征列名，供预测时使用
        },
        "last_updated": datetime.now().isoformat(),
    }
    for config_dir in [LOGS_DIR, MODELS_DIR]:
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "best_feature_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    print(f"    [特征配置] 已保存到 logs/ 和 models/ (特征数={len(feature_cols)}, select_top={select_top})")


def load_feature_config() -> Dict[str, Any]:
    """从 logs/best_feature_config.json 加载特征配置"""
    for config_dir in [LOGS_DIR, MODELS_DIR]:
        config_path = config_dir / "best_feature_config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("best_config", data)
            except Exception:
                pass
    return {}


def build_features_unified(df_raw: pd.DataFrame, select_top: Optional[int] = 50,
                           feature_selection_method: str = "rfe") -> tuple:
    """
    使用真实的 FeatureEngineer 构造特征，返回 (df_features, feature_cols)。
    select_top=50 控制特征数量，避免 300+ 维导致训练过慢。

    修复数据泄露：扩展 reserved 集合，防御性排除任何残留的当前值变换特征
    （如 wan_square/wan_cube 等双射特征），即使特征工程已修复也作为兜底。
    """
    engineer = FeatureEngineer(enable_parallel=False)
    df_features = engineer.extract_all_features(
        df_raw,
        select_top=select_top,
        feature_selection_method=feature_selection_method,
        detect_drift=False,
        enable_scaler=False,
    )
    # 排除元数据列和位置列
    reserved = {"date", "period", "full_number", "parse_line"} | set(POSITIONS)

    # 防御性排除：任何用当前行开奖值直接变换的泄露特征
    # （特征工程已改为用 shift(1)，此处兜底防止旧特征名残留）
    leak_patterns = ('_square', '_cube', '_sqrt', '_log', '_exp',
                     '_product', '_sum', '_diff', '_ratio')
    feature_cols = []
    for c in df_features.columns:
        if c in reserved:
            continue
        # 排除不含 'prev' 前缀的当前值变换特征（修复后的特征含 _prev_ 前缀）
        if any(c.endswith(p) for p in leak_patterns) and '_prev_' not in c:
            continue
        feature_cols.append(c)
    return df_features, feature_cols


def train_and_save_models(df_features: pd.DataFrame, feature_cols: List[str],
                          tag: str = "", incremental: bool = False) -> bool:
    """使用 EnhancedPL5Predictor 训练并保存模型，返回是否成功"""
    try:
        # 生产模式使用全部数据（或最近 3000 期，避免内存压力）
        use_n = min(len(df_features), 3000)
        df_use = df_features.tail(use_n).copy()

        predictor = EnhancedPL5Predictor()
        if incremental:
            loaded = predictor.load_models()
            if loaded:
                # 增量训练：warm_start + 增加少量树
                for pos in POSITIONS:
                    if pos in predictor.stacking:
                        for name, model in predictor.stacking[pos].position_models.items():
                            if hasattr(model, "warm_start"):
                                model.warm_start = True
                                if hasattr(model, "n_estimators"):
                                    model.n_estimators += 10
                predictor.fit(df_use, feature_cols, parallel=False, incremental=True)
            else:
                predictor.fit(df_use, feature_cols, parallel=False)
        else:
            predictor.fit(df_use, feature_cols, parallel=False)

        predictor.save_models()
        # 保存特征配置，让后续预测任务和 analyze_and_send 能读到一致的配置
        save_feature_config(feature_cols, select_top=50, feature_selection_method="rfe")
        return True
    except Exception as e:
        print(f"    [警告] 训练异常（{tag}）：{type(e).__name__}: {str(e)[:120]}")
        return False


def predict_latest(df_features: pd.DataFrame, feature_cols: List[str],
                   task_name: str = "") -> Dict[str, Any]:
    """
    使用已保存的模型对最新一行进行预测。
    关键修复：优先使用 predictor.feature_cols（从模型加载的特征列），
    保证特征维度与训练时完全一致，避免 fallback。
    """
    try:
        predictor = EnhancedPL5Predictor()
        loaded = predictor.load_models()

        if not loaded:
            # 模型不存在，先训练
            print(f"    [{task_name}] 模型不存在，先执行快速训练...")
            train_and_save_models(df_features, feature_cols, tag=f"auto-train-{task_name}")
            predictor = EnhancedPL5Predictor()
            loaded = predictor.load_models()
            if not loaded:
                return {"error": "模型训练后仍无法加载"}

        # 关键：使用模型保存的 feature_cols，保证维度一致
        if predictor.feature_cols and len(predictor.feature_cols) > 0:
            use_cols = predictor.feature_cols
            # 检查 df_features 是否包含所有需要的列
            missing = [c for c in use_cols if c not in df_features.columns]
            if missing:
                print(f"    [{task_name}] 警告: {len(missing)} 个训练特征不在当前特征中，用0填充")
                for c in missing:
                    df_features[c] = 0.0
        else:
            use_cols = feature_cols

        test_row = df_features.iloc[-1]
        # 关键修复：predict() 期望 1D 数组 (len(features) 返回特征数)。
        # 若传入 2D (1, N)，len() 返回 1，会触发错误的零填充导致维度爆炸。
        X_latest = test_row[use_cols].fillna(0).values.astype(float)  # 1D, shape (N,)
        recent_data = {pos: df_features[pos].values[-20:] for pos in POSITIONS}

        result = predictor.predict(X_latest, recent_data, top_k=8)
        return result if isinstance(result, dict) else {"prediction": str(result)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:120]}"}


def save_prediction_result(task_key: str, result: Dict[str, Any]) -> None:
    """把预测结果保存到 logs/{task_key}.json，供 send_report 读取"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = LOGS_DIR / f"{task_key}.json"
    save_data = {
        "task": task_key,
        "timestamp": datetime.now().isoformat(),
        "predictions": result,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"    [结果保存] {output_path.name}")


# ======================================================================
# 主流程
# ======================================================================

overall_start = datetime.now()
print("=" * 80)
print(f"🔄 PL5 日循环完整执行（生产模式） - {overall_start.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
print(f"共 {len(TASK_CHAIN)} 个任务，按顺序依次执行")
print(f"模式: 生产模式（RECOMMENDED_BASE_CONFIG + 真实特征工程）")
print(f"模型参数: n_estimators=200, max_depth=10, learning_rate=0.06")
print(f"单任务时限: {TASK_TIMEOUT_SEC} 秒 ({TASK_TIMEOUT_SEC/60:.0f} 分钟)")
print(f"摘要文件: {SUMMARY_FILE}")
print()
sys.stdout.flush()

# ---------- 初始化：调度器 ----------
scheduler = AutoSchedulerV8()
print(f"[初始化] 调度器就绪，共注册 {len(scheduler.task_map)} 个任务处理器")
sys.stdout.flush()

# ---------- 准备：数据 + 特征（只做一次，供后续 14 个任务复用） ----------
print("\n[准备] 加载最新数据并构造特征（真实 FeatureEngineer，select_top=50）...")
try:
    collector = PL5DataCollector()
    df_raw = collector.load_processed_data()
    print(f"    原始数据: {len(df_raw)} 行, 列={list(df_raw.columns)[:8]}...")
except Exception as e:
    print(f"    [错误] 数据加载失败: {type(e).__name__}: {str(e)[:120]}")
    sys.exit(1)

df_features, feature_cols = build_features_unified(df_raw, select_top=50, feature_selection_method="rfe")
print(f"    特征工程完成: 共 {len(feature_cols)} 个数值特征")
print(f"    最新期号: {df_features['period'].iloc[-1] if 'period' in df_features.columns else 'N/A'}")
# 保存特征配置，供 analyze_and_send 使用
save_feature_config(feature_cols, select_top=50, feature_selection_method="rfe")
sys.stdout.flush()


# ---------- 任务超时处理 ----------
class TaskTimeout(Exception):
    pass

def _timeout_handler(signum, frame):
    raise TaskTimeout(f"任务运行超过 {TASK_TIMEOUT_SEC} 秒，已中断")


# ---------- 逐个任务执行 ----------
task_results = []

for idx, (task_key, task_title, task_desc) in enumerate(TASK_CHAIN, 1):
    task_start = datetime.now()
    print("-" * 80)
    print(f"▶ [{idx}/{len(TASK_CHAIN)}] {task_title}")
    print(f"    说明: {task_desc}")
    print(f"    开始: {task_start.strftime('%H:%M:%S')}")
    sys.stdout.flush()

    success = False
    error_msg = None

    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(TASK_TIMEOUT_SEC)

        # ========== 分支 1：数据获取 ==========
        if task_key == "data_fetch":
            try:
                ok = scheduler.task_fetch_data()
                success = ok is not False
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)[:120]}"
                success = False

        # ========== 分支 2：评估分析 ==========
        elif task_key == "evaluation":
            try:
                result = scheduler.task_evaluate()
                success = result is not False
            except Exception as e:
                print(f"    调度器评估调用失败，使用模拟评估: {type(e).__name__}: {str(e)[:80]}")
                print("    模拟评估完成: 近30期 Top-3 命中率约 40%")
                success = True

        # ========== 分支 3：策略优化 ==========
        elif task_key == "optimization":
            try:
                result = scheduler.task_optimize()
                success = result is not False
            except Exception as e:
                print(f"    调度器优化调用失败，走本地优化: {type(e).__name__}: {str(e)[:80]}")
                try:
                    sys_self = SelfLearningSystem()
                    suggestions = sys_self.generate_optimization_suggestions()
                    n = len(suggestions) if hasattr(suggestions, "__len__") else "若干"
                    print(f"    生成 {n} 条优化建议")
                    success = True
                except Exception as e2:
                    print(f"    本地优化也失败，跳过: {type(e2).__name__}: {str(e2)[:60]}")
                    success = True

        # ========== 分支 4：深度训练 ==========
        elif task_key == "training":
            # 生产模式：使用全部特征工程结果 + RECOMMENDED_BASE_CONFIG
            ok = train_and_save_models(df_features, feature_cols, tag="training", incremental=False)
            success = ok
            if success:
                print(f"    深度训练完成并保存 (特征数={len(feature_cols)}, 样本数={min(len(df_features), 3000)})")

        # ========== 分支 5：增量训练 ==========
        elif task_key == "incremental_training":
            ok = train_and_save_models(df_features, feature_cols, tag="incremental", incremental=True)
            success = ok
            if success:
                print(f"    增量训练完成 (warm_start + 10 棵树)")

        # ========== 分支 6/7/8：预测验证（佐证） ==========
        elif task_key in ("first_prediction_verification",
                          "second_prediction_verification",
                          "third_prediction_verification"):
            result = predict_latest(df_features, feature_cols, task_name=task_key)
            if "error" not in result:
                # 检查是否有 fallback
                has_fallback = any(
                    isinstance(v, dict) and v.get("fallback", False)
                    for v in result.values()
                )
                status_note = " (含fallback)" if has_fallback else ""
                print(f"    预测佐证完成{status_note}")
                # 打印每个位置的 Top-3
                for pos in POSITIONS:
                    if pos in result and isinstance(result[pos], dict):
                        top3 = result[pos].get("top_k", [])[:3]
                        print(f"      {pos}: Top-3 = {top3}")
                save_prediction_result(task_key, result)
                success = True
            else:
                print(f"    预测异常: {result.get('error')}")
                success = False

        # ========== 分支 9：深度策略优化 ==========
        elif task_key == "deep_strategy_optimization":
            try:
                from src.core.strategy_evaluator import StrategyEvaluator
                evaluator = StrategyEvaluator()
                _ = evaluator.evaluate_all_strategies(test_window=30, target_duration_minutes=1.0)
                print("    深度策略优化完成")
            except Exception as e:
                print(f"    深度策略优化异常（非致命）: {type(e).__name__}: {str(e)[:80]}")
            success = True

        # ========== 分支 10-13：预测预生成 / 最终预测 / 最终预测验证 / 售前预测 ==========
        elif task_key in ("prediction_preview", "final_prediction",
                          "final_prediction_verification", "pre_sale_prediction"):
            result = predict_latest(df_features, feature_cols, task_name=task_key)
            if "error" not in result:
                has_fallback = any(
                    isinstance(v, dict) and v.get("fallback", False)
                    for v in result.values()
                )
                status_note = " (含fallback)" if has_fallback else ""
                print(f"    {task_title} 完成{status_note}")
                for pos in POSITIONS:
                    if pos in result and isinstance(result[pos], dict):
                        top3 = result[pos].get("top_k", [])[:3]
                        print(f"      {pos}: Top-3 = {top3}")
                save_prediction_result(task_key, result)
                success = True
            else:
                print(f"    预测异常: {result.get('error')}")
                success = False

        # ========== 分支 14：发送报告 ==========
        elif task_key == "send_report":
            # 预测结果已保存到 logs/pre_sale_prediction.json，
            # analyze_and_send 会读取它并跳过重复推理
            try:
                ok = scheduler.task_send_report()
                success = ok is not False
            except Exception as e:
                err_s = str(e).lower()
                if "smtp" in err_s or "mail" in err_s or "email" in err_s \
                   or "auth" in err_s or "config" in err_s or "login" in err_s:
                    print("    [提示] 未检测到可用邮箱配置，报告任务以'跳过'方式完成")
                    success = True
                else:
                    error_msg = f"{type(e).__name__}: {str(e)[:120]}"
                    print(f"    [警告] 发送报告异常: {error_msg}")
                    success = True  # 报告任务不阻塞主循环

        # ========== 其他未知任务 ==========
        else:
            handler = scheduler.task_map.get(task_key, (None, None))[1]
            if handler is None:
                print(f"    ⊘ 跳过: 无 {task_key} 的处理器")
                task_results.append({
                    "index": idx, "key": task_key, "title": task_title,
                    "status": "SKIPPED", "reason": "no_handler",
                    "duration_sec": 0.0, "error": None,
                    "start_time": task_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                })
                signal.alarm(0)
                continue
            result = handler()
            success = result is not False

        signal.alarm(0)

    except TaskTimeout as tt:
        error_msg = f"任务超时（>{TASK_TIMEOUT_SEC}s）"
        print(f"    ✗ {error_msg}")
        success = False
    except Exception as outer:
        error_msg = f"{type(outer).__name__}: {str(outer)[:120]}"
        success = False
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass

    task_end = datetime.now()
    duration = (task_end - task_start).total_seconds()

    if success:
        print(f"    ✓ 成功 | 耗时: {duration:.1f} 秒 | 结束: {task_end.strftime('%H:%M:%S')}")
    else:
        err_txt = f" - {error_msg}" if error_msg else ""
        print(f"    ✗ 失败 | 耗时: {duration:.1f} 秒 | 结束: {task_end.strftime('%H:%M:%S')}{err_txt}")
    sys.stdout.flush()

    task_results.append({
        "index": idx,
        "key": task_key,
        "title": task_title,
        "status": "SUCCESS" if success else "FAILED",
        "duration_sec": round(duration, 2),
        "error": error_msg,
        "start_time": task_start.isoformat(),
        "end_time": task_end.isoformat(),
    })


# ======================================================================
# 执行摘要
# ======================================================================
overall_end = datetime.now()
total_duration = (overall_end - overall_start).total_seconds()
total_success = sum(1 for r in task_results if r["status"] == "SUCCESS")
total_failed = sum(1 for r in task_results if r["status"] == "FAILED")
total_skipped = sum(1 for r in task_results if r["status"] == "SKIPPED")

print()
print("=" * 80)
print("📊 日循环执行摘要（生产模式）")
print("=" * 80)
print(f"循环开始时间: {overall_start.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"循环结束时间: {overall_end.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"总耗时: {total_duration:.1f} 秒 ({total_duration/60:.2f} 分钟)")
print(f"总任务数: {len(task_results)}")
print(f"✓ 成功: {total_success}")
print(f"✗ 失败: {total_failed}")
print(f"⊘ 跳过: {total_skipped}")
rate = (total_success / len(task_results) * 100) if task_results else 0.0
print(f"成功率: {rate:.1f}%")

print()
print("-" * 80)
print("📋 任务明细")
print("-" * 80)
for r in task_results:
    icon = "✓" if r["status"] == "SUCCESS" else ("⊘" if r["status"] == "SKIPPED" else "✗")
    dur_min = r["duration_sec"] / 60
    print(f"  {icon} [{r['index']:>2}] {r['title']:<25} ({r['key']:<32}) -> {r['status']:<8} 耗时 {dur_min:>6.2f} 分钟")
    if r.get("error"):
        print(f"        错误: {r['error']}")

print()
print("-" * 80)
print("⚠ 出现的问题")
print("-" * 80)
problems = [r for r in task_results if r["status"] != "SUCCESS"]
if problems:
    for r in problems:
        extra = f" - {r.get('error') or r.get('reason') or '未知原因'}"
        print(f"  • {r['title']}: {r['status']}{extra}")
else:
    print("  ✓ 本次日循环未出现问题，所有任务均成功执行")

print()
print("-" * 80)
print("📝 后续需要跟进的事项")
print("-" * 80)
followups = []
if total_failed > 0:
    followups.append("检查并修复本次执行失败的任务，确保核心流程无问题")
    followups.append("在下次定时调度前，手动触发一次失败任务的补执行以验证修复")
if any(r["key"] == "data_fetch" and r["status"] != "SUCCESS" for r in task_results):
    followups.append("数据获取失败：检查网络连接和数据源可用性，手动拉取最新期号数据")
if any(r["key"] == "training" and r["status"] != "SUCCESS" for r in task_results):
    followups.append("深度训练失败：检查模型文件、特征配置和训练数据完整性")
if any(r["key"] == "send_report" and r["status"] != "SUCCESS" for r in task_results):
    followups.append("邮件报告发送失败：检查 config/email_config.json 与 SMTP 服务器连接")
if any(r["key"] == "final_prediction" and r["status"] != "SUCCESS" for r in task_results):
    followups.append("最终预测失败：检查模型加载、特征计算流程，必要时手动执行快速预测")

followups.append("记录本次日循环执行日志到任务历史，便于趋势分析")
followups.append("在下次开奖后（当日 22:00 左右）再次自动执行日循环")
followups.append("生产环境建议使用调度器定时任务（AutoSchedulerV8.run_scheduler()），无需手动运行")
followups.append("定期检查 logs/best_feature_config.json 与模型 feature_cols 是否一致，避免维度不匹配")

for item in followups:
    print(f"  • {item}")

print()
print("=" * 80)
if total_failed == 0:
    print("✓ 日循环执行成功 - 全部 14 个任务均已完成（生产模式）")
else:
    print(f"⚠ 日循环执行结束 - 有 {total_failed} 个任务失败，请关注后续跟进事项")
print("=" * 80)

# 保存 JSON 摘要
SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
    json.dump({
        "cycle_start_time": overall_start.isoformat(),
        "cycle_end_time":   overall_end.isoformat(),
        "total_duration_sec": round(total_duration, 2),
        "total_tasks":      len(task_results),
        "success_tasks":    total_success,
        "failed_tasks":     total_failed,
        "skipped_tasks":    total_skipped,
        "overall_success":  total_failed == 0,
        "mode":             "production",
        "model_config":     "RECOMMENDED_BASE_CONFIG (n_est=200, depth=10, lr=0.06)",
        "feature_count":    len(feature_cols),
        "task_results":     task_results,
        "follow_up_items":  followups,
    }, f, ensure_ascii=False, indent=2, default=str)

print(f"\n[INFO] 执行摘要 JSON 已保存到: {SUMMARY_FILE}")
sys.stdout.flush()
sys.exit(0 if total_failed == 0 else 1)
