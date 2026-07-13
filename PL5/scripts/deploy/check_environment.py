#!/usr/bin/env python3
"""
PL5 环境检查脚本
用于检查部署环境是否满足要求
"""

import os
import sys
import platform
import subprocess
import shutil
import socket
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志文件
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'deploy.log')

# 环境要求
REQUIREMENTS = {
    'python_version': (3, 10),
    'min_disk_space_gb': 5,
    'min_memory_gb': 4,
    'required_ports': [8000, 8080],
    'required_python_packages': [
        'fastapi',
        'uvicorn',
        'numpy',
        'pandas',
        'scikit-learn',
    ]
}


class EnvironmentChecker:
    """环境检查器"""

    def __init__(self):
        self.check_results: Dict[str, Dict] = {}
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

    def check_python_version(self) -> bool:
        """检查Python版本"""
        self.log("检查Python版本...")
        current_version = sys.version_info[:2]
        required_version = REQUIREMENTS['python_version']

        if current_version >= required_version:
            self.log(f"✓ Python版本: {sys.version.split()[0]}")
            self.check_results['python_version'] = {
                'status': 'PASS',
                'current': '.'.join(map(str, current_version)),
                'required': '.'.join(map(str, required_version))
            }
            return True
        else:
            error_msg = f"✗ Python版本过低: {'.'.join(map(str, current_version))}，需要 >= {'.'.join(map(str, required_version))}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.check_results['python_version'] = {
                'status': 'FAIL',
                'current': '.'.join(map(str, current_version)),
                'required': '.'.join(map(str, required_version))
            }
            return False

    def check_disk_space(self) -> bool:
        """检查磁盘空间"""
        self.log("检查磁盘空间...")
        try:
            if platform.system() == 'Windows':
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(PROJECT_ROOT),
                    ctypes.pointer(free_bytes),
                    ctypes.pointer(total_bytes),
                    None
                )
                free_gb = free_bytes.value / (1024**3)
                total_gb = total_bytes.value / (1024**3)
            else:
                stat = shutil.disk_usage(PROJECT_ROOT)
                free_gb = stat.free / (1024**3)
                total_gb = stat.total / (1024**3)

            required_gb = REQUIREMENTS['min_disk_space_gb']

            if free_gb >= required_gb:
                self.log(f"✓ 磁盘空间: {free_gb:.2f}GB 可用 / {total_gb:.2f}GB 总计")
                self.check_results['disk_space'] = {
                    'status': 'PASS',
                    'free_gb': round(free_gb, 2),
                    'total_gb': round(total_gb, 2),
                    'required_gb': required_gb
                }
                return True
            else:
                error_msg = f"✗ 磁盘空间不足: {free_gb:.2f}GB 可用，需要 >= {required_gb}GB"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                self.check_results['disk_space'] = {
                    'status': 'FAIL',
                    'free_gb': round(free_gb, 2),
                    'required_gb': required_gb
                }
                return False
        except Exception as e:
            error_msg = f"✗ 检查磁盘空间失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def check_memory(self) -> bool:
        """检查内存"""
        self.log("检查内存...")
        try:
            import psutil
            memory = psutil.virtual_memory()
            total_gb = memory.total / (1024**3)
            available_gb = memory.available / (1024**3)
            required_gb = REQUIREMENTS['min_memory_gb']

            if total_gb >= required_gb:
                self.log(f"✓ 内存: {total_gb:.2f}GB 总计，{available_gb:.2f}GB 可用")
                self.check_results['memory'] = {
                    'status': 'PASS',
                    'total_gb': round(total_gb, 2),
                    'available_gb': round(available_gb, 2),
                    'required_gb': required_gb
                }
                return True
            else:
                warning_msg = f"⚠ 内存较低: {total_gb:.2f}GB，建议 >= {required_gb}GB"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                self.check_results['memory'] = {
                    'status': 'WARNING',
                    'total_gb': round(total_gb, 2),
                    'required_gb': required_gb
                }
                return True
        except ImportError:
            warning_msg = "⚠ 无法检查内存: psutil 未安装"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            return True
        except Exception as e:
            error_msg = f"✗ 检查内存失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def check_network(self) -> bool:
        """检查网络连接"""
        self.log("检查网络连接...")
        try:
            # 检查外部网络连接
            test_hosts = [
                ('8.8.8.8', 53),      # Google DNS
                ('114.114.114.114', 53),  # 国内DNS
            ]

            connected = False
            for host, port in test_hosts:
                try:
                    socket.create_connection((host, port), timeout=3)
                    connected = True
                    break
                except:
                    continue

            if connected:
                self.log("✓ 网络连接正常")
                self.check_results['network'] = {'status': 'PASS'}
                return True
            else:
                warning_msg = "⚠ 无法连接外部网络"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                self.check_results['network'] = {'status': 'WARNING'}
                return True
        except Exception as e:
            error_msg = f"✗ 检查网络失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def check_ports(self) -> bool:
        """检查端口占用情况"""
        self.log("检查端口占用...")
        occupied_ports = []

        for port in REQUIREMENTS['required_ports']:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()

                if result == 0:
                    occupied_ports.append(port)
            except Exception as e:
                self.log(f"检查端口 {port} 时出错: {e}", 'WARNING')

        if occupied_ports:
            warning_msg = f"⚠ 以下端口已被占用: {', '.join(map(str, occupied_ports))}"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            self.check_results['ports'] = {
                'status': 'WARNING',
                'occupied_ports': occupied_ports
            }
        else:
            self.log("✓ 所有必需端口可用")
            self.check_results['ports'] = {'status': 'PASS'}

        return True

    def check_pip(self) -> bool:
        """检查pip是否可用"""
        self.log("检查pip...")
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.log(f"✓ pip: {result.stdout.strip()}")
                self.check_results['pip'] = {'status': 'PASS'}
                return True
            else:
                error_msg = "✗ pip 不可用"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                self.check_results['pip'] = {'status': 'FAIL'}
                return False
        except Exception as e:
            error_msg = f"✗ 检查pip失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def check_pyyaml(self) -> bool:
        """检查PyYAML是否安装（关键依赖，缺失会导致配置文件不生效）"""
        self.log("检查PyYAML...")
        try:
            import yaml
            version = getattr(yaml, '__version__', 'unknown')
            self.log(f"✓ PyYAML: {version}")
            self.check_results['pyyaml'] = {'status': 'PASS', 'version': version}
            return True
        except ImportError:
            error_msg = (
                "✗ PyYAML 未安装！配置文件 model_config.yaml 将无法加载，\n"
                "  系统将使用内置默认值，所有配置修改均不生效。\n"
                "  请执行: pip install PyYAML"
            )
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"✗ PyYAML 检查失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def check_git(self) -> bool:
        """检查Git是否可用"""
        self.log("检查Git...")
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.log(f"✓ Git: {result.stdout.strip()}")
                self.check_results['git'] = {'status': 'PASS'}
                return True
            else:
                warning_msg = "⚠ Git 不可用（可选）"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                self.check_results['git'] = {'status': 'WARNING'}
                return True
        except Exception as e:
            warning_msg = f"⚠ Git 检查失败: {e}（可选）"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            return True

    def check_project_structure(self) -> bool:
        """检查项目结构"""
        self.log("检查项目结构...")
        required_dirs = [
            'src',
            'config',
            'data',
            'logs',
            'models',
        ]
        required_files = [
            'requirements.txt',
            'main.py',
        ]

        missing_dirs = []
        missing_files = []

        for dir_name in required_dirs:
            dir_path = os.path.join(PROJECT_ROOT, dir_name)
            if not os.path.isdir(dir_path):
                missing_dirs.append(dir_name)

        for file_name in required_files:
            file_path = os.path.join(PROJECT_ROOT, file_name)
            if not os.path.isfile(file_path):
                missing_files.append(file_name)

        if missing_dirs or missing_files:
            error_msg = f"✗ 项目结构不完整: 缺失目录 {missing_dirs}, 缺失文件 {missing_files}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.check_results['project_structure'] = {
                'status': 'FAIL',
                'missing_dirs': missing_dirs,
                'missing_files': missing_files
            }
            return False
        else:
            self.log("✓ 项目结构完整")
            self.check_results['project_structure'] = {'status': 'PASS'}
            return True

    def check_permissions(self) -> bool:
        """检查文件权限"""
        self.log("检查文件权限...")
        try:
            # 检查是否有写入权限
            test_file = os.path.join(PROJECT_ROOT, 'logs', '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                self.log("✓ 文件写入权限正常")
                self.check_results['permissions'] = {'status': 'PASS'}
                return True
            except Exception as e:
                error_msg = f"✗ 无文件写入权限: {e}"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                self.check_results['permissions'] = {'status': 'FAIL'}
                return False
        except Exception as e:
            error_msg = f"✗ 检查权限失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def run_all_checks(self) -> Tuple[bool, Dict]:
        """运行所有检查"""
        self.log("=" * 50)
        self.log("开始环境检查")
        self.log("=" * 50)

        checks = [
            self.check_python_version,
            self.check_disk_space,
            self.check_memory,
            self.check_network,
            self.check_ports,
            self.check_pip,
            self.check_pyyaml,
            self.check_git,
            self.check_project_structure,
            self.check_permissions,
        ]

        all_passed = True
        for check in checks:
            try:
                if not check():
                    all_passed = False
            except Exception as e:
                self.log(f"检查 {check.__name__} 时发生错误: {e}", 'ERROR')
                all_passed = False

        self.log("=" * 50)
        if all_passed and not self.errors:
            self.log("✓ 所有环境检查通过")
        else:
            self.log(f"✗ 环境检查失败: {len(self.errors)} 个错误, {len(self.warnings)} 个警告")
        self.log("=" * 50)

        return all_passed and not self.errors, {
            'success': all_passed and not self.errors,
            'errors': self.errors,
            'warnings': self.warnings,
            'results': self.check_results
        }


def main():
    """主函数"""
    checker = EnvironmentChecker()
    success, results = checker.run_all_checks()

    # 输出JSON格式的结果（供其他脚本使用）
    if '--json' in sys.argv:
        import json
        print(json.dumps(results, indent=2, ensure_ascii=False))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
