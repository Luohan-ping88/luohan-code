"""
邮件发送模块 - 发送预测报告到邮箱
V10.0版本 - 全彩色清晰版
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import logging
from src.core.utils.logger import logger


class EmailSender:
    """邮件发送器"""
    
    def __init__(self, sender_email: str, auth_code: str, smtp_server: str = "smtp.qq.com", smtp_port: int = 465):
        self.sender_email = sender_email
        self.auth_code = auth_code
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
    
    def send_report(self, recipient_email: str, subject: str, html_content: str, text_content: str = None):
        """发送报告邮件
        
        Raises:
            smtplib.SMTPException: SMTP通信错误，由外层 execute_with_retry 处理重试
            Exception: 其他异常，同样由外层重试机制处理
        """
        # 创建邮件对象
        msg = MIMEMultipart('alternative')
        msg['From'] = self.sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # 添加纯文本内容
        if text_content:
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        
        # 添加HTML内容
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # 连接SMTP服务器并发送
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
            server.login(self.sender_email, self.auth_code)
            server.sendmail(self.sender_email, recipient_email, msg.as_string())
        
        logger.info(f"✓ 邮件发送成功: {recipient_email}")
        return True


def generate_html_report(period: str, predictions: dict, analysis_data: dict, data_count: int, latest_period: str) -> str:
    """生成HTML格式的报告 - 全彩色清晰版"""
    
    position_names = {
        'wan': '万位',
        'qian': '千位',
        'bai': '百位',
        'shi': '十位',
        'ge': '个位'
    }
    
    # 提取预测结果
    top_8 = {}
    top_5 = {}
    top_3 = {}
    top_1 = {}
    
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        pred = predictions.get(pos, {})
        top_k = pred.get('top_k', [])
        top_8[pos] = top_k[:8]
        top_5[pos] = top_k[:5]
        top_3[pos] = top_k[:3]
        top_1[pos] = top_k[:1]
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>排列五第{period}期预测分析报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #E8D5F2 0%, #D5E8F2 100%);
            padding: 10px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: linear-gradient(180deg, #FFFAF5 0%, #FFF5F0 100%);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(139, 123, 232, 0.15);
        }}
        /* 头部 - 温暖渐变 */
        .header {{
            background: linear-gradient(135deg, #A8B5E8 0%, #D4A8E8 50%, #E8A8C8 100%);
            color: white;
            padding: 25px 20px;
            text-align: center;
        }}
        .header-title {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-bottom: 6px;
        }}
        .header-icon {{
            width: 32px;
            height: 32px;
            background: rgba(255,255,255,0.25);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            font-size: 22px;
            font-weight: 700;
            margin: 0;
            color: #FFFFFF;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
            letter-spacing: 1px;
        }}
        .header-subtitle {{
            font-size: 14px;
            margin-top: 6px;
            color: #FFFFFF;
            opacity: 0.95;
            text-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }}
        /* 内容区 */
        .content {{
            padding: 18px;
        }}
        /* 信息卡片 - 柔和背景 */
        .info-card {{
            background: linear-gradient(135deg, #F0F4FF 0%, #F8F0FF 100%);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            border: 1px solid rgba(168, 181, 232, 0.2);
        }}
        .info-card h2 {{
            font-size: 15px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
            color: #7B68EE;
            font-weight: 700;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }}
        .info-item {{
            display: flex;
            flex-direction: column;
            gap: 3px;
        }}
        .info-label {{
            font-size: 12px;
            color: #888888;
            font-weight: 500;
        }}
        .info-value {{
            font-size: 14px;
            font-weight: 600;
            color: #444444;
        }}
        .info-value.highlight {{
            color: #7B68EE;
            font-weight: 700;
        }}
        /* 预测结果 */
        .prediction-section {{
            margin-bottom: 16px;
        }}
        .section-header {{
            background: linear-gradient(135deg, #A8B5E8 0%, #D4A8E8 100%);
            color: white;
            padding: 12px 16px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 14px;
            box-shadow: 0 4px 12px rgba(168, 181, 232, 0.3);
        }}
        .position-card {{
            background: #FFFFFF;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 14px;
            border: 2px solid #E8E0F0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        .position-name {{
            font-size: 18px;
            font-weight: 800;
            margin-bottom: 14px;
            color: #4A3FB5;
            text-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }}
        .prediction-rows {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .prediction-row {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .row-label {{
            font-size: 14px;
            width: 55px;
            flex-shrink: 0;
            color: #555555;
            font-weight: 700;
        }}
        .number-list {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .number {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 15px;
            color: #FFFFFF;
            text-shadow: 0 1px 2px rgba(0,0,0,0.2);
            border: 2px solid rgba(255,255,255,0.5);
        }}
        .number.top1 {{
            background: #FF7A9A;
            box-shadow: 0 3px 8px rgba(255, 122, 154, 0.5);
        }}
        .number.top3 {{
            background: #5A9AE8;
            box-shadow: 0 3px 8px rgba(90, 154, 232, 0.5);
        }}
        .number.top5 {{
            background: #4AC4C4;
            box-shadow: 0 3px 8px rgba(74, 196, 196, 0.5);
        }}
        .number.top8 {{
            background: #8CD65A;
            box-shadow: 0 3px 8px rgba(140, 214, 90, 0.5);
        }}
        /* 模型状态 */
        .model-section {{
            background: linear-gradient(135deg, #F5FFF0 0%, #F0FFF5 100%);
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 16px;
            border: 1px solid rgba(168, 232, 125, 0.2);
        }}
        .model-section h3 {{
            font-size: 14px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
            color: #4A9A6A;
            font-weight: 700;
        }}
        .model-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .model-tag {{
            padding: 6px 14px;
            border-radius: 14px;
            font-size: 12px;
            font-weight: 700;
        }}
        .model-tag.active {{
            background: #E8F5E9;
            color: #2E7D32;
            border: 2px solid #81C784;
        }}
        .model-tag.inactive {{
            background: #FFEBEE;
            color: #C62828;
            border: 2px solid #EF9A9A;
        }}
        /* 风险提示 */
        .warning {{
            background: linear-gradient(135deg, #FFF9E8 0%, #FFF5D8 100%);
            border: 1px solid #FFE8A0;
            border-radius: 10px;
            padding: 14px;
            margin-top: 12px;
        }}
        .warning-title {{
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 8px;
            color: #E65100;
        }}
        .warning-text {{
            font-size: 12px;
            line-height: 1.7;
            color: #5D4037;
            font-weight: 500;
        }}
        /* 底部 */
        .footer {{
            background: linear-gradient(135deg, #F8F0FF 0%, #F0F8FF 100%);
            padding: 16px;
            text-align: center;
            border-top: 1px solid rgba(168, 181, 232, 0.2);
        }}
        .footer-text {{
            font-size: 12px;
            line-height: 1.6;
            color: #7A7A9A;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <div class="header-title">
                <div class="header-icon">🎯</div>
                <h1>PL5智能预测系统</h1>
            </div>
            <div class="header-subtitle">排列五第{period}期预测分析报告</div>
        </div>
        
        <div class="content">
            <!-- 基本信息 -->
            <div class="info-card">
                <h2>📋 基本信息</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">预测期号</span>
                        <span class="info-value highlight">第{period}期</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">基于数据</span>
                        <span class="info-value">第{int(period)-1}期</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">历史数据量</span>
                        <span class="info-value">{data_count}期</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">分析时间</span>
                        <span class="info-value">{current_time}</span>
                    </div>
                </div>
            </div>
            
            <!-- 预测结果 -->
            <div class="prediction-section">
                <div class="section-header">🎯 预测结果 (Top 8 / 5 / 3)</div>
"""
    
    # 生成每个位置的预测卡片
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        pos_name = position_names.get(pos, pos)
        
        html += f"""
                <div class="position-card">
                    <div class="position-name">{pos_name}</div>
                    <div class="prediction-rows">
                        <div class="prediction-row">
                            <span class="row-label">Top 1</span>
                            <div class="number-list">
                                {''.join([f'<span class="number top1">{n}</span>' for n in top_1.get(pos, [])])}
                            </div>
                        </div>
                        <div class="prediction-row">
                            <span class="row-label">Top 3</span>
                            <div class="number-list">
                                {''.join([f'<span class="number top3">{n}</span>' for n in top_3.get(pos, [])])}
                            </div>
                        </div>
                        <div class="prediction-row">
                            <span class="row-label">Top 5</span>
                            <div class="number-list">
                                {''.join([f'<span class="number top5">{n}</span>' for n in top_5.get(pos, [])])}
                            </div>
                        </div>
                        <div class="prediction-row">
                            <span class="row-label">Top 8</span>
                            <div class="number-list">
                                {''.join([f'<span class="number top8">{n}</span>' for n in top_8.get(pos, [])])}
                            </div>
                        </div>
                    </div>
                </div>
"""
    
    html += """
            </div>
            
            <!-- 模型状态 -->
            <div class="model-section">
                <h3>🔧 模型状态</h3>
                <div class="model-tags">
                    <span class="model-tag active">Stacking</span>
                    <span class="model-tag active">HMM</span>
                    <span class="model-tag active">Copula</span>
                    <span class="model-tag active">BSTS</span>
"""
    
    # 根据V10模块状态显示标签
    if analysis_data and 'mamba' in str(analysis_data).lower():
        html += '<span class="model-tag active">Mamba</span>'
    else:
        html += '<span class="model-tag inactive">Mamba</span>'
        
    if analysis_data and 'itransformer' in str(analysis_data).lower():
        html += '<span class="model-tag active">iTransformer</span>'
    else:
        html += '<span class="model-tag inactive">iTransformer</span>'
    
    html += f"""
                </div>
            </div>
            
            <!-- 风险提示 -->
            <div class="warning">
                <div class="warning-title">⚠️ 风险提示</div>
                <div class="warning-text">
                    1. 彩票本质是概率游戏，任何模型均只能提升概率优势，无法保证100%中奖<br>
                    2. 本报告仅用于数理研究与规律分析，不构成购彩建议<br>
                    3. 请理性购彩，量力而行
                </div>
            </div>
        </div>
        
        <!-- 底部 -->
        <div class="footer">
            <div class="footer-text">
                PL5智能预测系统 V10.3 | 基于深度学习与数理统计<br>
                本报告由系统自动生成
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    return html


if __name__ == "__main__":
    import os
    
    sender_email = os.environ.get('PL5_EMAIL', 'your_email@qq.com')
    auth_code = os.environ.get('PL5_AUTH_CODE', 'your_auth_code')
    
    sender = EmailSender(sender_email, auth_code)
    
    test_predictions = {
        'wan': {'top_k': [1, 5, 0, 7, 3, 4, 8, 6]},
        'qian': {'top_k': [4, 1, 3, 5, 9, 0, 2, 7]},
        'bai': {'top_k': [9, 5, 1, 7, 4, 8, 0, 3]},
        'shi': {'top_k': [6, 4, 8, 2, 1, 5, 9, 3]},
        'ge': {'top_k': [7, 2, 9, 4, 1, 5, 3, 6]}
    }
    
    html = generate_html_report("2026090", test_predictions, {})
    
    print("HTML报告生成完成")
    print("提示: 请设置环境变量 PL5_EMAIL 和 PL5_AUTH_CODE 后再发送邮件")
