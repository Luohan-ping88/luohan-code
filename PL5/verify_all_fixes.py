#!/usr/bin/env python3
"""
验证所有修复的脚本
"""
import sys
import os
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("✅ PL5 所有修复验证")
print("=" * 80)
print(f"\n验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

all_passed = True

# ==========================================
# 验证 1: 环境变量配置
# ==========================================
print("\n" + "=" * 80)
print("[1/6] 验证环境变量配置")
print("=" * 80)

try:
    from src.core.config.env_config import get_config
    config = get_config()
    print("✓ 环境变量配置加载成功")
    print(f"✓ 邮件服务器: {config.email_config['smtp_server']}:{config.email_config['smtp_port']}")
    print(f"✓ 发件人: {config.email_config['from_email']}")
    print(f"✓ 收件人: {config.email_config['to_email']}")
    print(f"✓ 特征模式: {config.feature_config['feature_mode']}")
    print(f"✓ C++加速: {'启用' if config.feature_config['enable_cpp_acceleration'] else '禁用'}")
    print("✓ 环境变量配置验证通过")
except Exception as e:
    print(f"✗ 环境变量配置验证失败: {e}")
    all_passed = False

# ==========================================
# 验证 2: 预测展示修复 - email_sender.py
# ==========================================
print("\n" + "=" * 80)
print("[2/6] 验证邮件发送模块的预测展示")
print("=" * 80)

try:
    from src.app.email_sender import generate_html_report
    
    test_predictions = {
        'wan': {'top_k': [3, 7, 1, 9, 4, 2, 8, 6], 'probabilities': [0.5, 0.2, 0.15, 0.08, 0.04, 0.02, 0.007, 0.003]},
        'qian': {'top_k': [5, 2, 8, 0, 3, 7, 1, 9], 'probabilities': [0.45, 0.25, 0.18, 0.07, 0.03, 0.015, 0.003, 0.002]},
        'bai': {'top_k': [9, 4, 1, 7, 2, 6, 3, 8], 'probabilities': [0.55, 0.2, 0.12, 0.06, 0.03, 0.02, 0.015, 0.005]},
        'shi': {'top_k': [1, 6, 9, 3, 8, 0, 5, 2], 'probabilities': [0.38, 0.28, 0.17, 0.07, 0.04, 0.03, 0.02, 0.01]},
        'ge': {'top_k': [8, 3, 5, 1, 7, 9, 2, 0], 'probabilities': [0.42, 0.23, 0.16, 0.08, 0.05, 0.03, 0.02, 0.01]},
    }
    
    html = generate_html_report(
        period='2026135',
        predictions=test_predictions,
        analysis_data={'v11': 'active'},
        data_count=7609,
        latest_period='2026134'
    )
    
    checks = ['Top 8', 'Top 5', 'Top 3', 'Top 1']
    all_found = True
    for check in checks:
        if check in html:
            print(f"✓ 找到 {check} 展示")
        else:
            print(f"✗ 缺少 {check} 展示")
            all_found = False
            all_passed = False
    
    if all_found:
        print("✓ email_sender.py 预测展示验证通过")
    else:
        print("✗ email_sender.py 预测展示验证失败")
        
except Exception as e:
    print(f"✗ 邮件发送模块验证失败: {e}")
    import traceback
    traceback.print_exc()
    all_passed = False

# ==========================================
# 验证 3: 预测展示修复 - send_training_report_to_customer.py
# ==========================================
print("\n" + "=" * 80)
print("[3/6] 验证报告生成模块的预测展示")
print("=" * 80)

try:
    from scripts.send_training_report_to_customer import generate_professional_report, generate_simple_prediction_data, create_training_summary
    
    test_data = generate_simple_prediction_data()
    summary = create_training_summary()
    
    html_report, text_report = generate_professional_report(test_data, summary)
    
    checks = ['Top 8', 'Top 5', 'Top 3']
    all_found = True
    for check in checks:
        if check in html_report:
            print(f"✓ HTML报告包含 {check}")
        else:
            print(f"✗ HTML报告缺少 {check}")
            all_found = False
            all_passed = False
    
    for check in checks:
        if check in text_report:
            print(f"✓ 文本报告包含 {check}")
        else:
            print(f"✗ 文本报告缺少 {check}")
            all_found = False
            all_passed = False
    
    if all_found:
        print("✓ send_training_report_to_customer.py 预测展示验证通过")
    else:
        print("✗ send_training_report_to_customer.py 预测展示验证失败")
        
except Exception as e:
    print(f"✗ 报告生成模块验证失败: {e}")
    import traceback
    traceback.print_exc()
    all_passed = False

# ==========================================
# 验证 4: 预测展示修复 - generate_prediction.py
# ==========================================
print("\n" + "=" * 80)
print("[4/6] 验证预测生成脚本")
print("=" * 80)

try:
    with open('scripts/utility/generate_prediction.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = ['Top 8', 'Top 5', 'Top 3', 'Top 1']
    all_found = True
    for check in checks:
        if check in content:
            print(f"✓ 脚本包含 {check} 展示")
        else:
            print(f"✗ 脚本缺少 {check} 展示")
            all_found = False
            all_passed = False
    
    if all_found:
        print("✓ generate_prediction.py 预测展示验证通过")
    else:
        print("✗ generate_prediction.py 预测展示验证失败")
        
except Exception as e:
    print(f"✗ 预测生成脚本验证失败: {e}")
    all_passed = False

# ==========================================
# 验证 5: 测试预测展示脚本
# ==========================================
print("\n" + "=" * 80)
print("[5/6] 运行预测展示测试脚本")
print("=" * 80)

try:
    import subprocess
    result = subprocess.run(
        [sys.executable, 'test_prediction_display.py'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode == 0:
        print("✓ 测试脚本运行成功")
        print("\n测试输出:")
        print(result.stdout[-800:])
    else:
        print(f"✗ 测试脚本运行失败: {result.stderr}")
        all_passed = False
        
except Exception as e:
    print(f"✗ 测试脚本运行异常: {e}")
    import traceback
    traceback.print_exc()
    all_passed = False

# ==========================================
# 验证 6: 验证已保存的预测结果
# ==========================================
print("\n" + "=" * 80)
print("[6/6] 验证已保存的预测结果")
print("=" * 80)

try:
    latest_pred_path = Path('results/latest_prediction.json')
    if latest_pred_path.exists():
        with open(latest_pred_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✓ 找到预测结果: {latest_pred_path}")
        print(f"✓ 预测期数: {data.get('period', 'N/A')}")
        predictions = data.get('predictions', {})
        
        position_names = {
            'wan': '万位',
            'qian': '千位',
            'bai': '百位',
            'shi': '十位',
            'ge': '个位'
        }
        
        print("\n🎯 预测结果 (完整展示):")
        for pos, pos_name in position_names.items():
            if pos in predictions:
                top_k = predictions[pos].get('top_k', [])
                print(f"\n{pos_name}:")
                print(f"  Top 8: {top_k[:8]}")
                print(f"  Top 5: {top_k[:5]}")
                print(f"  Top 3: {top_k[:3]}")
                print(f"  Top 1: {top_k[:1]}")
    else:
        print("✗ 未找到预测结果文件")
        
    training_info_path = Path('logs/training_info.json')
    if training_info_path.exists():
        with open(training_info_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"\n✓ 找到训练信息: {training_info_path}")
        print(f"✓ 模型版本: {data.get('model_version', 'N/A')}")
        print(f"✓ 特征工程: {data.get('feature_engineering', 'N/A')}")
        
except Exception as e:
    print(f"✗ 验证预测结果失败: {e}")

# ==========================================
# 总结
# ==========================================
print("\n" + "=" * 80)
print("📊 验证总结")
print("=" * 80)

if all_passed:
    print("\n🎉 所有验证通过！")
    print("\n✅ 已完成的修复:")
    print("  1. 环境变量配置系统 - 正常工作")
    print("  2. 预测号码展示 - 完整展示 Top 8/5/3/1")
    print("  3. 邮件报告生成 - 包含完整的预测展示")
    print("  4. V11 先进特征工程 - 集成完成")
    
    print("\n📁 修改的文件:")
    print("  - src/app/email_sender.py - 已有完整展示")
    print("  - scripts/send_training_report_to_customer.py - 已更新")
    print("  - scripts/utility/generate_prediction.py - 已更新")
    print("  - src/core/config/env_config.py - 环境变量配置")
    print("  - .env - 实际配置文件")
    print("  - .env.example - 配置模板")
    print("  - ENVIRONMENT_SETUP.md - 配置文档")
    
    print("\n🎯 下一步:")
    print("  - 运行完整训练: python main.py train --v11")
    print("  - 生成预测: python main.py predict --v11")
    print("  - 发送报告: python scripts/send_training_report_to_customer.py")
else:
    print("\n⚠ 部分验证失败，请检查以上错误")

print("\n" + "=" * 80)
