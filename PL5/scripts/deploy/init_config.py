#!/usr/bin/env python3
"""
PL5 配置初始化脚本
用于创建和初始化配置文件
"""

import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志文件
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'deploy.log')

# 默认配置
DEFAULT_CONFIGS = {
    'config/config.json': {
        "system": {
            "name": "排列五高阶数理分析预测系统",
            "version": "5.3",
            "debug": False
        },
        "scheduler": {
            "data_fetch_time": "00:00",
            "evaluation_time": "00:30",
            "optimization_start": "01:00",
            "training_start": "02:00",
            "training_deadline": "17:00",
            "email_send_time": "17:30",
            "enabled": True
        },
        "prediction": {
            "top_k": 8,
            "confidence_threshold": 0.6,
            "generate_report": True
        },
        "model": {
            "hmm": {
                "n_components": 4,
                "covariance_type": "full",
                "n_iter": 100
            },
            "ensemble": {
                "n_models": 5,
                "min_weight": 0.05
            }
        },
        "data": {
            "source_url": "http://data.17500.cn/pl5_asc.txt",
            "max_records": 5000,
            "update_on_start": True
        },
        "cpp_core": {
            "enabled": True,
            "fallback_to_python": True
        }
    },
    'config/model_config.yaml': '''# 模型配置文件
model:
  name: "pl5_predictor"
  version: "v10"
  type: "ensemble"

training:
  batch_size: 32
  epochs: 100
  learning_rate: 0.001
  early_stopping_patience: 10

features:
  use_statistical: true
  use_sequence: true
  use_temporal: true

evaluation:
  metrics:
    - accuracy
    - precision
    - recall
    - f1
  cross_validation_folds: 5
''',
    'config/email_config.example.json': {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "sender_email": "your_email@example.com",
        "sender_password": "your_password",
        "recipients": ["recipient@example.com"],
        "enabled": False
    },
    'config/scheduler_config_v8.json': {
        "auto_start": True,
        "interval_minutes": 60,
        "retry_on_failure": True,
        "max_retries": 3
    },
    'config/guardian_config.json': {
        "enabled": True,
        "check_interval_seconds": 60,
        "restart_on_failure": True,
        "max_restart_attempts": 5
    },
    '.env.example': '''# PL5 环境变量配置
# 复制此文件为 .env 并填写实际值

# 调试模式
DEBUG=false

# API配置
API_HOST=0.0.0.0
API_PORT=8000

# 数据库配置（如使用）
# DATABASE_URL=sqlite:///data/pl5.db

# 邮件配置
EMAIL_ENABLED=false
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
EMAIL_USER=your_email@example.com
EMAIL_PASS=your_password

# 日志级别
LOG_LEVEL=INFO

# 模型配置
MODEL_PATH=models/
DATA_PATH=data/
'''
}


class ConfigInitializer:
    """配置初始化器"""

    def __init__(self):
        self.init_results: Dict[str, Dict] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        """确保日志目录存在"""
        log_dir = os.path.join(PROJECT_ROOT, 'logs')
        os.makedirs(log_dir, exist_ok=True)

    def log(self, message: str, level: str = 'INFO'):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

    def ensure_directories(self) -> bool:
        """确保必要的目录存在"""
        self.log("创建必要的目录...")

        directories = [
            'config',
            'data/raw',
            'data/processed',
            'logs',
            'models',
            'results',
            'backups',
            'scripts/deploy',
            'docs',
        ]

        created = []
        failed = []

        for dir_path in directories:
            full_path = os.path.join(PROJECT_ROOT, dir_path)
            try:
                os.makedirs(full_path, exist_ok=True)
                created.append(dir_path)
            except Exception as e:
                failed.append((dir_path, str(e)))

        if failed:
            error_msg = f"✗ 部分目录创建失败: {failed}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.init_results['directories'] = {
                'status': 'PARTIAL',
                'created': created,
                'failed': failed
            }
            return len(created) > 0
        else:
            self.log(f"✓ 所有目录创建成功 ({len(created)} 个)")
            self.init_results['directories'] = {
                'status': 'PASS',
                'created': created
            }
            return True

    def create_config_file(self, rel_path: str, content) -> bool:
        """创建单个配置文件"""
        full_path = os.path.join(PROJECT_ROOT, rel_path)

        # 如果文件已存在，备份它
        if os.path.exists(full_path):
            backup_path = f"{full_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                shutil.copy2(full_path, backup_path)
                self.log(f"  已备份现有配置: {rel_path}")
            except Exception as e:
                self.log(f"  警告: 备份失败 {rel_path}: {e}", 'WARNING')

        # 创建目录
        dir_path = os.path.dirname(full_path)
        os.makedirs(dir_path, exist_ok=True)

        try:
            if isinstance(content, dict):
                with open(full_path, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2, ensure_ascii=False)
            else:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            return True
        except Exception as e:
            self.log(f"  创建失败 {rel_path}: {e}", 'ERROR')
            return False

    def init_configs(self) -> bool:
        """初始化所有配置文件"""
        self.log("初始化配置文件...")

        created = []
        failed = []
        skipped = []

        for rel_path, content in DEFAULT_CONFIGS.items():
            full_path = os.path.join(PROJECT_ROOT, rel_path)

            # 检查文件是否已存在（且不是example文件）
            if os.path.exists(full_path) and not rel_path.endswith('.example'):
                # 对于非example文件，如果存在则跳过
                if 'example' not in rel_path and '.env.example' not in rel_path:
                    skipped.append(rel_path)
                    continue

            if self.create_config_file(rel_path, content):
                created.append(rel_path)
            else:
                failed.append(rel_path)

        if failed:
            error_msg = f"✗ 部分配置文件创建失败: {failed}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.init_results['configs'] = {
                'status': 'PARTIAL' if created else 'FAIL',
                'created': created,
                'failed': failed,
                'skipped': skipped
            }
            return len(created) > 0
        else:
            self.log(f"✓ 配置文件初始化完成 ({len(created)} 个创建, {len(skipped)} 个跳过)")
            self.init_results['configs'] = {
                'status': 'PASS',
                'created': created,
                'skipped': skipped
            }
            return True

    def init_env_file(self) -> bool:
        """初始化.env文件"""
        self.log("初始化环境变量文件...")

        env_path = os.path.join(PROJECT_ROOT, '.env')
        env_example_path = os.path.join(PROJECT_ROOT, '.env.example')

        if os.path.exists(env_path):
            self.log("✓ .env 文件已存在，跳过创建")
            self.init_results['env_file'] = {
                'status': 'PASS',
                'action': 'skipped'
            }
            return True

        if os.path.exists(env_example_path):
            try:
                shutil.copy2(env_example_path, env_path)
                self.log("✓ .env 文件已从示例创建")
                self.log("  请编辑 .env 文件并填写实际配置值")
                self.init_results['env_file'] = {
                    'status': 'PASS',
                    'action': 'created_from_example'
                }
                return True
            except Exception as e:
                error_msg = f"✗ 创建 .env 文件失败: {e}"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                self.init_results['env_file'] = {
                    'status': 'FAIL',
                    'error': str(e)
                }
                return False
        else:
            # 创建默认.env文件
            if self.create_config_file('.env', DEFAULT_CONFIGS['.env.example']):
                self.log("✓ .env 文件已创建（默认配置）")
                self.log("  请编辑 .env 文件并填写实际配置值")
                self.init_results['env_file'] = {
                    'status': 'PASS',
                    'action': 'created_default'
                }
                return True
            else:
                return False

    def validate_configs(self) -> bool:
        """验证配置文件"""
        self.log("验证配置文件...")

        config_files = [
            'config/config.json',
            'config/scheduler_config_v8.json',
        ]

        valid = []
        invalid = []

        for config_file in config_files:
            full_path = os.path.join(PROJECT_ROOT, config_file)
            if not os.path.exists(full_path):
                invalid.append((config_file, '文件不存在'))
                continue

            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    json.load(f)
                valid.append(config_file)
            except json.JSONDecodeError as e:
                invalid.append((config_file, f'JSON解析错误: {e}'))
            except Exception as e:
                invalid.append((config_file, str(e)))

        if invalid:
            error_msg = f"✗ 部分配置文件无效: {invalid}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.init_results['validation'] = {
                'status': 'FAIL',
                'valid': valid,
                'invalid': invalid
            }
            return False
        else:
            self.log(f"✓ 所有配置文件验证通过 ({len(valid)} 个)")
            self.init_results['validation'] = {
                'status': 'PASS',
                'valid': valid
            }
            return True

    def set_permissions(self) -> bool:
        """设置文件权限（主要用于Unix系统）"""
        if sys.platform == 'win32':
            self.log("Windows系统，跳过权限设置")
            self.init_results['permissions'] = {'status': 'PASS', 'platform': 'windows'}
            return True

        self.log("设置文件权限...")

        try:
            # 设置脚本可执行权限
            script_dirs = [
                os.path.join(PROJECT_ROOT, 'scripts'),
            ]

            for script_dir in script_dirs:
                if os.path.exists(script_dir):
                    for root, dirs, files in os.walk(script_dir):
                        for file in files:
                            if file.endswith('.sh') or file.endswith('.py'):
                                file_path = os.path.join(root, file)
                                os.chmod(file_path, 0o755)

            self.log("✓ 文件权限设置完成")
            self.init_results['permissions'] = {'status': 'PASS'}
            return True
        except Exception as e:
            warning_msg = f"⚠ 权限设置失败: {e}"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            return True  # 权限设置失败不是致命错误

    def run_all_initializations(self) -> Tuple[bool, Dict]:
        """运行所有初始化步骤"""
        self.log("=" * 50)
        self.log("开始配置初始化")
        self.log("=" * 50)

        steps = [
            ('创建目录', self.ensure_directories),
            ('初始化配置', self.init_configs),
            ('初始化环境变量', self.init_env_file),
            ('验证配置', self.validate_configs),
            ('设置权限', self.set_permissions),
        ]

        all_passed = True
        for name, step_func in steps:
            try:
                if not step_func():
                    all_passed = False
            except Exception as e:
                self.log(f"步骤 {name} 时发生错误: {e}", 'ERROR')
                all_passed = False

        self.log("=" * 50)
        if all_passed:
            self.log("✓ 配置初始化完成")
        else:
            self.log(f"✗ 配置初始化失败: {len(self.errors)} 个错误")
        self.log("=" * 50)

        return all_passed, {
            'success': all_passed,
            'errors': self.errors,
            'warnings': self.warnings,
            'results': self.init_results
        }


def main():
    """主函数"""
    initializer = ConfigInitializer()
    success, results = initializer.run_all_initializations()

    # 输出JSON格式的结果
    if '--json' in sys.argv:
        import json
        print(json.dumps(results, indent=2, ensure_ascii=False))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
