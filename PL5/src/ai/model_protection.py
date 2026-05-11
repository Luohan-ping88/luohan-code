"""模型保护模块
提供模型文件的访问控制和完整性校验功能
"""

import os
import hashlib
import hmac
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ModelProtection:
    """模型保护管理器"""

    def __init__(self, models_dir: str = "models", secret_key: str = None):
        """初始化模型保护管理器

        Args:
            models_dir: 模型文件目录
            secret_key: 用于签名的密钥
        """
        self.models_dir = Path(models_dir)
        self.secret_key = secret_key or os.getenv("MODEL_SECRET_KEY", "default-model-secret-key-change-in-production")
        self.allowed_users = {"admin", "user"}

        # 确保目录存在并设置正确权限
        self._setup_directory()

    def _setup_directory(self):
        """设置模型目录权限"""
        if not self.models_dir.exists():
            self.models_dir.mkdir(parents=True, exist_ok=True)

        # 设置目录权限 (Linux/macOS)
        if os.name != "nt":
            try:
                os.chmod(self.models_dir, 0o700)  # 只有所有者可读写执行
            except Exception as e:
                logger.warning(f"Failed to set directory permissions: {e}")

    def _generate_signature(self, file_path: Path) -> str:
        """生成文件签名

        Args:
            file_path: 文件路径

        Returns:
            签名字符串
        """
        if not file_path.exists():
            return ""

        # 读取文件内容
        with open(file_path, "rb") as f:
            content = f.read()

        # 计算HMAC签名
        signature = hmac.new(self.secret_key.encode(), content, hashlib.sha256).hexdigest()

        return signature

    def _get_signature_file(self, model_file: Path) -> Path:
        """获取签名文件路径"""
        return model_file.with_suffix(model_file.suffix + ".sig")

    def sign_model(self, model_file: str) -> bool:
        """为模型文件生成签名

        Args:
            model_file: 模型文件路径

        Returns:
            是否成功
        """
        model_path = self.models_dir / model_file

        if not model_path.exists():
            logger.error(f"Model file not found: {model_file}")
            return False

        # 生成签名
        signature = self._generate_signature(model_path)

        # 保存签名到文件
        sig_file = self._get_signature_file(model_path)
        with open(sig_file, "w") as f:
            f.write(signature)

        # 设置文件权限
        if os.name != "nt":
            try:
                os.chmod(sig_file, 0o600)  # 只有所有者可读
            except Exception as e:
                logger.warning(f"Failed to set signature file permissions: {e}")

        logger.info(f"Model signed: {model_file}")
        return True

    def verify_model(self, model_file: str) -> bool:
        """验证模型文件的完整性

        Args:
            model_file: 模型文件路径

        Returns:
            是否验证通过
        """
        model_path = self.models_dir / model_file
        sig_file = self._get_signature_file(model_path)

        if not model_path.exists():
            logger.error(f"Model file not found: {model_file}")
            return False

        if not sig_file.exists():
            logger.warning(f"Signature file not found for: {model_file}")
            return False

        # 读取存储的签名
        with open(sig_file, "r") as f:
            stored_signature = f.read().strip()

        # 计算当前签名
        current_signature = self._generate_signature(model_path)

        # 比较签名
        if stored_signature != current_signature:
            logger.error(f"Model integrity check failed for: {model_file}")
            return False

        return True

    def has_access(self, user_role: str) -> bool:
        """检查用户是否有权限访问模型

        Args:
            user_role: 用户角色

        Returns:
            是否有权限
        """
        return user_role in self.allowed_users

    def list_models(self) -> list:
        """列出所有模型文件"""
        models = []

        if not self.models_dir.exists():
            return models

        for item in self.models_dir.iterdir():
            if item.is_file() and not item.suffix == ".sig":
                # 检查是否有签名文件
                sig_file = self._get_signature_file(item)
                has_signature = sig_file.exists()

                models.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "size_bytes": item.stat().st_size,
                        "has_signature": has_signature,
                        "last_modified": item.stat().st_mtime,
                    }
                )

        return models

    def validate_and_load_model(self, model_file: str, user_role: str) -> Dict[str, Any]:
        """验证并加载模型（安全检查）

        Args:
            model_file: 模型文件路径
            user_role: 用户角色

        Returns:
            检查结果
        """
        result = {"success": False, "message": "", "model_file": model_file}

        # 检查权限
        if not self.has_access(user_role):
            result["message"] = "Permission denied"
            return result

        # 验证完整性
        if not self.verify_model(model_file):
            result["message"] = "Model integrity check failed"
            return result

        # 检查文件路径安全（防止路径遍历攻击）
        model_path = self.models_dir / model_file
        if not str(model_path).startswith(str(self.models_dir)):
            result["message"] = "Path traversal detected"
            return result

        result["success"] = True
        result["message"] = "Validation passed"
        result["model_path"] = str(model_path)

        return result

    def get_model_info(self, model_file: str) -> Optional[Dict[str, Any]]:
        """获取模型文件信息

        Args:
            model_file: 模型文件路径

        Returns:
            模型信息
        """
        model_path = self.models_dir / model_file

        if not model_path.exists():
            return None

        sig_file = self._get_signature_file(model_path)

        return {
            "name": model_file,
            "path": str(model_path),
            "size_bytes": model_path.stat().st_size,
            "size_human": self._format_size(model_path.stat().st_size),
            "has_signature": sig_file.exists(),
            "last_modified": model_path.stat().st_mtime,
            "signature_valid": self.verify_model(model_file) if sig_file.exists() else None,
        }

    def _format_size(self, bytes_size: int) -> str:
        """格式化文件大小"""
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.2f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.2f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"


# 全局模型保护实例
_model_protection = ModelProtection()


def get_model_protection() -> ModelProtection:
    """获取全局模型保护管理器"""
    return _model_protection
