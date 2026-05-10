#!/usr/bin/env python3
"""
PL5 依赖安装脚本
用于安装项目所需的所有依赖
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志文件
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'deploy.log')


class DependencyInstaller:
    """依赖安装器"""

    def __init__(self):
        self.install_results: Dict[str, Dict] = {}
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

    def upgrade_pip(self) -> bool:
        """升级pip"""
        self.log("升级pip...")
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                self.log("✓ pip升级成功")
                self.install_results['pip_upgrade'] = {'status': 'PASS'}
                return True
            else:
                error_msg = f"✗ pip升级失败: {result.stderr}"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                self.install_results['pip_upgrade'] = {'status': 'FAIL', 'error': result.stderr}
                return False
        except Exception as e:
            error_msg = f"✗ pip升级失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def install_requirements(self, requirements_file: str = 'requirements.txt') -> bool:
        """安装requirements.txt中的依赖"""
        req_path = os.path.join(PROJECT_ROOT, requirements_file)

        if not os.path.exists(req_path):
            error_msg = f"✗ 依赖文件不存在: {req_path}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

        self.log(f"安装依赖: {requirements_file}...")

        try:
            # 先解析依赖文件
            with open(req_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            packages = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    packages.append(line)

            self.log(f"发现 {len(packages)} 个依赖包")

            # 安装依赖
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', req_path],
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                self.log(f"✓ 依赖安装成功 ({len(packages)} 个包)")
                self.install_results['requirements'] = {
                    'status': 'PASS',
                    'packages_count': len(packages),
                    'packages': packages
                }
                return True
            else:
                error_msg = f"✗ 依赖安装失败: {result.stderr}"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                self.install_results['requirements'] = {
                    'status': 'FAIL',
                    'error': result.stderr
                }
                return False

        except subprocess.TimeoutExpired:
            error_msg = "✗ 依赖安装超时"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"✗ 依赖安装失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def install_optional_dependencies(self) -> bool:
        """安装可选依赖"""
        self.log("安装可选依赖...")

        optional_packages = {
            'psutil': '系统监控',
            'cryptography': '加密功能',
            'httpx': 'HTTP客户端',
            'aiofiles': '异步文件操作',
        }

        installed = []
        failed = []

        for package, description in optional_packages.items():
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', package],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    self.log(f"✓ {package} ({description}) 安装成功")
                    installed.append(package)
                else:
                    self.log(f"⚠ {package} ({description}) 安装失败: {result.stderr}", 'WARNING')
                    failed.append(package)
            except Exception as e:
                self.log(f"⚠ {package} ({description}) 安装失败: {e}", 'WARNING')
                failed.append(package)

        self.install_results['optional'] = {
            'status': 'PASS' if installed else 'WARNING',
            'installed': installed,
            'failed': failed
        }

        return True

    def verify_installation(self) -> bool:
        """验证安装"""
        self.log("验证依赖安装...")

        # 核心依赖列表
        core_packages = [
            'fastapi',
            'uvicorn',
            'numpy',
            'pandas',
            'sklearn',
            'pytest',
        ]

        missing = []
        installed = []

        for package in core_packages:
            try:
                __import__(package)
                installed.append(package)
            except ImportError:
                missing.append(package)

        if missing:
            error_msg = f"✗ 以下依赖未正确安装: {', '.join(missing)}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.install_results['verification'] = {
                'status': 'FAIL',
                'missing': missing,
                'installed': installed
            }
            return False
        else:
            self.log(f"✓ 所有核心依赖已正确安装 ({len(installed)} 个包)")
            self.install_results['verification'] = {
                'status': 'PASS',
                'installed': installed
            }
            return True

    def install_windows_specific(self) -> bool:
        """安装Windows特定依赖"""
        if sys.platform != 'win32':
            self.log("非Windows系统，跳过Windows特定依赖")
            return True

        self.log("安装Windows特定依赖...")

        windows_packages = {
            'pywin32': 'Windows API访问',
            'wmi': 'Windows管理规范',
        }

        installed = []
        failed = []

        for package, description in windows_packages.items():
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', package],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    self.log(f"✓ {package} ({description}) 安装成功")
                    installed.append(package)
                else:
                    self.log(f"⚠ {package} ({description}) 安装失败: {result.stderr}", 'WARNING')
                    failed.append(package)
            except Exception as e:
                self.log(f"⚠ {package} ({description}) 安装失败: {e}", 'WARNING')
                failed.append(package)

        self.install_results['windows'] = {
            'status': 'PASS',
            'installed': installed,
            'failed': failed
        }

        return True

    def create_virtual_env(self, venv_path: str = None) -> bool:
        """创建虚拟环境"""
        if '--no-venv' in sys.argv:
            self.log("跳过虚拟环境创建 (--no-venv)")
            return True

        if venv_path is None:
            venv_path = os.path.join(PROJECT_ROOT, 'venv')

        if os.path.exists(venv_path):
            self.log(f"虚拟环境已存在: {venv_path}")
            return True

        self.log(f"创建虚拟环境: {venv_path}...")

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'venv', venv_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                self.log("✓ 虚拟环境创建成功")
                self.install_results['virtual_env'] = {
                    'status': 'PASS',
                    'path': venv_path
                }
                return True
            else:
                warning_msg = f"⚠ 虚拟环境创建失败: {result.stderr}"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                self.install_results['virtual_env'] = {
                    'status': 'WARNING',
                    'error': result.stderr
                }
                return True  # 虚拟环境是可选的
        except Exception as e:
            warning_msg = f"⚠ 虚拟环境创建失败: {e}"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            return True

    def run_all_installations(self) -> Tuple[bool, Dict]:
        """运行所有安装步骤"""
        self.log("=" * 50)
        self.log("开始安装依赖")
        self.log("=" * 50)

        steps = [
            ('升级pip', self.upgrade_pip),
            ('安装requirements', self.install_requirements),
            ('安装Windows特定依赖', self.install_windows_specific),
            ('安装可选依赖', self.install_optional_dependencies),
            ('验证安装', self.verify_installation),
        ]

        all_passed = True
        for name, step_func in steps:
            try:
                if not step_func():
                    all_passed = False
                    if name in ['安装requirements', '验证安装']:
                        break  # 关键步骤失败，停止安装
            except Exception as e:
                self.log(f"步骤 {name} 时发生错误: {e}", 'ERROR')
                all_passed = False
                if name in ['安装requirements', '验证安装']:
                    break

        self.log("=" * 50)
        if all_passed:
            self.log("✓ 所有依赖安装成功")
        else:
            self.log(f"✗ 依赖安装失败: {len(self.errors)} 个错误")
        self.log("=" * 50)

        return all_passed, {
            'success': all_passed,
            'errors': self.errors,
            'warnings': self.warnings,
            'results': self.install_results
        }


def main():
    """主函数"""
    installer = DependencyInstaller()
    success, results = installer.run_all_installations()

    # 输出JSON格式的结果
    if '--json' in sys.argv:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
