#!/usr/bin/env python3
"""执行剩余日循环任务 8-14"""
import json
import time
import logging
import warnings
from pathlib import Path
from datetime import datetime
import sys

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

start_time = datetime.now()
print("\n" + "=" * 80)
print("继续执行日循环任务 8-14")
print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# 初始化 AutoSchedulerV8
print("\n初始化 AutoSchedulerV8...")
from src.app.auto_scheduler_v8 import AutoSchedulerV8
scheduler = AutoSchedulerV8()
print(f"  ✓ 调度器初始化完成")

# 执行任务 8-14
results = {}

# 任务8: 三次佐证
print("\n【任务8/14】三次预测验证（三次佐证）")
t8_start = time.time()
try:
    success = scheduler.task_third_prediction_verification()
    elapsed = time.time() - t8_start
    results['third_prediction_verification'] = {"status": "完成" if success else "失败", "elapsed": f"{elapsed:.1f}s"}
    print(f"  {'✓' if success else '✗'} 三次佐证: {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - t8_start
    results['third_prediction_verification'] = {"status": "失败", "elapsed": f"{elapsed:.1f}s", "error": str(e)[:100]}
    print(f"  ✗ 失败: {e}")

# 任务9: 深度策略优化
print("\n【任务9/14】深度策略优化（四次佐证）")
t9_start = time.time()
try:
    scheduler.task_deep_strategy_optimization()
    elapsed = time.time() - t9_start
    results['deep_strategy_optimization'] = {"status": "完成", "elapsed": f"{elapsed:.1f}s"}
    print(f"  ✓ 深度策略优化: {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - t9_start
    results['deep_strategy_optimization'] = {"status": "失败", "elapsed": f"{elapsed:.1f}s", "error": str(e)[:100]}
    print(f"  ✗ 失败: {e}")

# 任务10: 预测预览
print("\n【任务10/14】预测结果预生成（五次佐证）")
t10_start = time.time()
try:
    scheduler.task_prediction_preview()
    elapsed = time.time() - t10_start
    results['prediction_preview'] = {"status": "完成", "elapsed": f"{elapsed:.1f}s"}
    print(f"  ✓ 预测预览: {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - t10_start
    results['prediction_preview'] = {"status": "失败", "elapsed": f"{elapsed:.1f}s", "error": str(e)[:100]}
    print(f"  ✗ 失败: {e}")

# 任务11: 最终预测
print("\n【任务11/14】生成最终预测结果")
t11_start = time.time()
try:
    scheduler.task_final_prediction()
    elapsed = time.time() - t11_start
    results['final_prediction'] = {"status": "完成", "elapsed": f"{elapsed:.1f}s"}
    print(f"  ✓ 最终预测: {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - t11_start
    results['final_prediction'] = {"status": "失败", "elapsed": f"{elapsed:.1f}s", "error": str(e)[:100]}
    print(f"  ✗ 失败: {e}")

# 任务12: 最终预测验证
print("\n【任务12/14】最终预测验证")
t12_start = time.time()
try:
    scheduler.task_final_prediction_verification()
    elapsed = time.time() - t12_start
    results['final_prediction_verification'] = {"status": "完成", "elapsed": f"{elapsed:.1f}s"}
    print(f"  ✓ 最终预测验证: {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - t12_start
    results['final_prediction_verification'] = {"status": "失败", "elapsed": f"{elapsed:.1f}s", "error": str(e)[:100]}
    print(f"  ✗ 失败: {e}")

# 任务13: 售前预测
print("\n【任务13/14】售前最终预测")
t13_start = time.time()
try:
    scheduler.task_pre_sale_prediction()
    elapsed = time.time() - t13_start
    results['pre_sale_prediction'] = {"status": "完成", "elapsed": f"{elapsed:.1f}s"}
    print(f"  ✓ 售前预测: {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - t13_start
    results['pre_sale_prediction'] = {"status": "失败", "elapsed": f"{elapsed:.1f}s", "error": str(e)[:100]}
    print(f"  ✗ 失败: {e}")

# 任务14: 发送报告
print("\n【任务14/14】发送训练报告和最终预测")
t14_start = time.time()
try:
    scheduler.task_send_report()
    elapsed = time.time() - t14_start
    results['send_report'] = {"status": "完成", "elapsed": f"{elapsed:.1f}s"}
    print(f"  ✓ 发送报告: {elapsed:.1f}s")
except Exception as e:
    elapsed = time.time() - t14_start
    results['send_report'] = {"status": "失败", "elapsed": f"{elapsed:.1f}s", "error": str(e)[:100]}
    print(f"  ✗ 失败: {e}")

# 生成执行摘要
end_time = datetime.now()
total_elapsed = sum(
    (datetime.strptime(r['elapsed'].rstrip('s'), '%S') - datetime(1900, 1, 1)).total_seconds()
    if 'elapsed' in r and r['elapsed'].endswith('s') and r['elapsed'].rstrip('s').replace('.', '').isdigit()
    else 0
    for r in results.values()
)
successful = [k for k, v in results.items() if v.get('status') == '完成']
failed = [k for k, v in results.items() if v.get('status') == '失败']

print("\n" + "=" * 80)
print("任务 8-14 执行摘要")
print("=" * 80)
print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"本次耗时: {(end_time - start_time).total_seconds():.1f}s")
print(f"完成任务: {len(successful)}/{len(results)}")

print("\n详细结果:")
for k, v in results.items():
    status = "✓" if v.get('status') == '完成' else "✗"
    err = f" - {v.get('error', '')[:50]}" if 'error' in v else ""
    print(f"  [{status}] {k}: {v.get('elapsed', '?')}{err}")

# 保存摘要
summary = {
    "title": "日循环任务 8-14 执行摘要",
    "start_time": start_time.isoformat(),
    "end_time": end_time.isoformat(),
    "elapsed_seconds": (end_time - start_time).total_seconds(),
    "tasks": results,
    "successful_count": len(successful),
    "failed_count": len(failed)
}
summary_path = Path('results/summary')
summary_path.mkdir(parents=True, exist_ok=True)
with open(summary_path / f"daily_cycle_remaining_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 80)
print("✓ 任务 8-14 执行完成!")
print("=" * 80)

sys.exit(0 if len(failed) == 0 else 1)
