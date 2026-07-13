#!/usr/bin/env python3
"""
PL5 部署前检查脚本
用于在实际部署前进行全面检查
"""

import os
import sys
import json
import subprocess
import socket
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志文件
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'deploy.log')


class PreDeployChecker:
    """部署前检查器"""

    def __init__(self, environment: str = 'production'):
        self.environment = environment
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

    def check_code_quality(self) -> bool:
        """检查代码质量"""
        self.log("检查代码质量...")

        issues = []

        # 检查是否有语法错误
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', 'main.py'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                issues.append(f"main.py 语法错误: {result.stderr}")
        except Exception as e:
            issues.append(f"语法检查失败: {e}")

        # 检查关键文件是否存在
        critical_files = [
            'main.py',
            'requirements.txt',
            'config/config.json',
            'src/core/orchestrator.py',
        ]

        for file in critical_files:
            file_path = os.path.join(PROJECT_ROOT, file)
            if not os.path.exists(file_path):
                issues.append(f"关键文件缺失: {file}")

        if issues:
            error_msg = f"✗ 代码质量检查失败: {issues}"
            self.log(error_msg, 'ERROR')
            self.errors.extend(issues)
            self.check_results['code_quality'] = {
                'status': 'FAIL',
                'issues': issues
            }
            return False
        else:
            self.log("✓ 代码质量检查通过")
            self.check_results['code_quality'] = {'status': 'PASS'}
            return True

    def check_dependencies(self) -> bool:
        """检查依赖完整性"""
        self.log("检查依赖完整性...")

        missing = []
        outdated = []

        # 读取requirements.txt
        req_file = os.path.join(PROJECT_ROOT, 'requirements.txt')
        if not os.path.exists(req_file):
            error_msg = "✗ requirements.txt 不存在"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

        with open(req_file, 'r') as f:
            requirements = f.readlines()

        # 检查每个依赖
        for req in requirements:
            req = req.strip()
            if not req or req.startswith('#'):
                continue

            package_name = req.split('==')[0].split('>=')[0].split('<=')[0].strip()

            try:
                __import__(package_name.lower().replace('-', '_'))
            except ImportError:
                missing.append(package_name)

        if missing:
            error_msg = f"✗ 缺失依赖: {', '.join(missing)}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.check_results['dependencies'] = {
                'status': 'FAIL',
                'missing': missing,
                'outdated': outdated
            }
            return False
        else:
            self.log("✓ 所有依赖已安装")
            self.check_results['dependencies'] = {
                'status': 'PASS',
                'checked': len(requirements)
            }
            return True

    def check_configuration(self) -> bool:
        """检查配置有效性"""
        self.log("检查配置有效性...")

        issues = []

        # 检查主配置
        config_file = os.path.join(PROJECT_ROOT, 'config', 'config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # 验证必要字段
                required_fields = ['system', 'scheduler', 'prediction', 'model', 'data']
                for field in required_fields:
                    if field not in config:
                        issues.append(f"配置缺少必要字段: {field}")
            except json.JSONDecodeError as e:
                issues.append(f"config.json 解析错误: {e}")
        else:
            issues.append("config.json 不存在")

        # 检查环境变量
        env_file = os.path.join(PROJECT_ROOT, '.env')
        if not os.path.exists(env_file):
            self.log("⚠ .env 文件不存在，使用默认配置", 'WARNING')
            self.warnings.append(".env 文件不存在")

        if issues:
            error_msg = f"✗ 配置检查失败: {issues}"
            self.log(error_msg, 'ERROR')
            self.errors.extend(issues)
            self.check_results['configuration'] = {
                'status': 'FAIL',
                'issues': issues
            }
            return False
        else:
            self.log("✓ 配置检查通过")
            self.check_results['configuration'] = {'status': 'PASS'}
            return True

    def check_data_files(self) -> bool:
        """检查数据文件"""
        self.log("检查数据文件...")

        issues = []
        warnings = []

        # 检查数据目录
        data_dirs = [
            'data/raw',
            'data/processed',
        ]

        for data_dir in data_dirs:
            dir_path = os.path.join(PROJECT_ROOT, data_dir)
            if not os.path.exists(dir_path):
                warnings.append(f"数据目录不存在: {data_dir}")

        # 检查历史数据文件
        history_file = os.path.join(PROJECT_ROOT, 'data', 'raw', 'pl5_history.txt')
        if not os.path.exists(history_file):
            warnings.append("历史数据文件不存在，将在首次运行时自动下载")

        # 检查模型目录
        models_dir = os.path.join(PROJECT_ROOT, 'models')
        if not os.path.exists(models_dir):
            warnings.append("模型目录不存在")
        elif not any(os.path.isfile(os.path.join(models_dir, f)) for f in os.listdir(models_dir)):
            warnings.append("模型目录为空，需要训练模型")

        if issues:
            error_msg = f"✗ 数据文件检查失败: {issues}"
            self.log(error_msg, 'ERROR')
            self.errors.extend(issues)
            self.check_results['data_files'] = {
                'status': 'FAIL',
                'issues': issues,
                'warnings': warnings
            }
            return False
        else:
            if warnings:
                self.log(f"⚠ 数据文件检查通过，但有警告: {warnings}")
                self.warnings.extend(warnings)
            else:
                self.log("✓ 数据文件检查通过")
            self.check_results['data_files'] = {
                'status': 'PASS',
                'warnings': warnings
            }
            return True

    def check_database(self) -> bool:
        """检查数据库连接（如果使用）"""
        self.log("检查数据库...")

        # 目前PL5主要使用文件存储，此检查为预留
        self.log("✓ 数据库检查通过（使用文件存储）")
        self.check_results['database'] = {'status': 'PASS', 'type': 'file_storage'}
        return True

    def check_external_services(self) -> bool:
        """检查外部服务连接"""
        self.log("检查外部服务...")

        services = {
            'data_source': ('http://data.17500.cn', 80),
        }

        unavailable = []

        for service_name, (host, port) in services.items():
            try:
                if port == 80:
                    response = requests.get(host, timeout=5)
                    if response.status_code != 200:
                        unavailable.append(f"{service_name} (HTTP {response.status_code})")
                else:
                    sock = socket.create_connection((host, port), timeout=5)
                    sock.close()
            except Exception as e:
                unavailable.append(f"{service_name} ({e})")

        if unavailable:
            warning_msg = f"⚠ 部分外部服务不可用: {unavailable}"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            self.check_results['external_services'] = {
                'status': 'WARNING',
                'unavailable': unavailable
            }
        else:
            self.log("✓ 外部服务检查通过")
            self.check_results['external_services'] = {'status': 'PASS'}

        return True  # 外部服务不可用不是致命错误

    def check_security(self) -> bool:
        """安全检查"""
        self.log("安全检查...")

        issues = []

        # 检查是否有敏感文件暴露
        sensitive_files = [
            '.env',
            'config/email_config.json',
        ]

        for file in sensitive_files:
            file_path = os.path.join(PROJECT_ROOT, file)
            if os.path.exists(file_path):
                # 检查文件权限
                try:
                    stat = os.stat(file_path)
                    # Windows上权限检查简化
                    if sys.platform != 'win32':
                        if stat.st_mode & 0o077:
                            issues.append(f"{file} 权限过于开放")
                except Exception:
                    pass

        # 检查是否有敏感信息硬编码
        dangerous_patterns = ['password', 'secret', 'api_key', 'token']
        # 这里可以添加更复杂的检查逻辑

        if issues:
            warning_msg = f"⚠ 安全警告: {issues}"
            self.log(warning_msg, 'WARNING')
            self.warnings.extend(issues)
            self.check_results['security'] = {
                'status': 'WARNING',
                'issues': issues
            }
        else:
            self.log("✓ 安全检查通过")
            self.check_results['security'] = {'status': 'PASS'}

        return True

    def check_backup_status(self) -> bool:
        """检查备份状态"""
        self.log("检查备份状态...")

        backups_dir = os.path.join(PROJECT_ROOT, 'backups')

        if not os.path.exists(backups_dir):
            warning_msg = "⚠ 备份目录不存在"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            self.check_results['backup'] = {
                'status': 'WARNING',
                'message': '备份目录不存在'
            }
            return True

        # 检查最近的备份
        backup_dirs = [d for d in os.listdir(backups_dir) if os.path.isdir(os.path.join(backups_dir, d))]

        if not backup_dirs:
            warning_msg = "⚠ 没有可用的备份"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            self.check_results['backup'] = {
                'status': 'WARNING',
                'message': '没有可用的备份'
            }
        else:
            # 按时间排序
            backup_dirs.sort(reverse=True)
            latest_backup = backup_dirs[0]
            self.log(f"✓ 最新备份: {latest_backup}")
            self.check_results['backup'] = {
                'status': 'PASS',
                'latest_backup': latest_backup,
                'total_backups': len(backup_dirs)
            }

        return True

    def check_system_resources(self) -> bool:
        """检查系统资源"""
        self.log("检查系统资源...")

        issues = []

        try:
            import psutil

            # 检查CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                issues.append(f"CPU使用率过高: {cpu_percent}%")

            # 检查内存
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                issues.append(f"内存使用率过高: {memory.percent}%")

            # 检查磁盘
            disk = psutil.disk_usage(PROJECT_ROOT)
            if disk.percent > 90:
                issues.append(f"磁盘使用率过高: {disk.percent}%")

            self.log(f"  CPU: {cpu_percent}%, 内存: {memory.percent}%, 磁盘: {disk.percent}%")

        except ImportError:
            self.log("⚠ psutil 未安装，跳过详细资源检查", 'WARNING')

        if issues:
            warning_msg = f"⚠ 系统资源警告: {issues}"
            self.log(warning_msg, 'WARNING')
            self.warnings.extend(issues)
            self.check_results['system_resources'] = {
                'status': 'WARNING',
                'issues': issues
            }
        else:
            self.log("✓ 系统资源充足")
            self.check_results['system_resources'] = {'status': 'PASS'}

        return True

    def run_all_checks(self) -> Tuple[bool, Dict]:
        """运行所有部署前检查"""
        self.log("=" * 50)
        self.log(f"开始部署前检查 (环境: {self.environment})")
        self.log("=" * 50)

        checks = [
            ('代码质量', self.check_code_quality),
            ('依赖完整性', self.check_dependencies),
            ('配置有效性', self.check_configuration),
            ('数据文件', self.check_data_files),
            ('数据库', self.check_database),
            ('外部服务', self.check_external_services),
            ('安全性', self.check_security),
            ('备份状态', self.check_backup_status),
            ('系统资源', self.check_system_resources),
        ]

        all_passed = True
        for name, check_func in checks:
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                self.log(f"检查 {name} 时发生错误: {e}", 'ERROR')
                all_passed = False

        self.log("=" * 50)
        if all_passed and not self.errors:
            self.log("✓ 所有部署前检查通过，可以开始部署")
        else:
            self.log(f"✗ 部署前检查失败: {len(self.errors)} 个错误, {len(self.warnings)} 个警告")
            if self.errors:
                self.log("错误列表:")
                for error in self.errors:
                    self.log(f"  - {error}", 'ERROR')
        self.log("=" * 50)

        return all_passed and not self.errors, {
            'success': all_passed and not self.errors,
            'environment': self.environment,
            'errors': self.errors,
            'warnings': self.warnings,
            'results': self.check_results
        }


def main():
    """主函数"""
    environment = 'production'

    # 解析命令行参数
    for arg in sys.argv[1:]:
        if arg.startswith('--env='):
            environment = arg.split('=')[1]

    checker = PreDeployChecker(environment)
    success, results = checker.run_all_checks()

    # 输出JSON格式的结果
    if '--json' in sys.argv:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
