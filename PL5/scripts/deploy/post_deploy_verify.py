#!/usr/bin/env python3
"""
PL5 部署后验证脚本
用于验证部署是否成功
"""

import os
import sys
import json
import time
import socket
import subprocess
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志文件
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'deploy.log')

# 默认配置
DEFAULT_API_HOST = 'localhost'
DEFAULT_API_PORT = 8000
DEFAULT_HEALTH_CHECK_URL = f'http://{DEFAULT_API_HOST}:{DEFAULT_API_PORT}/api/health'


class PostDeployVerifier:
    """部署后验证器"""

    def __init__(self, environment: str = 'production'):
        self.environment = environment
        self.verify_results: Dict[str, Dict] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.api_base_url = f"http://{DEFAULT_API_HOST}:{DEFAULT_API_PORT}"
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

    def verify_service_running(self) -> bool:
        """验证服务是否运行"""
        self.log("验证服务运行状态...")

        # 检查端口是否被监听
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((DEFAULT_API_HOST, DEFAULT_API_PORT))
            sock.close()

            if result == 0:
                self.log(f"✓ 服务正在端口 {DEFAULT_API_PORT} 上运行")
                self.verify_results['service_running'] = {
                    'status': 'PASS',
                    'port': DEFAULT_API_PORT
                }
                return True
            else:
                error_msg = f"✗ 服务未在端口 {DEFAULT_API_PORT} 上运行"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                self.verify_results['service_running'] = {
                    'status': 'FAIL',
                    'port': DEFAULT_API_PORT,
                    'error': 'Port not open'
                }
                return False
        except Exception as e:
            error_msg = f"✗ 检查服务状态失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def verify_health_check(self) -> bool:
        """验证健康检查端点"""
        self.log("验证健康检查端点...")

        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    DEFAULT_HEALTH_CHECK_URL,
                    timeout=10
                )

                if response.status_code == 200:
                    health_data = response.json()
                    self.log(f"✓ 健康检查通过: {health_data}")
                    self.verify_results['health_check'] = {
                        'status': 'PASS',
                        'response': health_data,
                        'attempts': attempt + 1
                    }
                    return True
                else:
                    error_msg = f"✗ 健康检查失败: HTTP {response.status_code}"
                    self.log(error_msg, 'ERROR')
                    if attempt < max_retries - 1:
                        self.log(f"  重试中... ({attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        self.errors.append(error_msg)
                        self.verify_results['health_check'] = {
                            'status': 'FAIL',
                            'http_status': response.status_code,
                            'attempts': attempt + 1
                        }
                        return False

            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    self.log(f"  连接失败，重试中... ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    error_msg = "✗ 无法连接到服务"
                    self.log(error_msg, 'ERROR')
                    self.errors.append(error_msg)
                    self.verify_results['health_check'] = {
                        'status': 'FAIL',
                        'error': 'Connection refused',
                        'attempts': attempt + 1
                    }
                    return False
            except Exception as e:
                error_msg = f"✗ 健康检查异常: {e}"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                return False

    def verify_api_endpoints(self) -> bool:
        """验证API端点"""
        self.log("验证API端点...")

        endpoints = [
            {'path': '/api/health', 'method': 'GET', 'expected_status': 200},
            {'path': '/api/status', 'method': 'GET', 'expected_status': 200},
        ]

        results = []
        all_passed = True

        for endpoint in endpoints:
            url = f"{self.api_base_url}{endpoint['path']}"
            try:
                if endpoint['method'] == 'GET':
                    response = requests.get(url, timeout=10)
                else:
                    response = requests.post(url, timeout=10)

                if response.status_code == endpoint['expected_status']:
                    self.log(f"✓ {endpoint['method']} {endpoint['path']} - {response.status_code}")
                    results.append({
                        'endpoint': endpoint['path'],
                        'status': 'PASS',
                        'http_status': response.status_code
                    })
                else:
                    warning_msg = f"⚠ {endpoint['method']} {endpoint['path']} - 期望 {endpoint['expected_status']}, 实际 {response.status_code}"
                    self.log(warning_msg, 'WARNING')
                    self.warnings.append(warning_msg)
                    results.append({
                        'endpoint': endpoint['path'],
                        'status': 'WARNING',
                        'expected_status': endpoint['expected_status'],
                        'actual_status': response.status_code
                    })
                    all_passed = False

            except Exception as e:
                warning_msg = f"⚠ {endpoint['method']} {endpoint['path']} - 错误: {e}"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                results.append({
                    'endpoint': endpoint['path'],
                    'status': 'FAIL',
                    'error': str(e)
                })
                all_passed = False

        self.verify_results['api_endpoints'] = {
            'status': 'PASS' if all_passed else 'WARNING',
            'results': results
        }

        return True  # API端点警告不视为部署失败

    def verify_response_time(self) -> bool:
        """验证响应时间"""
        self.log("验证响应时间...")

        try:
            start_time = time.time()
            response = requests.get(DEFAULT_HEALTH_CHECK_URL, timeout=10)
            end_time = time.time()

            response_time = (end_time - start_time) * 1000  # 转换为毫秒

            if response_time < 1000:  # 1秒内
                self.log(f"✓ 响应时间正常: {response_time:.2f}ms")
                self.verify_results['response_time'] = {
                    'status': 'PASS',
                    'response_time_ms': round(response_time, 2)
                }
                return True
            elif response_time < 3000:  # 3秒内
                warning_msg = f"⚠ 响应时间较慢: {response_time:.2f}ms"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                self.verify_results['response_time'] = {
                    'status': 'WARNING',
                    'response_time_ms': round(response_time, 2)
                }
                return True
            else:
                warning_msg = f"⚠ 响应时间过慢: {response_time:.2f}ms"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                self.verify_results['response_time'] = {
                    'status': 'WARNING',
                    'response_time_ms': round(response_time, 2)
                }
                return True

        except Exception as e:
            error_msg = f"✗ 响应时间测试失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def verify_core_functionality(self) -> bool:
        """验证核心功能"""
        self.log("验证核心功能...")

        try:
            sys.path.insert(0, PROJECT_ROOT)
            from src.core.orchestrator import PL5Orchestrator

            orchestrator = PL5Orchestrator()
            status = orchestrator.get_status()

            self.log(f"✓ 核心功能正常: {status}")
            self.verify_results['core_functionality'] = {
                'status': 'PASS',
                'system_status': status
            }
            return True

        except Exception as e:
            warning_msg = f"⚠ 核心功能验证失败: {e}"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            self.verify_results['core_functionality'] = {
                'status': 'WARNING',
                'error': str(e)
            }
            return True  # 核心功能警告不视为部署失败

    def verify_data_access(self) -> bool:
        """验证数据访问"""
        self.log("验证数据访问...")

        issues = []

        # 检查数据目录
        data_dirs = [
            'data/raw',
            'data/processed',
        ]

        for data_dir in data_dirs:
            dir_path = os.path.join(PROJECT_ROOT, data_dir)
            if not os.path.exists(dir_path):
                issues.append(f"数据目录不存在: {data_dir}")

        # 检查日志目录写入
        log_dir = os.path.join(PROJECT_ROOT, 'logs')
        try:
            test_file = os.path.join(log_dir, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except Exception as e:
            issues.append(f"日志目录写入失败: {e}")

        if issues:
            warning_msg = f"⚠ 数据访问警告: {issues}"
            self.log(warning_msg, 'WARNING')
            self.warnings.extend(issues)
            self.verify_results['data_access'] = {
                'status': 'WARNING',
                'issues': issues
            }
        else:
            self.log("✓ 数据访问正常")
            self.verify_results['data_access'] = {'status': 'PASS'}

        return True

    def verify_configuration(self) -> bool:
        """验证配置加载"""
        self.log("验证配置加载...")

        try:
            config_file = os.path.join(PROJECT_ROOT, 'config', 'config.json')
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 验证必要字段
            required_fields = ['system', 'scheduler', 'prediction']
            missing_fields = [f for f in required_fields if f not in config]

            if missing_fields:
                warning_msg = f"⚠ 配置缺少字段: {missing_fields}"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                self.verify_results['configuration'] = {
                    'status': 'WARNING',
                    'missing_fields': missing_fields
                }
            else:
                self.log("✓ 配置加载正常")
                self.verify_results['configuration'] = {
                    'status': 'PASS',
                    'version': config.get('system', {}).get('version', 'unknown')
                }

            return True

        except Exception as e:
            error_msg = f"✗ 配置加载失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def verify_logs(self) -> bool:
        """验证日志记录"""
        self.log("验证日志记录...")

        log_files = [
            'logs/deploy.log',
            'logs/system.log',
        ]

        existing_logs = []
        for log_file in log_files:
            log_path = os.path.join(PROJECT_ROOT, log_file)
            if os.path.exists(log_path):
                existing_logs.append(log_file)

        if existing_logs:
            self.log(f"✓ 日志文件存在: {existing_logs}")
            self.verify_results['logs'] = {
                'status': 'PASS',
                'log_files': existing_logs
            }
        else:
            warning_msg = "⚠ 未找到日志文件"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)
            self.verify_results['logs'] = {
                'status': 'WARNING',
                'message': 'No log files found'
            }

        return True

    def verify_processes(self) -> bool:
        """验证进程状态"""
        self.log("验证进程状态...")

        try:
            import psutil

            python_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline and any('pl5' in str(arg).lower() or 'main' in str(arg).lower() for arg in cmdline):
                            python_processes.append({
                                'pid': proc.info['pid'],
                                'cmdline': ' '.join(cmdline) if cmdline else 'N/A'
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if python_processes:
                self.log(f"✓ 发现 {len(python_processes)} 个PL5相关进程")
                self.verify_results['processes'] = {
                    'status': 'PASS',
                    'processes': python_processes
                }
            else:
                warning_msg = "⚠ 未发现PL5相关进程"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                self.verify_results['processes'] = {
                    'status': 'WARNING',
                    'message': 'No PL5 processes found'
                }

            return True

        except ImportError:
            self.log("⚠ psutil 未安装，跳过进程检查")
            self.verify_results['processes'] = {
                'status': 'PASS',
                'message': 'Skipped (psutil not installed)'
            }
            return True

    def generate_report(self) -> Dict:
        """生成验证报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'success': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings,
            'results': self.verify_results
        }

    def run_all_verifications(self) -> Tuple[bool, Dict]:
        """运行所有部署后验证"""
        self.log("=" * 50)
        self.log(f"开始部署后验证 (环境: {self.environment})")
        self.log("=" * 50)

        verifications = [
            ('服务运行状态', self.verify_service_running),
            ('健康检查', self.verify_health_check),
            ('API端点', self.verify_api_endpoints),
            ('响应时间', self.verify_response_time),
            ('核心功能', self.verify_core_functionality),
            ('数据访问', self.verify_data_access),
            ('配置加载', self.verify_configuration),
            ('日志记录', self.verify_logs),
            ('进程状态', self.verify_processes),
        ]

        all_passed = True
        for name, verify_func in verifications:
            try:
                if not verify_func():
                    all_passed = False
            except Exception as e:
                self.log(f"验证 {name} 时发生错误: {e}", 'ERROR')
                all_passed = False

        self.log("=" * 50)
        if all_passed and not self.errors:
            self.log("✓ 所有部署后验证通过，部署成功")
        else:
            self.log(f"✗ 部署后验证失败: {len(self.errors)} 个错误, {len(self.warnings)} 个警告")
            if self.errors:
                self.log("错误列表:")
                for error in self.errors:
                    self.log(f"  - {error}", 'ERROR')
        self.log("=" * 50)

        report = self.generate_report()

        # 保存报告
        report_file = os.path.join(PROJECT_ROOT, 'logs', f'deploy_verify_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.log(f"验证报告已保存: {report_file}")
        except Exception as e:
            self.log(f"保存验证报告失败: {e}", 'WARNING')

        return all_passed and not self.errors, report


def main():
    """主函数"""
    environment = 'production'

    # 解析命令行参数
    for arg in sys.argv[1:]:
        if arg.startswith('--env='):
            environment = arg.split('=')[1]

    verifier = PostDeployVerifier(environment)
    success, results = verifier.run_all_verifications()

    # 输出JSON格式的结果
    if '--json' in sys.argv:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
