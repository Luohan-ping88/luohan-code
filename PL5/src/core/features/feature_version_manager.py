#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
特征版本管理模块
确保训练和预测使用完全相同的特征集
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.core.config import MODELS_DIR, LOGS_DIR
from src.core.utils.logger import get_logger

logger = get_logger(__name__)


class FeatureVersionManager:
    """特征版本管理器"""

    def __init__(self):
        self.versions_dir = Path(MODELS_DIR) / "feature_versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        
        self.latest_link = self.versions_dir / "latest.json"
        self.history_file = self.versions_dir / "history.json"
        
        self.feature_config_file = Path(LOGS_DIR) / "best_feature_config.json"
        
        self._init_history()
    
    def _init_history(self):
        """初始化历史记录"""
        if not self.history_file.exists():
            self._save_history([])
    
    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_history(self, history: List[Dict]):
        """保存历史记录"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    
    def _compute_feature_hash(self, feature_cols: List[str]) -> str:
        """计算特征集的哈希值"""
        sorted_cols = sorted(feature_cols)
        cols_str = "|".join(sorted_cols)
        return hashlib.md5(cols_str.encode()).hexdigest()
    
    def save_feature_version(
        self,
        feature_cols: List[str],
        feature_config: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        保存特征版本
        
        Args:
            feature_cols: 特征列列表
            feature_config: 特征配置（可选）
            metadata: 元数据（可选）
            
        Returns:
            str: 版本ID
        """
        feature_hash = self._compute_feature_hash(feature_cols)
        version_id = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}_{feature_hash[:8]}"
        
        version_data = {
            "version_id": version_id,
            "timestamp": datetime.now().isoformat(),
            "feature_hash": feature_hash,
            "feature_count": len(feature_cols),
            "feature_cols": feature_cols,
            "feature_config": feature_config or {},
            "metadata": metadata or {}
        }
        
        # 保存版本文件
        version_file = self.versions_dir / f"{version_id}.json"
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2, ensure_ascii=False)
        
        # 更新最新链接
        try:
            if self.latest_link.exists():
                self.latest_link.unlink()
            self.latest_link.symlink_to(version_file.name)
        except:
            # Windows 可能不支持符号链接，直接复制
            import shutil
            shutil.copy(version_file, self.latest_link)
        
        # 更新历史记录
        history = self._load_history()
        history.insert(0, {
            "version_id": version_id,
            "timestamp": version_data["timestamp"],
            "feature_count": len(feature_cols),
            "feature_hash": feature_hash
        })
        # 只保留最近20个版本
        history = history[:20]
        self._save_history(history)
        
        logger.info(f"[特征版本] 已保存版本: {version_id} (特征数: {len(feature_cols)})")
        return version_id
    
    def load_feature_version(self, version_id: Optional[str] = None) -> Optional[Dict]:
        """
        加载特征版本
        
        Args:
            version_id: 版本ID（可选，不传则加载最新版本）
            
        Returns:
            Dict: 特征版本数据
        """
        if version_id:
            version_file = self.versions_dir / f"{version_id}.json"
        else:
            version_file = self.latest_link
        
        if not version_file.exists():
            logger.warning(f"[特征版本] 版本文件不存在: {version_file}")
            return None
        
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                version_data = json.load(f)
            logger.info(f"[特征版本] 已加载版本: {version_data.get('version_id', 'unknown')}")
            return version_data
        except Exception as e:
            logger.error(f"[特征版本] 加载版本失败: {e}")
            return None
    
    def get_latest_version_info(self) -> Optional[Dict]:
        """获取最新版本信息"""
        history = self._load_history()
        if history:
            return history[0]
        return None
    
    def check_feature_consistency(
        self,
        current_features: List[str],
        version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        检查特征一致性
        
        Args:
            current_features: 当前特征列表
            version_id: 要对比的版本ID（可选，不传则对比最新版本）
            
        Returns:
            Dict: 一致性检查结果
        """
        version_data = self.load_feature_version(version_id)
        
        if not version_data:
            return {
                "consistent": False,
                "reason": "没有可对比的特征版本",
                "action": "save_new_version"
            }
        
        saved_features = version_data.get("feature_cols", [])
        saved_hash = version_data.get("feature_hash", "")
        current_hash = self._compute_feature_hash(current_features)
        
        if saved_hash == current_hash:
            return {
                "consistent": True,
                "version_id": version_data.get("version_id"),
                "feature_count": len(current_features)
            }
        else:
            # 计算差异
            saved_set = set(saved_features)
            current_set = set(current_features)
            
            added = list(current_set - saved_set)
            removed = list(saved_set - current_set)
            
            return {
                "consistent": False,
                "reason": "特征集不匹配",
                "version_id": version_data.get("version_id"),
                "added_count": len(added),
                "removed_count": len(removed),
                "added_features": added[:10],  # 只显示前10个
                "removed_features": removed[:10],
                "action": "update_version" if len(added) + len(removed) < 10 else "save_new_version"
            }
    
    def list_versions(self, limit: int = 10) -> List[Dict]:
        """列出特征版本"""
        history = self._load_history()
        return history[:limit]


# 全局实例
_feature_manager: Optional[FeatureVersionManager] = None


def get_feature_version_manager() -> FeatureVersionManager:
    """获取特征版本管理器全局实例"""
    global _feature_manager
    if _feature_manager is None:
        _feature_manager = FeatureVersionManager()
    return _feature_manager
