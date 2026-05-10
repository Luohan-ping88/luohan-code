#!/usr/bin/env python
"""
自动化预测和邮件发送 - 增强版
包含详细的性能指标和训练状态
"""
import sys
import os
import pickle
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def get_performance_metrics():
    """获取性能指标"""
    try:
        # 加载评估报告
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
        # 加载模型信息
        model_info_file = 'src/models/model_info.json'
        if os.path.exists(model_info_file):
            with open(model_info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return None

def main():
    print('='*60)
    print('PL5 自动化预测与邮件发送 - 增强版')
    print('（训练完成后自动执行）')
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

    # 2. 加载数据（全部历史数据）
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
    
    # 只使用训练时的特征列
    feature_cols = predictor.feature_cols
    available_cols = [col for col in feature_cols if col in features.columns]
    
    # 使用最新数据进行预测
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
    print('[4/4] 发送详细邮件报告...')
    try:
        from src.app.email_sender import EmailSender
        
        # 加载邮件配置
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
        
        # 创建邮件发送器
        sender = EmailSender(sender_email, auth_code)
        
        # 获取性能指标
        metrics = get_performance_metrics()
        training_status = get_training_status()
        
        # 构建邮件内容
        subject = f"PL5预测报告 - 第{next_period}期（详细版）"
        
        # 构建HTML内容
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                h2 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                h3 {{ color: #555; margin-top: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #007bff; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .highlight {{ background-color: #fff3cd; font-weight: bold; }}
                .metric {{ display: inline-block; margin: 5px 15px 5px 0; padding: 8px 15px; background: #e9ecef; border-radius: 5px; }}
                .top3 {{ color: #d9534f; font-weight: bold; }}
                .top5 {{ color: #f0ad4e; }}
                .top8 {{ color: #5bc0de; }}
            </style>
        </head>
        <body>
            <h2>🎯 PL5排列五预测报告（详细版）</h2>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <h3>📊 基本信息</h3>
                <p><strong>预测期号:</strong> <span style="font-size: 18px; color: #d9534f;">第{next_period}期</span></p>
                <p><strong>基于数据:</strong> 第{latest_period}期（共{len(data)}期历史数据）</p>
                <p><strong>数据范围:</strong> 第{data['period'].iloc[0]}期 至 第{data['period'].iloc[-1]}期</p>
                <p><strong>生成时间:</strong> {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
            </div>
            
            <h3>🎲 预测结果（Top 8/5/3）</h3>
            <table>
                <tr>
                    <th>位置</th>
                    <th class="top3">Top 3 推荐</th>
                    <th class="top5">Top 5 推荐</th>
                    <th class="top8">Top 8 推荐</th>
                    <th>最高概率</th>
                </tr>
        """
        
        for position in ['wan', 'qian', 'bai', 'shi', 'ge']:
            top8 = predictions[position]['top_k'][:8]
            top5 = predictions[position]['top_k'][:5]
            top3 = predictions[position]['top_k'][:3]
            max_prob = max(predictions[position]['probabilities'][:5])
            
            html_content += f"""
                <tr>
                    <td><strong>{position.upper()}</strong></td>
                    <td class="top3">{top3}</td>
                    <td class="top5">{top5}</td>
                    <td class="top8">{top8}</td>
                    <td>{max_prob:.1%}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h3>📈 详细概率分布</h3>
            <table>
                <tr>
                    <th>位置</th>
                    <th>号码</th>
                    <th>概率</th>
                    <th>号码</th>
                    <th>概率</th>
                    <th>号码</th>
                    <th>概率</th>
                </tr>
        """
        
        for position in ['wan', 'qian', 'bai', 'shi', 'ge']:
            top3 = predictions[position]['top_k'][:3]
            probs = predictions[position]['probabilities'][:3]
            
            html_content += f"""
                <tr>
                    <td><strong>{position.upper()}</strong></td>
                    <td class="highlight">{top3[0]}</td>
                    <td class="highlight">{probs[0]:.1%}</td>
                    <td>{top3[1]}</td>
                    <td>{probs[1]:.1%}</td>
                    <td>{top3[2]}</td>
                    <td>{probs[2]:.1%}</td>
                </tr>
            """
        
        html_content += "</table>"
        
        # 添加性能指标
        if metrics:
            html_content += f"""
            <h3>📊 模型性能指标</h3>
            <div style="background: #e8f5e9; padding: 15px; border-radius: 5px;">
                <div class="metric">总体准确率: {metrics.get('accuracy', 'N/A'):.2%}</div>
                <div class="metric">近期准确率: {metrics.get('recent_accuracy', 'N/A'):.2%}</div>
                <div class="metric">趋势: {metrics.get('trend', 'N/A')}</div>
            </div>
            """
        
        # 添加训练状态
        html_content += f"""
            <h3>🔧 训练状态</h3>
            <div style="background: #e3f2fd; padding: 15px; border-radius: 5px;">
                <div class="metric">模型已训练: {'是' if predictor.is_trained else '否'}</div>
                <div class="metric">特征数量: {len(predictor.feature_cols)}</div>
                <div class="metric">模型组件: Stacking + HMM + BSTS + EVM + Copula</div>
            </div>
            
            <hr style="margin: 30px 0;">
            <p style="color: #666; font-size: 12px; text-align: center;">
                <small>本报告由PL5智能预测系统自动生成 | 基于{len(data)}期历史数据训练</small>
            </p>
        </body>
        </html>
        """
        
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
    print('自动化预测与邮件发送完成！')
    print('='*60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
