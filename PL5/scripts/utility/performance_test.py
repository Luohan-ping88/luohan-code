#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能测试工具
用于验证性能优化效果
"""

import time
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

from src.core.monitoring.performance_monitor import start_performance_monitoring, stop_performance_monitoring, get_performance_monitor
from src.core.monitoring.bottleneck_detector import detect_bottlenecks, save_bottleneck_report
from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineerV9
from src.core.models.predictor import PL5Predictor
from src.core.utils.logger import setup_logging

logger = setup_logging(__name__)


class PerformanceTester:
    """性能测试器"""
    
    def __init__(self, output_dir: Path = None):
        """初始化性能测试器"""
        self.output_dir = output_dir or Path("logs") / "performance" / "tests"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """开始测试"""
        self.start_time = datetime.now()
        start_performance_monitoring()
        logger.info(f"性能测试开始: {self.start_time}")
    
    def stop(self):
        """停止测试"""
        self.end_time = datetime.now()
        stop_performance_monitoring()
        logger.info(f"性能测试结束: {self.end_time}")
        logger.info(f"测试持续时间: {(self.end_time - self.start_time).total_seconds():.2f} 秒")
    
    def test_data_collection(self) -> dict:
        """测试数据采集性能"""
        logger.info("\n=== 测试数据采集性能 ===")
        start = time.time()
        
        try:
            collector = PL5DataCollector()
            df = collector.update_data()
            end = time.time()
            
            result = {
                'success': True,
                'execution_time': end - start,
                'record_count': len(df) if df is not None else 0,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"数据采集完成，耗时: {result['execution_time']:.2f} 秒, 记录数: {result['record_count']}")
            return result
        except Exception as e:
            end = time.time()
            result = {
                'success': False,
                'execution_time': end - start,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            logger.error(f"数据采集失败: {str(e)}")
            return result
    
    def test_feature_engineering(self, df: pd.DataFrame) -> dict:
        """测试特征工程性能"""
        logger.info("\n=== 测试特征工程性能 ===")
        start = time.time()
        
        try:
            engineer = FeatureEngineerV9()
            # 预热缓存
            engineer.prewarm_cache(df)
            
            # 测试特征提取
            df_features = engineer.extract_all_features(df, select_top=100)
            end = time.time()
            
            result = {
                'success': True,
                'execution_time': end - start,
                'feature_count': len(df_features.columns) - 7,  # 减去原始列
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"特征工程完成，耗时: {result['execution_time']:.2f} 秒, 特征数: {result['feature_count']}")
            return result
        except Exception as e:
            end = time.time()
            result = {
                'success': False,
                'execution_time': end - start,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            logger.error(f"特征工程失败: {str(e)}")
            return result
    
    def test_model_training(self, df: pd.DataFrame, feature_cols: list) -> dict:
        """测试模型训练性能"""
        logger.info("\n=== 测试模型训练性能 ===")
        start = time.time()
        
        try:
            predictor = PL5Predictor()
            predictor.fit(df, feature_cols)
            end = time.time()
            
            # 保存模型
            predictor.save_models()
            
            result = {
                'success': True,
                'execution_time': end - start,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"模型训练完成，耗时: {result['execution_time']:.2f} 秒")
            return result
        except Exception as e:
            end = time.time()
            result = {
                'success': False,
                'execution_time': end - start,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            logger.error(f"模型训练失败: {str(e)}")
            return result
    
    def test_model_prediction(self, features: np.ndarray) -> dict:
        """测试模型预测性能"""
        logger.info("\n=== 测试模型预测性能 ===")
        start = time.time()
        
        try:
            predictor = PL5Predictor()
            if not predictor.load_models():
                raise Exception("模型加载失败")
            
            # 测试多次预测
            predictions = []
            for i in range(10):
                pred = predictor.predict(features)
                predictions.append(pred)
            
            end = time.time()
            avg_time = (end - start) / 10
            
            result = {
                'success': True,
                'execution_time': end - start,
                'average_prediction_time': avg_time,
                'predictions_count': len(predictions),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"模型预测完成，10次预测总耗时: {result['execution_time']:.2f} 秒, 平均每次: {result['average_prediction_time']:.4f} 秒")
            return result
        except Exception as e:
            end = time.time()
            result = {
                'success': False,
                'execution_time': end - start,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            logger.error(f"模型预测失败: {str(e)}")
            return result
    
    def run_full_test(self):
        """运行完整性能测试"""
        self.start()
        
        # 1. 测试数据采集
        data_result = self.test_data_collection()
        self.results['data_collection'] = data_result
        
        if data_result['success']:
            # 2. 测试特征工程
            collector = PL5DataCollector()
            df = collector.load_processed_data()
            if df is not None and not df.empty:
                fe_result = self.test_feature_engineering(df)
                self.results['feature_engineering'] = fe_result
                
                if fe_result['success']:
                    # 提取特征列
                    feature_cols = [col for col in df.columns if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
                    
                    # 3. 测试模型训练
                    train_result = self.test_model_training(df, feature_cols)
                    self.results['model_training'] = train_result
                    
                    if train_result['success']:
                        # 4. 测试模型预测
                        if len(feature_cols) > 0:
                            # 使用最后一行数据作为测试特征
                            test_features = df[feature_cols].iloc[-1].values
                            predict_result = self.test_model_prediction(test_features)
                            self.results['model_prediction'] = predict_result
                        else:
                            self.results['model_prediction'] = {
                                'success': False,
                                'error': 'No feature columns available',
                                'timestamp': datetime.now().isoformat()
                            }
                else:
                    self.results['model_training'] = {
                        'success': False,
                        'error': 'Feature engineering failed',
                        'timestamp': datetime.now().isoformat()
                    }
                    self.results['model_prediction'] = {
                        'success': False,
                        'error': 'Feature engineering failed',
                        'timestamp': datetime.now().isoformat()
                    }
            else:
                self.results['feature_engineering'] = {
                    'success': False,
                    'error': 'No data available',
                    'timestamp': datetime.now().isoformat()
                }
                self.results['model_training'] = {
                    'success': False,
                    'error': 'No data available',
                    'timestamp': datetime.now().isoformat()
                }
                self.results['model_prediction'] = {
                    'success': False,
                    'error': 'No data available',
                    'timestamp': datetime.now().isoformat()
                }
        else:
            self.results['feature_engineering'] = {
                'success': False,
                'error': 'Data collection failed',
                'timestamp': datetime.now().isoformat()
            }
            self.results['model_training'] = {
                'success': False,
                'error': 'Data collection failed',
                'timestamp': datetime.now().isoformat()
            }
            self.results['model_prediction'] = {
                'success': False,
                'error': 'Data collection failed',
                'timestamp': datetime.now().isoformat()
            }
        
        # 5. 检测性能瓶颈
        bottlenecks = detect_bottlenecks()
        self.results['bottlenecks'] = bottlenecks
        
        # 6. 保存瓶颈报告
        report_path = save_bottleneck_report()
        if report_path:
            self.results['bottleneck_report'] = str(report_path)
        
        # 7. 获取性能摘要
        monitor = get_performance_monitor()
        self.results['performance_summary'] = monitor.get_performance_summary()
        
        # 8. 保存测试结果
        self.save_results()
        
        self.stop()
        return self.results
    
    def save_results(self):
        """保存测试结果"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = self.output_dir / f"performance_test_{timestamp}.json"
        
        test_result = {
            'test_time': datetime.now().isoformat(),
            'duration': (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else None,
            'results': self.results,
            'system_info': {
                'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                'platform': sys.platform
            }
        }
        
        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(test_result, f, ensure_ascii=False, indent=2)
            logger.info(f"性能测试结果已保存到: {result_file}")
        except Exception as e:
            logger.error(f"保存测试结果失败: {str(e)}")
    
    def generate_report(self):
        """生成性能测试报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.output_dir / f"performance_report_{timestamp}.md"
        
        report_lines = [
            f"# 性能测试报告",
            f"测试时间: {datetime.now().isoformat()}",
            f"测试持续时间: {(self.end_time - self.start_time).total_seconds():.2f} 秒\n"
        ]
        
        # 数据采集
        dc = self.results.get('data_collection', {})
        report_lines.extend([
            "## 数据采集性能",
            f"状态: {'成功' if dc.get('success') else '失败'}",
            f"执行时间: {dc.get('execution_time', 'N/A'):.2f} 秒",
            f"记录数: {dc.get('record_count', 'N/A')}",
            f"错误: {dc.get('error', '无')}\n"
        ])
        
        # 特征工程
        fe = self.results.get('feature_engineering', {})
        report_lines.extend([
            "## 特征工程性能",
            f"状态: {'成功' if fe.get('success') else '失败'}",
            f"执行时间: {fe.get('execution_time', 'N/A'):.2f} 秒",
            f"特征数: {fe.get('feature_count', 'N/A')}",
            f"错误: {fe.get('error', '无')}\n"
        ])
        
        # 模型训练
        mt = self.results.get('model_training', {})
        report_lines.extend([
            "## 模型训练性能",
            f"状态: {'成功' if mt.get('success') else '失败'}",
            f"执行时间: {mt.get('execution_time', 'N/A'):.2f} 秒",
            f"错误: {mt.get('error', '无')}\n"
        ])
        
        # 模型预测
        mp = self.results.get('model_prediction', {})
        report_lines.extend([
            "## 模型预测性能",
            f"状态: {'成功' if mp.get('success') else '失败'}",
            f"总执行时间: {mp.get('execution_time', 'N/A'):.2f} 秒",
            f"平均每次预测时间: {mp.get('average_prediction_time', 'N/A'):.4f} 秒",
            f"预测次数: {mp.get('predictions_count', 'N/A')}",
            f"错误: {mp.get('error', '无')}\n"
        ])
        
        # 性能瓶颈
        bn = self.results.get('bottlenecks', {})
        report_lines.extend([
            "## 性能瓶颈分析",
            f"系统瓶颈数: {len(bn.get('system', []))}",
            f"函数瓶颈数: {len(bn.get('function', []))}",
            f"性能趋势: {len(bn.get('trends', []))}\n"
        ])
        
        # 性能摘要
        ps = self.results.get('performance_summary', {})
        report_lines.extend([
            "## 性能摘要",
            f"样本数: {ps.get('sample_count', 'N/A')}",
            f"CPU平均使用率: {ps.get('cpu', {}).get('avg', 'N/A'):.1f}%",
            f"CPU最高使用率: {ps.get('cpu', {}).get('max', 'N/A'):.1f}%",
            f"内存平均使用率: {ps.get('memory', {}).get('avg', 'N/A'):.1f}%",
            f"内存最高使用率: {ps.get('memory', {}).get('max', 'N/A'):.1f}%\n"
        ])
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            logger.info(f"性能测试报告已生成: {report_file}")
        except Exception as e:
            logger.error(f"生成报告失败: {str(e)}")


import sys

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='性能测试工具')
    parser.add_argument('--full', action='store_true', help='运行完整测试')
    parser.add_argument('--data', action='store_true', help='仅测试数据采集')
    parser.add_argument('--features', action='store_true', help='仅测试特征工程')
    parser.add_argument('--train', action='store_true', help='仅测试模型训练')
    parser.add_argument('--predict', action='store_true', help='仅测试模型预测')
    parser.add_argument('--output', type=str, help='输出目录')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output) if args.output else None
    tester = PerformanceTester(output_dir)
    
    if args.full:
        results = tester.run_full_test()
        tester.generate_report()
    elif args.data:
        tester.start()
        result = tester.test_data_collection()
        tester.results['data_collection'] = result
        tester.save_results()
        tester.stop()
    elif args.features:
        tester.start()
        collector = PL5DataCollector()
        df = collector.load_processed_data()
        if df is not None and not df.empty:
            result = tester.test_feature_engineering(df)
            tester.results['feature_engineering'] = result
        else:
            tester.results['feature_engineering'] = {
                'success': False,
                'error': 'No data available'
            }
        tester.save_results()
        tester.stop()
    elif args.train:
        tester.start()
        collector = PL5DataCollector()
        df = collector.load_processed_data()
        if df is not None and not df.empty:
            feature_cols = [col for col in df.columns if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
            result = tester.test_model_training(df, feature_cols)
            tester.results['model_training'] = result
        else:
            tester.results['model_training'] = {
                'success': False,
                'error': 'No data available'
            }
        tester.save_results()
        tester.stop()
    elif args.predict:
        tester.start()
        collector = PL5DataCollector()
        df = collector.load_processed_data()
        if df is not None and not df.empty:
            feature_cols = [col for col in df.columns if col not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
            if len(feature_cols) > 0:
                test_features = df[feature_cols].iloc[-1].values
                result = tester.test_model_prediction(test_features)
                tester.results['model_prediction'] = result
            else:
                tester.results['model_prediction'] = {
                    'success': False,
                    'error': 'No feature columns available'
                }
        else:
            tester.results['model_prediction'] = {
                'success': False,
                'error': 'No data available'
            }
        tester.save_results()
        tester.stop()
    else:
        # 默认运行完整测试
        results = tester.run_full_test()
        tester.generate_report()


if __name__ == "__main__":
    main()