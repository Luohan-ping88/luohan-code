#!/usr/bin/env python
"""
自动化预测和邮件发送 - 美化版 V3
包含系统版本号、美化界面、详细性能指标和训练状态
"""
import sys
import os
import pickle
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 系统版本号
SYSTEM_VERSION = "V10.0"
SYSTEM_NAME = "PL5智能预测系统"

def get_performance_metrics():
    """获取性能指标"""
    try:
        eval_file = 'results/evaluation_report_latest.json'
        if os.path.exists(eval_file):
            with open(eval_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return None

def get_training_status():
    """获取训练状态"""
    try:
        model_info_file = 'src/models/model_info.json'
        if os.path.exists(model_info_file):
            with open(model_info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return None

def main():
    print('='*60)
    print(f'{SYSTEM_NAME} {SYSTEM_VERSION}')
    print('自动化预测与邮件发送 - 美化版')
    print('='*60)
    print()

    # 1. 加载训练好的模型
    print('[1/4] 加载训练好的模型...')
    from src.core.models.predictor import PL5Predictor
    from src.core.data.collector import PL5DataCollectorV8
    from src.core.features.engineer import FeatureEngineer
    
    predictor = PL5Predictor()
    
    model_path = 'src/models/pl5_predictor_trained.pkl'
    if not os.path.exists(model_path):
        print('      错误: 未找到训练好的模型！')
        return False
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
    
    predictor.stacking = model_data['stacking']
    predictor.hmm_models = model_data['hmm_models']
    predictor.bsts_models = model_data['bsts_models']
    predictor.evm_models = model_data['evm_models']
    predictor.copula = model_data['copula']
    predictor.is_trained = model_data['is_trained']
    predictor.feature_cols = model_data['feature_cols']
    
    print(f'      模型加载成功！')
    print(f'      特征列数量: {len(predictor.feature_cols)}')
    print()

    # 2. 加载数据
    print('[2/4] 加载全部历史数据...')
    collector = PL5DataCollectorV8()
    data = collector.load_processed_data()
    
    print(f'      数据总量: {len(data)} 条记录')
    print(f'      数据范围: 第{data["period"].iloc[0]}期 至 第{data["period"].iloc[-1]}期')
    print()

    # 3. 执行预测
    print('[3/4] 执行预测...')
    engineer = FeatureEngineer()
    features = engineer.extract_all_features(data)
    
    feature_cols = predictor.feature_cols
    available_cols = [col for col in feature_cols if col in features.columns]
    
    latest_features = features[available_cols].iloc[[-1]]
    predictions = predictor.predict(latest_features)
    
    latest_period = data['period'].iloc[-1]
    next_period = str(int(latest_period) + 1)
    
    print(f'      最新期号: {latest_period}')
    print(f'      预测期号: {next_period}')
    print()
    print('      预测结果:')
    print('      ' + '-'*50)
    for position in ['wan', 'qian', 'bai', 'shi', 'ge']:
        top8 = predictions[position]['top_k'][:8]
        top5 = predictions[position]['top_k'][:5]
        top3 = predictions[position]['top_k'][:3]
        probs = predictions[position]['probabilities'][:5]
        prob_str = ', '.join([f'{p:.1%}' for p in probs])
        print(f'        {position:6s}:')
        print(f'          Top 8: {top8}')
        print(f'          Top 5: {top5} (概率: {prob_str})')
        print(f'          Top 3: {top3}')
    print('      ' + '-'*50)
    print()

    # 4. 发送邮件报告
    print('[4/4] 发送美化版邮件报告...')
    try:
        from src.app.email_sender import EmailSender
        
        config_path = 'config/email_config.json'
        if not os.path.exists(config_path):
            print('      警告: 邮件配置文件不存在')
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            email_conf = json.load(f)
        
        sender_email = email_conf.get('sender_email', '') or email_conf.get('from_email', '')
        auth_code = email_conf.get('auth_code', '')
        recipients = email_conf.get('recipients', []) or [email_conf.get('to_email', '')]
        
        if not sender_email or not auth_code or not recipients:
            print('      警告: 邮件配置不完整')
            return False
        
        sender = EmailSender(sender_email, auth_code)
        
        metrics = get_performance_metrics()
        training_status = get_training_status()
        
        subject = f"🎯 {SYSTEM_NAME} {SYSTEM_VERSION} | 第{next_period}期预测报告"
        
        # 美化版HTML内容
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{SYSTEM_NAME} 预测报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            position: relative;
        }}
        .version-badge {{
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            backdrop-filter: blur(10px);
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); }}
        .header .subtitle {{ font-size: 16px; opacity: 0.9; }}
        .content {{ padding: 30px; }}
        .info-card {{ 
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 25px;
            border-left: 5px solid #667eea;
        }}
        .info-card h3 {{ 
            color: #667eea; 
            margin-bottom: 15px;
            font-size: 18px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .info-row {{ 
            display: flex; 
            justify-content: space-between; 
            padding: 8px 0;
            border-bottom: 1px dashed #ddd;
        }}
        .info-row:last-child {{ border-bottom: none; }}
        .info-label {{ color: #666; font-weight: 500; }}
        .info-value {{ 
            color: #333; 
            font-weight: bold;
        }}
        .highlight-value {{ 
            color: #e74c3c;
            font-size: 20px;
            text-shadow: 1px 1px 2px rgba(231, 76, 60, 0.2);
        }}
        .predictions-section {{ margin-top: 25px; }}
        .predictions-section h3 {{
            color: #333;
            margin-bottom: 20px;
            font-size: 20px;
            text-align: center;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .prediction-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin: 15px 0;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .prediction-table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 10px;
            font-weight: 600;
            text-align: center;
        }}
        .prediction-table td {{
            padding: 15px 10px;
            text-align: center;
            border-bottom: 1px solid #eee;
        }}
        .prediction-table tr:nth-child(even) {{ background-color: #f8f9ff; }}
        .prediction-table tr:hover {{ background-color: #eef0ff; }}
        .position-cell {{
            font-weight: bold;
            color: #667eea;
            font-size: 16px;
        }}
        .top3 {{ 
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-weight: bold;
            display: inline-block;
            box-shadow: 0 2px 8px rgba(238, 90, 90, 0.3);
        }}
        .top5 {{
            background: linear-gradient(135deg, #feca57 0%, #ff9f43 100%);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-weight: 600;
            display: inline-block;
        }}
        .top8 {{
            background: linear-gradient(135deg, #48dbfb 0%, #0abde3 100%);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            display: inline-block;
        }}
        .prob-cell {{
            color: #27ae60;
            font-weight: bold;
        }}
        .metrics-section {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 25px;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }}
        .metric-card:hover {{ transform: translateY(-5px); }}
        .metric-icon {{ font-size: 30px; margin-bottom: 10px; }}
        .metric-label {{ color: #666; font-size: 14px; margin-bottom: 5px; }}
        .metric-value {{ 
            color: #333; 
            font-size: 24px; 
            font-weight: bold;
        }}
        .status-section {{
            background: linear-gradient(135deg, #d299c2 0%, #fef9d7 100%);
            border-radius: 15px;
            padding: 20px;
            margin-top: 25px;
        }}
        .status-section h3 {{
            color: #8e44ad;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .status-badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .status-badge {{
            background: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            color: #555;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .status-badge.success {{ 
            background: #d4edda; 
            color: #155724;
            border: 1px solid #c3e6cb;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
            border-top: 1px solid #eee;
        }}
        .footer .system-info {{
            margin-bottom: 10px;
            font-weight: 500;
        }}
        .divider {{
            height: 3px;
            background: linear-gradient(90deg, transparent, #667eea, transparent);
            margin: 25px 0;
            border-radius: 2px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <div class="version-badge">{SYSTEM_VERSION}</div>
            <h1>🎯 {SYSTEM_NAME}</h1>
            <div class="subtitle">智能预测报告 | 第{next_period}期</div>
        </div>
        
        <div class="content">
            <!-- 基本信息卡片 -->
            <div class="info-card">
                <h3>📊 基本信息</h3>
                <div class="info-row">
                    <span class="info-label">预测期号</span>
                    <span class="info-value highlight-value">第{next_period}期</span>
                </div>
                <div class="info-row">
                    <span class="info-label">基于数据</span>
                    <span class="info-value">第{latest_period}期</span>
                </div>
                <div class="info-row">
                    <span class="info-label">历史数据量</span>
                    <span class="info-value">{len(data)} 期</span>
                </div>
                <div class="info-row">
                    <span class="info-label">数据范围</span>
                    <span class="info-value">第{data['period'].iloc[0]}期 ~ 第{data['period'].iloc[-1]}期</span>
                </div>
                <div class="info-row">
                    <span class="info-label">生成时间</span>
                    <span class="info-value">{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</span>
                </div>
            </div>
            
            <div class="divider"></div>
            
            <!-- 预测结果 -->
            <div class="predictions-section">
                <h3>🎲 预测结果（Top 8 / 5 / 3）</h3>
                <table class="prediction-table">
                    <thead>
                        <tr>
                            <th style="width: 12%;">位置</th>
                            <th style="width: 22%;">🔥 Top 3 推荐</th>
                            <th style="width: 26%;">⭐ Top 5 推荐</th>
                            <th style="width: 26%;">💎 Top 8 推荐</th>
                            <th style="width: 14%;">最高概率</th>
                        </tr>
                    </thead>
                    <tbody>"""
        
        position_names = {'wan': '万位', 'qian': '千位', 'bai': '百位', 'shi': '十位', 'ge': '个位'}
        for position in ['wan', 'qian', 'bai', 'shi', 'ge']:
            top8 = predictions[position]['top_k'][:8]
            top5 = predictions[position]['top_k'][:5]
            top3 = predictions[position]['top_k'][:3]
            max_prob = max(predictions[position]['probabilities'][:5])
            
            html_content += f"""
                        <tr>
                            <td class="position-cell">{position_names[position]}</td>
                            <td><span class="top3">{' '.join(map(str, top3))}</span></td>
                            <td><span class="top5">{' '.join(map(str, top5))}</span></td>
                            <td><span class="top8">{' '.join(map(str, top8))}</span></td>
                            <td class="prob-cell">{max_prob:.1%}</td>
                        </tr>"""
        
        html_content += """
                    </tbody>
                </table>
            </div>
            
            <div class="divider"></div>"""
        
        # 性能指标
        if metrics:
            html_content += f"""
            <!-- 性能指标 -->
            <div class="metrics-section">
                <div class="metric-card">
                    <div class="metric-icon">📈</div>
                    <div class="metric-label">总体准确率</div>
                    <div class="metric-value">{metrics.get('accuracy', 0):.2%}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-icon">🎯</div>
                    <div class="metric-label">近期准确率</div>
                    <div class="metric-value">{metrics.get('recent_accuracy', 0):.2%}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-icon">📊</div>
                    <div class="metric-label">趋势评估</div>
                    <div class="metric-value">{metrics.get('trend', 'N/A')}</div>
                </div>
            </div>"""
        
        html_content += f"""
            
            <!-- 训练状态 -->
            <div class="status-section">
                <h3>🔧 模型状态</h3>
                <div class="status-badges">
                    <span class="status-badge success">✅ 模型已训练</span>
                    <span class="status-badge">特征数量: {len(predictor.feature_cols)}</span>
                    <span class="status-badge">Stacking</span>
                    <span class="status-badge">HMM</span>
                    <span class="status-badge">BSTS</span>
                    <span class="status-badge">EVM</span>
                    <span class="status-badge">Copula</span>
                </div>
            </div>
        </div>
        
        <!-- 页脚 -->
        <div class="footer">
            <div class="system-info">{SYSTEM_NAME} {SYSTEM_VERSION} | 基于 {len(data)} 期历史数据智能分析</div>
            <div>本报告由系统自动生成 | {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
    </div>
</body>
</html>"""
        
        # 发送邮件
        success_count = 0
        for recipient in recipients:
            try:
                result = sender.send_report(recipient, subject, html_content)
                if result:
                    success_count += 1
                    print(f'      ✓ 邮件已发送至: {recipient}')
                else:
                    print(f'      ✗ 邮件发送失败: {recipient}')
            except Exception as e:
                print(f'      ✗ 发送异常 ({recipient}): {str(e)[:50]}')
        
        print(f'\n      邮件发送完成: {success_count}/{len(recipients)} 成功')
        
    except Exception as e:
        print(f'      邮件发送失败: {str(e)[:100]}')
        return False
    
    print()
    print('='*60)
    print('自动化预测与美化版邮件发送完成！')
    print('='*60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
