#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断send_report任务失败的原因
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("诊断 send_report 任务")
print("=" * 80)

# 1. 检查 analyze_and_send 是否存在
print("\n[1] 检查模块导入...")
try:
    from src.app.analyze_and_send import analyze_and_send
    print("✓ analyze_and_send 模块导入成功")
except Exception as e:
    print(f"✗ analyze_and_send 导入失败: {e}")
    traceback.print_exc()

# 2. 检查 EmailSender 是否存在
print("\n[2] 检查 EmailSender...")
try:
    from src.app.email_sender import EmailSender
    print("✓ EmailSender 导入成功")
except Exception as e:
    print(f"✗ EmailSender 导入失败: {e}")
    traceback.print_exc()

# 3. 检查训练信息文件
print("\n[3] 检查训练信息文件...")
training_info_path = Path("logs/training_info.json")
if training_info_path.exists():
    print(f"✓ training_info.json 存在")
    try:
        import json
        with open(training_info_path, 'r', encoding='utf-8') as f:
            info = json.load(f)
        print(f"  内容: {json.dumps(info, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"  读取失败: {e}")
else:
    print(f"✗ training_info.json 不存在")

# 4. 检查数据收集器
print("\n[4] 检查数据收集器...")
try:
    from src.core.data.collector import PL5DataCollector
    collector = PL5DataCollector()
    df = collector.load_processed_data()
    if df is not None and len(df) > 0:
        latest_period = df['period'].iloc[-1]
        next_period = str(int(latest_period) + 1)
        print(f"✓ 数据加载成功")
        print(f"  最新期号: {latest_period}")
        print(f"  预测期号: {next_period}")
    else:
        print("✗ 无数据")
except Exception as e:
    print(f"✗ 数据收集器失败: {e}")
    traceback.print_exc()

# 5. 尝试直接运行 analyze_and_send
print("\n[5] 尝试运行 analyze_and_send()...")
try:
    result = analyze_and_send()
    print(f"✓ analyze_and_send 执行成功")
    print(f"  结果: {result}")
except Exception as e:
    print(f"✗ analyze_and_send 执行失败: {e}")
    traceback.print_exc()

print("\n" + "=" * 80)
print("诊断完成")
print("=" * 80)
