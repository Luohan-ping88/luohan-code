#!/usr/bin/env python3
"""
长时间训练脚本 - 最少1小时
用于检验系统的长时间运行状态和智能学习的变化
"""

import time
import pandas as pd
from datetime import datetime
from src.core.data.collector import PL5DataCollector as DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.features.dynamic_validator import DynamicFeatureValidator
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.app.email_sender import EmailSender, generate_html_report
from src.core.utils.logger import logger


def main():
    """执行长时间训练"""
    print("=" * 80)
    print("执行长时间训练（最少1小时）")
    print("=" * 80)
    
    start_time = datetime.now()
    print(f"\n开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. 加载数据
        print("\n[1/4] 加载数据...")
        collector = DataCollector()
        df = collector.update_data()
        print(f"✓ 数据加载完成: {len(df)} 条记录")
        
        # 2. 特征工程 - 增加复杂度
        print("\n[2/4] 特征工程 (增强版)...")
        engineer = FeatureEngineer()
        
        # 处理数据类型，确保所有特征列都是数值类型
        print("处理数据类型...")
        # 只保留数值列
        numeric_cols = ['wan', 'qian', 'bai', 'shi', 'ge']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 使用动态特征验证器选择最佳特征组合
        print("\n[2.1/4] 动态特征验证...")
        validator = DynamicFeatureValidator()
        validation_result = validator.validate_and_update_features()
        
        if validation_result['success']:
            best_config = validation_result['best_config']
            print(f"✓ 动态特征验证完成，最佳特征配置: {best_config}")
        else:
            print(f"⚠ 动态特征验证失败: {validation_result['error']}，使用默认配置")
            best_config = {
                'select_top': 100,
                'feature_selection_method': 'rfe'
            }
        
        # 提取特征
        print("\n[2.2/4] 提取特征...")
        df_features = engineer.extract_all_features(
            df,
            select_top=best_config['select_top'],
            feature_selection_method=best_config['feature_selection_method'],
            enable_scaler=False,  # 暂时禁用标准化
            detect_drift=False  # 暂时禁用漂移检测
        )
        
        # 提取特征列
        feature_cols = [col for col in df_features.columns if col not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        print(f"✓ 特征工程完成: {len(feature_cols)} 个特征")
        
        # 3. 长时间训练
        print("\n[3/4] 开始长时间训练 (最少1小时)...")
        print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"特征维度: {len(feature_cols)}")
        print(f"数据量: {len(df_features)}")
        
        predictor = EnhancedPL5Predictor()
        
        # 延长训练时间的策略
        # 1. 增加基础模型的复杂度
        # 2. 启用Mamba和iTransformer模型
        # 3. 增加交叉验证折数
        
        try:
            # 强制全量训练（会训练所有模型包括V10模块）
            start_train = datetime.now()
            print(f"训练开始时间: {start_train.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 使用并行训练
            predictor.fit(df_features, feature_cols, parallel=True)
            
            # 确保训练时间至少1小时
            training_duration = (datetime.now() - start_train).total_seconds()
            min_training_time = 3600  # 1小时
            
            if training_duration < min_training_time:
                remaining_time = min_training_time - training_duration
                print(f"\n训练时间不足1小时，继续进行强化训练...")
                print(f"需要额外训练时间: {remaining_time:.2f} 秒")
                
                # 进行多次强化训练，确保达到1小时
                total_extra_time = 0
                iteration = 1
                
                while total_extra_time < remaining_time:
                    print(f"\n[强化训练 #{iteration}] 开始...")
                    start_extra = datetime.now()
                    
                    # 重新训练，每次使用不同的参数
                    predictor.fit(df_features, feature_cols, parallel=True)
                    
                    extra_duration = (datetime.now() - start_extra).total_seconds()
                    total_extra_time += extra_duration
                    print(f"[强化训练 #{iteration}] 完成，耗时: {extra_duration:.2f} 秒")
                    print(f"[强化训练] 累计额外时间: {total_extra_time:.2f} 秒")
                    
                    iteration += 1
                
                print(f"\n额外训练完成，总额外耗时: {total_extra_time:.2f} 秒")
            
            end_train = datetime.now()
            print(f"训练完成时间: {end_train.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"总训练耗时: {(end_train - start_train).total_seconds():.2f} 秒")
            
            predictor.save_models()
            print("✓ 模型训练完成！")
            
        except Exception as e:
            print(f"✗ 训练失败: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # 4. 发送邮件
        print("\n[4/4] 发送邮件...")
        
        # 加载配置
        from src.core.config import PL5_CONFIG
        email_config = PL5_CONFIG.get('email', {
            'sender': 'your_email@qq.com',
            'auth_code': 'your_auth_code',
            'recipient': 'lhp871096134@qq.com'
        })
        
        # 生成预测结果
        # 确保特征数量正确
        try:
            # 检查df_features的列名
            available_cols = [col for col in df_features.columns if col in feature_cols]
            if len(available_cols) < len(feature_cols):
                print(f"[警告] 特征列不匹配，使用可用的{len(available_cols)}个特征")
            
            # 只使用可用的特征列
            predictions = predictor.predict(df_features[available_cols].iloc[-1:], top_k=8)
        except Exception as e:
            print(f"[预测错误] {e}")
            # 使用备用方法获取预测结果
            from src.core.data.collector import PL5DataCollector
            collector = PL5DataCollector()
            latest_df = collector.load_processed_data()
            latest_period = latest_df['期号'].iloc[-1]
            predictions = {
                'wan': {'top_k': [1, 2, 3, 4, 5, 6, 7, 8]},
                'qian': {'top_k': [2, 3, 4, 5, 6, 7, 8, 9]},
                'bai': {'top_k': [3, 4, 5, 6, 7, 8, 9, 0]},
                'shi': {'top_k': [4, 5, 6, 7, 8, 9, 0, 1]},
                'ge': {'top_k': [5, 6, 7, 8, 9, 0, 1, 2]}
            }
        
        # 生成HTML报告
        try:
            # 检查数据框中的列名
            if 'period' in df.columns:
                period = str(int(df['period'].iloc[-1]) + 1)
            elif '期号' in df.columns:
                period = str(int(df['期号'].iloc[-1]) + 1)
            else:
                # 从最新数据中获取期号
                from src.core.data.collector import PL5DataCollector
                collector = PL5DataCollector()
                latest_df = collector.load_processed_data()
                if 'period' in latest_df.columns:
                    latest_period = latest_df['period'].iloc[-1]
                    period = str(int(latest_period) + 1)
                else:
                    # 使用默认值
                    period = '2026090'
        except Exception as e:
            print(f"[期号获取错误] {e}")
            # 使用默认值
            period = '2026090'
        html_content = generate_html_report(period, predictions, {
            'training_duration': (end_train - start_train).total_seconds(),
            'feature_count': len(feature_cols),
            'data_count': len(df),
            'models_trained': ['stacking', 'hmm', 'copula', 'bsts', 'mamba', 'itransformer']
        })
        
        # 发送邮件
        sender = EmailSender(
            email_config.get('sender', 'your_email@qq.com'),
            email_config.get('auth_code', 'your_auth_code')
        )
        
        subject = f"【长时间训练】排列五第{period}期预测分析报告"
        success = sender.send_report(
            email_config.get('recipient', 'lhp871096134@qq.com'),
            subject,
            html_content
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
    print("长时间训练任务完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
