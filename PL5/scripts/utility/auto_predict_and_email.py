#!/usr/bin/env python
"""
自动化预测和邮件发送
训练完成后自动执行预测并发送邮件报告
"""
import sys
import os
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def main():
    print('='*60)
    print('PL5 自动化预测与邮件发送')
    print('（训练完成后自动执行）')
    print('='*60)
    print()

    # 1. 加载训练好的模型
    print('[1/3] 加载训练好的模型...')
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

    # 2. 执行预测
    print('[2/3] 执行预测...')
    collector = PL5DataCollectorV8()
    data = collector.load_processed_data()
    
    engineer = FeatureEngineer()
    features = engineer.extract_all_features(data)
    
    # 只使用训练时的特征列
    feature_cols = predictor.feature_cols
    print(f'      使用训练时的 {len(feature_cols)} 个特征列')
    
    # 确保所有特征列都存在
    available_cols = [col for col in feature_cols if col in features.columns]
    missing_cols = [col for col in feature_cols if col not in features.columns]
    if missing_cols:
        print(f'      警告: 缺少 {len(missing_cols)} 个特征列')
    
    # 使用训练时的特征列进行预测
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
        top5 = predictions[position]['top_k'][:5]
        probs = predictions[position]['probabilities'][:5]
        prob_str = ', '.join([f'{p:.1%}' for p in probs])
        print(f'        {position:6s}: {top5}')
        print(f'                概率: {prob_str}')
    print('      ' + '-'*50)
    print()

    # 3. 发送邮件报告
    print('[3/3] 发送邮件报告...')
    try:
        from src.app.email_sender import EmailSender
        import json
        
        # 加载邮件配置
        config_path = 'config/email_config.json'
        if not os.path.exists(config_path):
            print('      警告: 邮件配置文件不存在，跳过邮件发送')
            print(f'      请创建 {config_path} 配置文件')
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            email_conf = json.load(f)
        
        # 支持多种配置格式
        sender_email = email_conf.get('sender_email', '') or email_conf.get('from_email', '')
        auth_code = email_conf.get('auth_code', '')
        recipients = email_conf.get('recipients', []) or [email_conf.get('to_email', '')]
        
        if not sender_email or not auth_code:
            print('      警告: 邮件配置不完整，跳过邮件发送')
            return False
        
        if not recipients:
            print('      警告: 没有配置收件人，跳过邮件发送')
            return False
        
        # 创建邮件发送器
        sender = EmailSender(sender_email, auth_code)
        
        # 构建邮件内容
        subject = f"PL5预测报告 - 第{next_period}期"
        
        # 构建HTML内容
        html_content = f"""
        <h2>PL5排列五预测报告</h2>
        <p><strong>预测期号:</strong> 第{next_period}期</p>
        <p><strong>基于数据:</strong> 第{latest_period}期</p>
        <p><strong>生成时间:</strong> {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <hr>
        <h3>预测结果</h3>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #f0f0f0;">
                <th>位置</th>
                <th>Top 5 推荐</th>
                <th>置信度</th>
            </tr>
        """
        
        for position in ['wan', 'qian', 'bai', 'shi', 'ge']:
            top5 = predictions[position]['top_k'][:5]
            probs = predictions[position]['probabilities'][:5]
            prob_str = ', '.join([f'{p:.1%}' for p in probs])
            html_content += f"""
            <tr>
                <td><strong>{position}</strong></td>
                <td>{top5}</td>
                <td>{prob_str}</td>
            </tr>
            """
        
        html_content += """
        </table>
        <hr>
        <p><small>本报告由PL5智能预测系统自动生成</small></p>
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
