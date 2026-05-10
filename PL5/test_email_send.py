#!/usr/bin/env python3
"""
测试邮件发送功能
使用与analyze_and_send.py相同的方式发送邮件
"""

import time
from datetime import datetime
from pathlib import Path
import json
import os
from src.core.data.collector import PL5DataCollector
from src.app.email_sender import EmailSender, generate_html_report
from src.core.utils.logger import logger


def generate_text_report(period, predictions):
    """生成纯文本报告"""
    text_report = f"""================================================================================
排列五第{period}期预测分析报告 V10.0
================================================================================

【一、基本信息】
预测期号: {period}
分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
数据量: 7564 条历史记录
特征维度: 145 个特征
训练时间: 3600 秒

【二、预测结果】
"""
    
    position_names = {
        'wan': '万位', 'qian': '千位', 'bai': '百位',
        'shi': '十位', 'ge': '个位'
    }
    
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        pred = predictions.get(pos, {})
        top_k = pred.get('top_k', [])
        top_8 = top_k[:8]
        top_5 = top_k[:5]
        top_3 = top_k[:3]
        
        text_report += f"""
{position_names[pos]}:
  推荐8个号码: {top_8}
  推荐5个号码: {top_5}
  推荐3个号码: {top_3}
"""
    
    text_report += """
【三、风险提示】
1. 彩票本质是概率游戏，任何模型均只能提升概率优势，无法保证100%中奖
2. 本报告仅用于数理研究与规律分析，不构成购彩建议
3. 请理性购彩，量力而行

================================================================================
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
排列五高阶数理分析预测系统 V10.0
================================================================================
"""
    
    return text_report

def main():
    """测试邮件发送"""
    print("=" * 80)
    print("测试邮件发送功能")
    print("=" * 80)
    
    start_time = datetime.now()
    print(f"\n开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. 加载数据获取期号
        print("\n[1/4] 加载数据...")
        collector = PL5DataCollector()
        df = collector.update_data()
        print(f"✓ 数据加载完成: {len(df)} 条记录")
        
        # 2. 生成期号
        print("\n[2/4] 生成期号...")
        try:
            if 'period' in df.columns:
                period = str(int(df['period'].iloc[-1]) + 1)
            elif '期号' in df.columns:
                period = str(int(df['期号'].iloc[-1]) + 1)
            else:
                latest_df = collector.load_processed_data()
                if 'period' in latest_df.columns:
                    latest_period = latest_df['period'].iloc[-1]
                    period = str(int(latest_period) + 1)
                else:
                    period = '2026090'
            print(f"✓ 期号生成成功: {period}")
        except Exception as e:
            print(f"[期号获取错误] {e}")
            period = '2026090'
        
        # 3. 生成预测结果
        print("\n[3/4] 生成预测结果...")
        predictions = {
            'wan': {'top_k': [4, 2, 3, 1, 5, 0, 7, 6]},
            'qian': {'top_k': [4, 3, 5, 2, 1, 0, 7, 6]},
            'bai': {'top_k': [4, 5, 3, 2, 1, 0, 7, 6]},
            'shi': {'top_k': [4, 5, 3, 2, 1, 0, 7, 6]},
            'ge': {'top_k': [4, 5, 3, 2, 1, 0, 7, 6]}
        }
        print("✓ 预测结果生成完成")
        
        # 4. 生成报告
        print("\n[4/4] 生成报告...")
        html_report = generate_html_report(period, predictions, {
            'training_duration': 3600,
            'feature_count': 145,
            'data_count': len(df),
            'models_trained': ['stacking', 'hmm', 'copula', 'bsts']
        })
        text_report = generate_text_report(period, predictions)
        print("✓ 报告生成完成")
        
        # 5. 读取邮箱配置
        print("\n[5/5] 读取邮箱配置...")
        config_path_new = Path(__file__).parent / 'config' / 'email_config.json'
        config_path_old = Path(__file__).parent / 'email_config.json'
        
        sender_email = "your_email@qq.com"
        auth_code = "your_auth_code"
        recipient_email = "lhp871096134@qq.com"
        
        if config_path_new.exists():
            with open(config_path_new, 'r', encoding='utf-8') as f:
                email_config = json.load(f)
            sender_email = email_config.get('from_email', sender_email)
            auth_code = email_config.get('auth_code', auth_code)
            recipient_email = email_config.get('to_email', recipient_email)
            print(f"✓ 从配置文件读取邮箱配置: {sender_email}")
        elif config_path_old.exists():
            with open(config_path_old, 'r', encoding='utf-8') as f:
                email_config = json.load(f)
            sender_email = email_config.get('from_email', sender_email)
            auth_code = email_config.get('auth_code', auth_code)
            recipient_email = email_config.get('to_email', recipient_email)
            print(f"✓ 从旧配置文件读取邮箱配置: {sender_email}")
        else:
            # 尝试从环境变量读取
            sender_email = os.environ.get('PL5_EMAIL', sender_email)
            auth_code = os.environ.get('PL5_AUTH_CODE', auth_code)
            recipient_email = os.environ.get('PL5_RECIPIENT', recipient_email)
            print(f"✓ 从环境变量读取邮箱配置: {sender_email}")
        
        # 6. 发送邮件
        print("\n[6/6] 发送邮件...")
        sender = EmailSender(sender_email, auth_code)
        
        subject = f"排列五第{period}期预测分析报告 V10.0 - {datetime.now().strftime('%Y-%m-%d')}"
        
        # 使用关键字参数，与analyze_and_send.py相同
        success = sender.send_report(
            recipient_email=recipient_email,
            subject=subject,
            html_content=html_report,
            text_content=text_report
        )
        
        if success:
            print("✓ 邮件发送成功！")
        else:
            print("✗ 邮件发送失败！")
        
    except Exception as e:
        print(f"✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    end_time = datetime.now()
    print(f"\n结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {(end_time - start_time).total_seconds():.2f} 秒")
    print("\n" + "=" * 80)
    print("邮件发送测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
