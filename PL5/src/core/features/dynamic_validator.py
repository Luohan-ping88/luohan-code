#!/usr/bin/env python3
"""
动态特征组验证器
用于依据开奖数据的变化采用动态的多维特征组验证训练策略
"""

import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.config import MODEL_CONFIG, MODELS_DIR, LOGS_DIR

logger = logging.getLogger(__name__)


class DynamicFeatureValidator:
    """动态特征组验证器
    
    用于依据开奖数据的变化采用动态的多维特征组验证训练策略
    能够适应开奖数据的变化及检验出最佳特征组合
    """
    
    def __init__(self):
        self.collector = PL5DataCollector()
        self.engineer = FeatureEngineer()
        self.best_feature_config = None
        self.validation_history = []
        
    def generate_feature_combinations(self) -> List[Dict[str, Any]]:
        """生成多种特征组合策略
        
        Returns:
            List[Dict[str, Any]]: 特征组合策略列表
        """
        feature_combinations = [
            {
                'name': 'full_features',
                'description': '全量特征',
                'select_top': None,
                'feature_selection_method': 'rfe'
            },
            {
                'name': 'top_50_rfe',
                'description': 'RFE选择前50个特征',
                'select_top': 50,
                'feature_selection_method': 'rfe'
            },
            {
                'name': 'top_100_rfe',
                'description': 'RFE选择前100个特征',
                'select_top': 100,
                'feature_selection_method': 'rfe'
            },
            {
                'name': 'top_150_rfe',
                'description': 'RFE选择前150个特征',
                'select_top': 150,
                'feature_selection_method': 'rfe'
            },
            {
                'name': 'top_50_model_based',
                'description': '模型选择前50个特征',
                'select_top': 50,
                'feature_selection_method': 'model_based'
            },
            {
                'name': 'top_100_model_based',
                'description': '模型选择前100个特征',
                'select_top': 100,
                'feature_selection_method': 'model_based'
            }
        ]
        
        return feature_combinations
    
    def validate_feature_combination(self, df: pd.DataFrame, config: Dict[str, Any], time_budget: float = 60.0) -> Dict[str, Any]:
        """验证单个特征组合的性能
        
        Args:
            df: 输入数据
            config: 特征组合配置
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        try:
            logger.info(f"验证特征组合: {config['name']} ({config['description']})")
            
            # 提取特征
            df_features = self.engineer.extract_all_features(
                df,
                select_top=config['select_top'],
                feature_selection_method=config['feature_selection_method']
            )
            
            # 提取特征列
            feature_cols = [col for col in df_features.columns 
                          if col not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
            
            # 划分训练集和测试集
            test_size = 20
            if len(df_features) < test_size * 2:
                logger.warning(f"数据量不足，使用全部数据进行验证")
                train_data = df_features
                test_data = df_features.tail(5)
            else:
                train_data = df_features.iloc[:-test_size]
                test_data = df_features.iloc[-test_size:]
            
            # 训练模型
            import time as _time_module
            _comb_start = _time_module.time()
            predictor = EnhancedPL5Predictor()
            predictor.fit(train_data, feature_cols)
            
            # 验证模型（带时间预算限制）
            total_hits = 0
            total_tests = 0
            _comb_deadline = _comb_start + time_budget
            
            for i, row in test_data.iterrows():
                if _time_module.time() > _comb_deadline:
                    logger.warning(f"特征组合 {config['name']} 验证超时({time_budget:.0f}s)，提前结束")
                    break
                # 提取特征向量
                features_list = []
                for col in feature_cols:
                    val = row[col]
                    # 处理可能的 Inf/NaN 和类型问题
                    try:
                        val = float(val)
                        if np.isfinite(val):
                            features_list.append(val)
                        else:
                            features_list.append(0.0)
                    except (ValueError, TypeError):
                        features_list.append(0.0)
                
                features = np.array(features_list, dtype=np.float64)
                
                # 准备最近的原始数据
                recent_original_data = {}
                for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                    if pos in df.columns:
                        recent_data = df[pos].values[-20:] if len(df) >= 20 else df[pos].values
                        recent_original_data[pos] = recent_data
                
                # 预测
                predictions = predictor.predict(
                    features=features,
                    recent_original_data=recent_original_data,
                    top_k=8,
                    use_rl=False,
                    use_uncertainty=False
                )
                
                # 验证预测结果
                for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                    actual_value = int(row[pos])
                    if pos in predictions and 'top_k' in predictions[pos]:
                        top_k = predictions[pos]['top_k']
                        if actual_value in top_k:
                            total_hits += 1
                        total_tests += 1
            
            # 计算准确率
            accuracy = total_hits / total_tests if total_tests > 0 else 0
            
            result = {
                'name': config['name'],
                'description': config['description'],
                'select_top': config['select_top'],
                'feature_selection_method': config['feature_selection_method'],
                'feature_count': len(feature_cols),
                'accuracy': accuracy,
                'hits': total_hits,
                'tests': total_tests,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"特征组合 {config['name']} 验证完成，准确率: {accuracy:.4f}")
            return result
            
        except Exception as e:
            logger.error(f"验证特征组合 {config['name']} 失败: {e}")
            return {
                'name': config['name'],
                'description': config['description'],
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def find_best_feature_combination(self, df: pd.DataFrame) -> Dict[str, Any]:
        """寻找最佳特征组合
        
        智能策略：基于数据变化量决定验证深度
        - 数据变化小（<5%新数据）：快速验证（1-2组合）
        - 数据变化中（5-20%）：标准验证（3-4组合）
        - 数据变化大（>20%）：完整验证（全部组合）
        
        Args:
            df: 输入数据
            
        Returns:
            Dict[str, Any]: 最佳特征组合配置
        """
        logger.info("开始寻找最佳特征组合...")
        
        import time
        import hashlib
        
        feature_combinations = self.generate_feature_combinations()
        
        # 计算当前数据指纹（基于最近1000条数据的统计特征）
        df_recent = df.tail(1000)
        data_hash = hashlib.md5(
            pd.util.hash_pandas_object(df_recent, index=False).values.tobytes()
        ).hexdigest()[:16]
        
        # 检查数据是否发生变化
        config_path = MODELS_DIR / "best_feature_config.json"
        prev_hash_path = MODELS_DIR / ".data_hash"
        data_changed = True
        prev_hash = None
        
        if prev_hash_path.exists():
            prev_hash = prev_hash_path.read_text().strip()
            data_changed = (data_hash != prev_hash)
        
        if not data_changed and config_path.exists():
            try:
                with open(config_path) as f:
                    config_data = json.load(f)
                best_config = config_data.get('best_config', {})
                logger.info(f"数据未变化（hash={data_hash}），使用缓存的最佳配置: {best_config}")
                self.best_feature_config = best_config
                return best_config
            except Exception:
                pass
        
        logger.info(f"数据发生变化（hash={data_hash}），执行特征验证...")
        prev_hash_path.write_text(data_hash)
        
        # 计算数据变化比例
        new_records_ratio = len(df_recent) / max(len(df), 1)
        n_combos = len(feature_combinations)
        
        if new_records_ratio < 0.05:
            n_to_test = min(2, n_combos)
            logger.info(f"数据变化较小（{new_records_ratio*100:.1f}%），快速验证前{n_to_test}个组合")
        elif new_records_ratio < 0.20:
            n_to_test = min(4, n_combos)
            logger.info(f"数据变化中等（{new_records_ratio*100:.1f}%），标准验证前{n_to_test}个组合")
        else:
            n_to_test = n_combos
            logger.info(f"数据变化较大（{new_records_ratio*100:.1f}%），完整验证全部{n_to_test}个组合")
        
        # 优先测试对预测最有影响力的组合
        priority_order = feature_combinations[:n_to_test]
        
        validation_results = []
        for config in priority_order:
            result = self.validate_feature_combination(df, config)
            if 'error' not in result:
                validation_results.append(result)
        
        # 选择最佳特征组合
        if validation_results:
            best_result = max(validation_results, key=lambda x: x['accuracy'])
            logger.info(f"最佳特征组合: {best_result['name']}，准确率: {best_result['accuracy']:.4f}")
            
            # 更新最佳特征配置
            self.best_feature_config = {
                'select_top': best_result['select_top'],
                'feature_selection_method': best_result['feature_selection_method']
            }
            
            # 记录验证历史
            self.validation_history.append({
                'timestamp': datetime.now().isoformat(),
                'best_feature_combination': best_result,
                'all_results': validation_results
            })
            
            return self.best_feature_config
        else:
            logger.warning("所有特征组合验证失败，使用默认配置")
            return {
                'select_top': None,
                'feature_selection_method': 'rfe'
            }
    
    def get_best_feature_config(self) -> Dict[str, Any]:
        """获取最佳特征配置
        
        Returns:
            Dict[str, Any]: 最佳特征配置
        """
        if self.best_feature_config is None:
            # 如果没有最佳配置，使用默认配置
            return {
                'select_top': None,
                'feature_selection_method': 'rfe'
            }
        return self.best_feature_config
    
    def validate_and_update_features(self) -> Dict[str, Any]:
        """验证并更新特征配置
        
        Returns:
            Dict[str, Any]: 验证结果
        """
        # 加载最新数据（使用 update_data 而非 load_processed_data，确保数据最新）
        df = self.collector.update_data()
        if df is None:
            logger.error("无法加载数据，使用默认特征配置")
            return {
                'success': False,
                'error': '无法加载数据'
            }
        
        # 寻找最佳特征组合
        best_config = self.find_best_feature_combination(df)
        
        # 保存最佳特征配置（同时保存到 models 和 logs 目录，保持内容一致）
        config_data = {
            'best_config': best_config,
            'validation_history': self.validation_history[-5:],  # 只保存最近5次验证结果
            'last_updated': datetime.now().isoformat()
        }
        try:
            import json
            for config_dir in [MODELS_DIR, LOGS_DIR]:
                config_path = config_dir / "best_feature_config.json"
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                logger.info(f"最佳特征配置已保存到: {config_path}")
        except Exception as e:
            logger.error(f"保存最佳特征配置失败: {e}")
        
        return {
            'success': True,
            'best_config': best_config,
            'validation_history': self.validation_history[-1:]
        }


if __name__ == "__main__":
    # 测试动态特征验证器
    validator = DynamicFeatureValidator()
    result = validator.validate_and_update_features()
    print(f"验证结果: {result}")
