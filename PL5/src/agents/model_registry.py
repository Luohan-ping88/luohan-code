"""
模型版本管理 - 模型注册、版本控制、A/B测试支持
"""

import json
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
import pickle

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """模型版本信息"""
    version_id: str
    model_name: str
    created_at: datetime
    description: str
    metrics: Dict[str, float]
    parameters: Dict[str, Any]
    file_hash: str
    file_path: Path
    parent_version: Optional[str] = None
    tags: List[str] = None
    status: str = "active"  # active, archived, deprecated
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'version_id': self.version_id,
            'model_name': self.model_name,
            'created_at': self.created_at.isoformat(),
            'description': self.description,
            'metrics': self.metrics,
            'parameters': self.parameters,
            'file_hash': self.file_hash,
            'file_path': str(self.file_path),
            'parent_version': self.parent_version,
            'tags': self.tags,
            'status': self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelVersion':
        return cls(
            version_id=data['version_id'],
            model_name=data['model_name'],
            created_at=datetime.fromisoformat(data['created_at']),
            description=data['description'],
            metrics=data['metrics'],
            parameters=data['parameters'],
            file_hash=data['file_hash'],
            file_path=Path(data['file_path']),
            parent_version=data.get('parent_version'),
            tags=data.get('tags', []),
            status=data.get('status', 'active')
        )


class ModelRegistry:
    """模型注册中心"""
    
    def __init__(self, registry_path: Path = None):
        if registry_path is None:
            registry_path = Path(__file__).parent.parent / 'models' / 'registry'
        
        self.registry_path = registry_path
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        self.versions_db_path = self.registry_path / 'versions_db.json'
        self.models_dir = self.registry_path / 'versions'
        self.models_dir.mkdir(exist_ok=True)
        
        self._versions: Dict[str, List[ModelVersion]] = {}
        self._load_registry()
    
    def _load_registry(self):
        """加载注册表"""
        if self.versions_db_path.exists():
            with open(self.versions_db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for model_name, versions_data in data.items():
                self._versions[model_name] = [
                    ModelVersion.from_dict(v) for v in versions_data
                ]
            
            logger.info(f"[Registry] 已加载 {len(self._versions)} 个模型的注册信息")
    
    def _save_registry(self):
        """保存注册表"""
        data = {
            model_name: [v.to_dict() for v in versions]
            for model_name, versions in self._versions.items()
        }
        
        with open(self.versions_db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _calculate_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]
    
    def register_model(self, model_name: str, model_file: Path,
                       description: str = "", metrics: Dict[str, float] = None,
                       parameters: Dict[str, Any] = None,
                       parent_version: str = None,
                       tags: List[str] = None) -> ModelVersion:
        """注册新模型版本"""
        
        # 生成版本ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_id = f"{model_name}_v{timestamp}"
        
        # 计算文件哈希
        file_hash = self._calculate_hash(model_file)
        
        # 复制模型文件到注册目录
        version_dir = self.models_dir / model_name
        version_dir.mkdir(exist_ok=True)
        
        dest_path = version_dir / f"{version_id}.pkl"
        shutil.copy2(model_file, dest_path)
        
        # 创建版本记录
        version = ModelVersion(
            version_id=version_id,
            model_name=model_name,
            created_at=datetime.now(),
            description=description,
            metrics=metrics or {},
            parameters=parameters or {},
            file_hash=file_hash,
            file_path=dest_path,
            parent_version=parent_version,
            tags=tags or []
        )
        
        # 添加到注册表
        if model_name not in self._versions:
            self._versions[model_name] = []
        
        self._versions[model_name].append(version)
        self._save_registry()
        
        logger.info(f"[Registry] 模型 {model_name} 版本 {version_id} 已注册")
        
        return version
    
    def get_version(self, model_name: str, version_id: str) -> Optional[ModelVersion]:
        """获取特定版本"""
        if model_name not in self._versions:
            return None
        
        for version in self._versions[model_name]:
            if version.version_id == version_id:
                return version
        
        return None
    
    def get_latest_version(self, model_name: str, status: str = "active") -> Optional[ModelVersion]:
        """获取最新版本"""
        if model_name not in self._versions:
            return None
        
        versions = [v for v in self._versions[model_name] if v.status == status]
        if not versions:
            return None
        
        return max(versions, key=lambda v: v.created_at)
    
    def get_all_versions(self, model_name: str) -> List[ModelVersion]:
        """获取所有版本"""
        return self._versions.get(model_name, [])
    
    def list_models(self) -> List[str]:
        """列出所有模型"""
        return list(self._versions.keys())
    
    def update_version_status(self, model_name: str, version_id: str, status: str):
        """更新版本状态"""
        version = self.get_version(model_name, version_id)
        if version:
            version.status = status
            self._save_registry()
            logger.info(f"[Registry] 模型 {model_name} 版本 {version_id} 状态更新为 {status}")
    
    def add_tags(self, model_name: str, version_id: str, tags: List[str]):
        """添加标签"""
        version = self.get_version(model_name, version_id)
        if version:
            version.tags.extend(tags)
            version.tags = list(set(version.tags))  # 去重
            self._save_registry()
    
    def compare_versions(self, model_name: str, version_id1: str, 
                        version_id2: str) -> Dict[str, Any]:
        """比较两个版本"""
        v1 = self.get_version(model_name, version_id1)
        v2 = self.get_version(model_name, version_id2)
        
        if not v1 or not v2:
            return {'error': '版本不存在'}
        
        comparison = {
            'version1': v1.to_dict(),
            'version2': v2.to_dict(),
            'metric_diff': {},
            'parameter_diff': {}
        }
        
        # 比较指标
        all_metrics = set(v1.metrics.keys()) | set(v2.metrics.keys())
        for metric in all_metrics:
            m1 = v1.metrics.get(metric, 0)
            m2 = v2.metrics.get(metric, 0)
            comparison['metric_diff'][metric] = {
                'v1': m1,
                'v2': m2,
                'diff': m2 - m1,
                'improvement': (m2 - m1) / m1 if m1 != 0 else 0
            }
        
        return comparison
    
    def get_version_lineage(self, model_name: str, version_id: str) -> List[ModelVersion]:
        """获取版本血缘关系"""
        lineage = []
        current_id = version_id
        
        while current_id:
            version = self.get_version(model_name, current_id)
            if not version:
                break
            
            lineage.append(version)
            current_id = version.parent_version
        
        return lineage
    
    def load_model(self, model_name: str, version_id: str = None) -> Any:
        """加载模型"""
        if version_id is None:
            version = self.get_latest_version(model_name)
        else:
            version = self.get_version(model_name, version_id)
        
        if not version:
            raise ValueError(f"模型 {model_name} 版本不存在")
        
        with open(version.file_path, 'rb') as f:
            model = pickle.load(f)
        
        logger.info(f"[Registry] 已加载模型 {model_name} 版本 {version.version_id}")
        
        return model
    
    def delete_version(self, model_name: str, version_id: str):
        """删除版本"""
        version = self.get_version(model_name, version_id)
        if version:
            # 删除文件
            if version.file_path.exists():
                version.file_path.unlink()
            
            # 从注册表移除
            self._versions[model_name] = [
                v for v in self._versions[model_name] 
                if v.version_id != version_id
            ]
            
            self._save_registry()
            logger.info(f"[Registry] 模型 {model_name} 版本 {version_id} 已删除")
    
    def get_best_version(self, model_name: str, metric: str = "accuracy") -> Optional[ModelVersion]:
        """获取最佳版本（基于指标）"""
        if model_name not in self._versions:
            return None
        
        active_versions = [v for v in self._versions[model_name] if v.status == "active"]
        if not active_versions:
            return None
        
        return max(active_versions, key=lambda v: v.metrics.get(metric, 0))
    
    def export_registry(self, filepath: Path):
        """导出注册表"""
        data = {
            'export_time': datetime.now().isoformat(),
            'models': {}
        }
        
        for model_name, versions in self._versions.items():
            data['models'][model_name] = {
                'version_count': len(versions),
                'versions': [v.to_dict() for v in versions]
            }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[Registry] 注册表已导出: {filepath}")


class ModelDeployment:
    """模型部署管理"""
    
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.deployments: Dict[str, Dict[str, Any]] = {}
        self.deployment_file = registry.registry_path / 'deployments.json'
        self._load_deployments()
    
    def _load_deployments(self):
        """加载部署信息"""
        if self.deployment_file.exists():
            with open(self.deployment_file, 'r', encoding='utf-8') as f:
                self.deployments = json.load(f)
    
    def _save_deployments(self):
        """保存部署信息"""
        with open(self.deployment_file, 'w', encoding='utf-8') as f:
            json.dump(self.deployments, f, ensure_ascii=False, indent=2)
    
    def deploy(self, model_name: str, version_id: str, 
               environment: str = "production", traffic_percentage: float = 100.0):
        """部署模型"""
        deployment_id = f"{model_name}_{environment}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.deployments[deployment_id] = {
            'model_name': model_name,
            'version_id': version_id,
            'environment': environment,
            'traffic_percentage': traffic_percentage,
            'deployed_at': datetime.now().isoformat(),
            'status': 'active'
        }
        
        self._save_deployments()
        
        logger.info(f"[Deployment] 模型 {model_name} 版本 {version_id} 已部署到 {environment}")
        
        return deployment_id
    
    def setup_ab_test(self, model_name: str, version_a: str, version_b: str,
                     traffic_split: Tuple[float, float] = (50.0, 50.0)):
        """设置A/B测试"""
        test_id = f"ab_test_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.deployments[test_id] = {
            'type': 'ab_test',
            'model_name': model_name,
            'version_a': version_a,
            'version_b': version_b,
            'traffic_split': traffic_split,
            'created_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        self._save_deployments()
        
        logger.info(f"[Deployment] A/B测试已设置: {test_id}")
        
        return test_id
    
    def get_active_deployments(self, environment: str = None) -> List[Dict[str, Any]]:
        """获取活跃部署"""
        deployments = []
        
        for dep_id, dep in self.deployments.items():
            if dep.get('status') == 'active':
                if environment is None or dep.get('environment') == environment:
                    dep['deployment_id'] = dep_id
                    deployments.append(dep)
        
        return deployments
    
    def rollback(self, deployment_id: str):
        """回滚部署"""
        if deployment_id in self.deployments:
            self.deployments[deployment_id]['status'] = 'rolled_back'
            self.deployments[deployment_id]['rolled_back_at'] = datetime.now().isoformat()
            self._save_deployments()
            
            logger.info(f"[Deployment] 部署 {deployment_id} 已回滚")
