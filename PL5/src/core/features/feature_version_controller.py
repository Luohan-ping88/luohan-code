"""
特征版本控制器 - V10.5
确保训练-预测特征一致性，检测特征漂移
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class FeatureVersionController:
    """
    特征版本控制器
    
    功能：
    1. 记录训练时的特征版本（特征名称、统计信息）
    2. 验证预测时的特征版本一致性
    3. 检测特征漂移
    4. 提供版本回滚能力
    """
    
    def __init__(self, version_file: Optional[Path] = None):
        self.version_file = version_file or Path("logs/feature_version.json")
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.current_version = None
        self.version_history: List[Dict[str, Any]] = []
        self._load_version()
    
    def _load_version(self):
        """加载历史版本"""
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.version_history = data.get('history', [])
                    self.current_version = self.version_history[-1] if self.version_history else None
                    logger.info(f"已加载特征版本历史，共{len(self.version_history)}个版本")
            except Exception as e:
                logger.warning(f"加载特征版本历史失败: {e}")
                self.version_history = []
                self.current_version = None
    
    def _save_version(self):
        """保存版本历史"""
        try:
            data = {
                'history': self.version_history[-100:],  # 只保留最近100个版本
                'last_updated': datetime.now().isoformat()
            }
            with open(self.version_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存特征版本历史失败: {e}")
    
    def _compute_feature_signature(self, df: pd.DataFrame, feature_cols: List[str]) -> str:
        """
        计算特征签名（基于特征名称和统计信息）
        """
        # 使用特征名称列表
        feature_names = sorted([c for c in feature_cols if c not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']])
        
        # 计算特征统计信息
        stats = {}
        for col in feature_names[:20]:  # 只取前20个特征计算统计（性能考虑）
            if col in df.columns:
                stats[col] = {
                    'mean': float(df[col].mean()) if not df[col].isna().all() else 0,
                    'std': float(df[col].std()) if not df[col].isna().all() else 0,
                }
        
        # 生成签名
        sig_data = {
            'feature_names': feature_names,
            'n_features': len(feature_names),
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }
        
        sig_str = json.dumps(sig_data, sort_keys=True)
        return hashlib.sha256(sig_str.encode()).hexdigest()[:16]
    
    def record_version(self, df: pd.DataFrame, feature_cols: List[str], 
                      metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        记录特征版本
        
        Args:
            df: 特征数据
            feature_cols: 特征列名列表
            metadata: 额外元数据（如训练时间、数据量等）
            
        Returns:
            版本信息字典
        """
        signature = self._compute_feature_signature(df, feature_cols)
        
        version_info = {
            'version_id': len(self.version_history) + 1,
            'signature': signature,
            'timestamp': datetime.now().isoformat(),
            'n_features': len([c for c in feature_cols if c not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]),
            'feature_names': sorted([c for c in feature_cols if c not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]),
            'metadata': metadata or {},
            'data_hash': hashlib.md5(df['period'].values.tobytes()).hexdigest()[:16]
        }
        
        self.version_history.append(version_info)
        self.current_version = version_info
        self._save_version()
        
        logger.info(f"已记录特征版本 v{version_info['version_id']}, "
                   f"签名={signature[:8]}, 特征数={version_info['n_features']}")
        
        return version_info
    
    def validate_version(self, df: pd.DataFrame, feature_cols: List[str],
                        strict: bool = False) -> Dict[str, Any]:
        """
        验证特征版本一致性
        
        Args:
            df: 当前特征数据
            feature_cols: 当前特征列名列表
            strict: 是否严格模式（检查统计信息）
            
        Returns:
            验证结果字典
        """
        if self.current_version is None:
            logger.warning("没有已记录的特征版本，跳过验证")
            return {
                'valid': True,
                'has_version': False,
                'message': '首次运行，无历史版本'
            }
        
        current_signature = self._compute_feature_signature(df, feature_cols)
        current_names = sorted([c for c in feature_cols if c not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']])
        expected_names = self.current_version['feature_names']
        
        # 检查特征名称一致性
        names_match = (current_names == expected_names)
        
        # 检查签名一致性
        signature_match = (current_signature == self.current_version['signature'])
        
        # 严格模式：检查特征数量
        n_features_match = (len(current_names) == self.current_version['n_features'])
        
        # 数据检查
        data_hash = hashlib.md5(df['period'].values.tobytes()).hexdigest()[:16]
        data_match = (data_hash == self.current_version.get('data_hash'))
        
        # 综合判断
        if strict:
            valid = names_match and signature_match and n_features_match
        else:
            valid = names_match and n_features_match
        
        result = {
            'valid': valid,
            'has_version': True,
            'signature_match': signature_match,
            'names_match': names_match,
            'n_features_match': n_features_match,
            'data_match': data_match,
            'current_signature': current_signature[:8],
            'expected_signature': self.current_version['signature'][:8],
            'current_n_features': len(current_names),
            'expected_n_features': self.current_version['n_features'],
            'message': self._generate_validation_message(names_match, n_features_match, signature_match)
        }
        
        if not valid:
            logger.warning(f"特征版本验证失败: {result['message']}")
            logger.warning(f"  当前特征: {len(current_names)}个, 签名={current_signature[:8]}")
            logger.warning(f"  期望特征: {self.current_version['n_features']}个, 签名={self.current_version['signature'][:8]}")
            
            # 显示差异
            if not names_match:
                added = set(current_names) - set(expected_names)
                removed = set(expected_names) - set(current_names)
                if added:
                    logger.warning(f"  新增特征: {list(added)[:5]}...")
                if removed:
                    logger.warning(f"  移除特征: {list(removed)[:5]}...")
        
        return result
    
    def _generate_validation_message(self, names_match: bool, n_match: bool, sig_match: bool) -> str:
        """生成验证消息"""
        if names_match and n_match and sig_match:
            return "特征版本完全一致"
        elif names_match and n_match and not sig_match:
            return "特征名称和数量一致，但统计信息有变化（可能是数据更新）"
        elif names_match and not n_match:
            return "特征名称一致，但数量不匹配"
        elif not names_match:
            return "特征名称不一致，请检查特征工程配置"
        else:
            return "特征版本验证失败"
    
    def detect_drift(self, df: pd.DataFrame, feature_cols: List[str],
                    threshold: float = 0.2) -> Dict[str, Any]:
        """
        检测特征漂移
        
        Args:
            df: 当前特征数据
            feature_cols: 特征列名列表
            threshold: 漂移阈值（PSI阈值）
            
        Returns:
            漂移检测结果
        """
        if self.current_version is None:
            return {'has_drift': False, 'message': '无历史版本'}
        
        # 获取共同的特征列
        current_features = [c for c in feature_cols if c not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        expected_features = set(self.current_version['feature_names'])
        common_features = [f for f in current_features if f in expected_features]
        
        if not common_features:
            return {
                'has_drift': True,
                'message': '没有共同特征，无法检测漂移',
                'drift_score': 1.0
            }
        
        # 计算PSI（Population Stability Index）
        psi_values = {}
        for col in common_features[:50]:  # 只检查前50个特征
            if col in df.columns and self.current_version['metadata'].get(f'{col}_dist'):
                current_dist = df[col].dropna()
                expected_dist = self.current_version['metadata'].get(f'{col}_dist', {})
                
                if expected_dist and len(current_dist) > 0:
                    psi = self._calculate_psi(current_dist, expected_dist)
                    psi_values[col] = psi
        
        # 计算平均PSI
        avg_psi = np.mean(list(psi_values.values())) if psi_values else 0.0
        
        # 找出漂移最大的特征
        max_drift_features = sorted(psi_values.items(), key=lambda x: x[1], reverse=True)[:5]
        
        result = {
            'has_drift': avg_psi > threshold,
            'avg_psi': float(avg_psi),
            'threshold': threshold,
            'n_features_checked': len(psi_values),
            'max_drift_features': [(f, float(v)) for f, v in max_drift_features],
            'message': f"平均PSI={avg_psi:.4f}, 阈值={threshold}, {'存在漂移' if avg_psi > threshold else '无显著漂移'}"
        }
        
        if result['has_drift']:
            logger.warning(f"检测到特征漂移: {result['message']}")
            logger.warning(f"  漂移最大的特征: {max_drift_features}")
        
        return result
    
    def _calculate_psi(self, current: pd.Series, expected: Dict) -> float:
        """
        计算PSI (Population Stability Index)
        """
        try:
            # 计算分位数
            bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
            current_pcts = np.histogram(current, bins=bins)[0] / len(current)
            
            expected_pcts = np.array([
                expected.get(f'bin_{i}', 0.1) for i in range(10)
            ])
            
            # 避免除零
            current_pcts = np.where(current_pcts == 0, 0.0001, current_pcts)
            expected_pcts = np.where(expected_pcts == 0, 0.0001, expected_pcts)
            
            # 计算PSI
            psi = np.sum((current_pcts - expected_pcts) * np.log(current_pcts / expected_pcts))
            return float(psi)
        except Exception:
            return 0.0
    
    def save_feature_distribution(self, df: pd.DataFrame, feature_cols: List[str]):
        """
        保存特征分布信息（用于漂移检测）
        """
        features = [c for c in feature_cols if c not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
        
        dist_info = {}
        for col in features[:50]:  # 只保存前50个特征
            if col in df.columns:
                current = df[col].dropna()
                if len(current) > 0:
                    bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
                    pcts = np.histogram(current, bins=bins)[0] / len(current)
                    dist_info[col] = {f'bin_{i}': float(p) for i, p in enumerate(pcts)}
        
        if self.current_version:
            self.current_version['metadata'].update(dist_info)
            self._save_version()
    
    def get_latest_version(self) -> Optional[Dict[str, Any]]:
        """获取最新版本信息"""
        return self.current_version
    
    def get_version_summary(self) -> str:
        """获取版本摘要"""
        if not self.version_history:
            return "没有特征版本历史"
        
        lines = ["=== 特征版本摘要 ==="]
        for v in self.version_history[-5:]:  # 只显示最近5个
            lines.append(
                f"v{v['version_id']} | {v['timestamp'][:19]} | "
                f"签名={v['signature'][:8]} | 特征数={v['n_features']}"
            )
        
        return '\n'.join(lines)


# 全局单例
_global_controller: Optional[FeatureVersionController] = None


def get_feature_version_controller() -> FeatureVersionController:
    """获取全局特征版本控制器"""
    global _global_controller
    if _global_controller is None:
        _global_controller = FeatureVersionController()
    return _global_controller
