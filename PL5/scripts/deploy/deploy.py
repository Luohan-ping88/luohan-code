#!/usr/bin/env python3
"""
PL5 主部署脚本
一键部署PL5排列五预测系统

部署流程:
1. 环境检查 (Python版本、磁盘空间、网络连接)
2. 依赖安装 (pip install -r requirements.txt)
3. 配置初始化 (创建配置文件、设置环境变量)
4. 代码部署 (复制代码、设置权限)
5. 数据库/数据准备 (初始化数据目录)
6. 验证测试 (运行冒烟测试)
7. 启动服务
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志文件
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'deploy.log')

# 部署步骤
DEPLOY_STEPS = [
    'environment_check',
    'install_dependencies',
    'init_config',
    'prepare_data',
    'verify_deployment',
    'start_service'
]


class DeployManager:
    """部署管理器"""

    def __init__(self, environment: str = 'production', skip_steps: List[str] = None):
        self.environment = environment
        self.skip_steps = skip_steps or []
        self.deploy_results: Dict[str, Dict] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.start_time = None
        self.end_time = None
        self._ensure_directories()

    def _ensure_directories(self):
        """确保必要目录存在"""
        os.makedirs(os.path.join(PROJECT_ROOT, 'logs'), exist_ok=True)
        os.makedirs(os.path.join(PROJECT_ROOT, 'backups'), exist_ok=True)

    def log(self, message: str, level: str = 'INFO'):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

    def run_script(self, script_name: str, args: List[str] = None) -> Tuple[bool, Dict]:
        """运行部署脚本"""
        script_path = os.path.join(PROJECT_ROOT, 'scripts', 'deploy', f"{script_name}.py")

        if not os.path.exists(script_path):
            error_msg = f"脚本不存在: {script_path}"
            self.log(error_msg, 'ERROR')
            return False, {'error': error_msg}

        cmd = [sys.executable, script_path]
        if args:
            cmd.extend(args)
        if '--json' not in cmd:
            cmd.append('--json')

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=PROJECT_ROOT
            )

            # 解析JSON输出
            try:
                output = json.loads(result.stdout)
            except json.JSONDecodeError:
                output = {'stdout': result.stdout, 'stderr': result.stderr}

            success = result.returncode == 0 and output.get('success', False)
            return success, output

        except subprocess.TimeoutExpired:
            error_msg = f"脚本执行超时: {script_name}"
            self.log(error_msg, 'ERROR')
            return False, {'error': error_msg}
        except Exception as e:
            error_msg = f"脚本执行失败: {script_name} - {e}"
            self.log(error_msg, 'ERROR')
            return False, {'error': str(e)}

    def step_environment_check(self) -> bool:
        """步骤1: 环境检查"""
        self.log("=" * 60)
        self.log("步骤 1/6: 环境检查")
        self.log("=" * 60)

        success, result = self.run_script('check_environment')
        self.deploy_results['environment_check'] = result

        if success:
            self.log("✓ 环境检查通过")
        else:
            error_msg = "✗ 环境检查失败"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)

        return success

    def step_install_dependencies(self) -> bool:
        """步骤2: 安装依赖"""
        self.log("=" * 60)
        self.log("步骤 2/6: 安装依赖")
        self.log("=" * 60)

        success, result = self.run_script('install_dependencies')
        self.deploy_results['install_dependencies'] = result

        if success:
            self.log("✓ 依赖安装完成")
        else:
            error_msg = "✗ 依赖安装失败"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)

        return success

    def step_init_config(self) -> bool:
        """步骤3: 初始化配置"""
        self.log("=" * 60)
        self.log("步骤 3/6: 初始化配置")
        self.log("=" * 60)

        success, result = self.run_script('init_config')
        self.deploy_results['init_config'] = result

        if success:
            self.log("✓ 配置初始化完成")
        else:
            error_msg = "✗ 配置初始化失败"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)

        return success

    def step_prepare_data(self) -> bool:
        """步骤4: 准备数据"""
        self.log("=" * 60)
        self.log("步骤 4/6: 准备数据")
        self.log("=" * 60)

        try:
            # 确保数据目录存在
            data_dirs = [
                'data/raw',
                'data/processed',
            ]

            for data_dir in data_dirs:
                dir_path = os.path.join(PROJECT_ROOT, data_dir)
                os.makedirs(dir_path, exist_ok=True)

            # 检查历史数据文件
            history_file = os.path.join(PROJECT_ROOT, 'data', 'raw', 'pl5_history.txt')
            if not os.path.exists(history_file):
                self.log("⚠ 历史数据文件不存在，将在首次运行时自动下载")
                self.warnings.append("历史数据文件不存在")

            self.log("✓ 数据准备完成")
            self.deploy_results['prepare_data'] = {'status': 'PASS'}
            return True

        except Exception as e:
            error_msg = f"✗ 数据准备失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.deploy_results['prepare_data'] = {'status': 'FAIL', 'error': str(e)}
            return False

    def step_verify_deployment(self) -> bool:
        """步骤5: 验证部署"""
        self.log("=" * 60)
        self.log("步骤 5/6: 验证部署")
        self.log("=" * 60)

        # 先运行部署前检查
        self.log("运行部署前检查...")
        success, result = self.run_script('pre_deploy_check', [f'--env={self.environment}'])
        self.deploy_results['pre_deploy_check'] = result

        if not success:
            error_msg = "✗ 部署前检查失败"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

        self.log("✓ 部署前检查通过")
        return True

    def step_start_service(self) -> bool:
        """步骤6: 启动服务"""
        self.log("=" * 60)
        self.log("步骤 6/6: 启动服务")
        self.log("=" * 60)

        try:
            # 检查端口是否被占用
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 8000))
            sock.close()

            if result == 0:
                self.log("⚠ 端口8000已被占用，服务可能已在运行")
                self.warnings.append("端口8000已被占用")

            # 启动服务
            self.log("启动API服务...")

            # 使用subprocess启动服务（后台运行）
            if sys.platform == 'win32':
                # Windows
                subprocess.Popen(
                    [sys.executable, '-m', 'uvicorn', 'src.ai.api:app', '--host', '0.0.0.0', '--port', '8000'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=PROJECT_ROOT
                )
            else:
                # Linux/Mac
                subprocess.Popen(
                    [sys.executable, '-m', 'uvicorn', 'src.ai.api:app', '--host', '0.0.0.0', '--port', '8000'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=PROJECT_ROOT
                )

            # 等待服务启动
            self.log("等待服务启动...")
            time.sleep(5)

            # 运行部署后验证
            self.log("运行部署后验证...")
            success, result = self.run_script('post_deploy_verify', [f'--env={self.environment}'])
            self.deploy_results['post_deploy_verify'] = result

            if success:
                self.log("✓ 服务启动成功，部署后验证通过")
                return True
            else:
                warning_msg = "⚠ 服务已启动，但部署后验证有警告"
                self.log(warning_msg, 'WARNING')
                self.warnings.append(warning_msg)
                return True  # 警告不视为失败

        except Exception as e:
            error_msg = f"✗ 启动服务失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.deploy_results['start_service'] = {'status': 'FAIL', 'error': str(e)}
            return False

    def create_backup(self) -> bool:
        """创建部署前备份"""
        self.log("创建部署前备份...")

        success, result = self.run_script('rollback', ['create'])

        if success:
            self.log("✓ 备份创建成功")
        else:
            self.log("⚠ 备份创建失败，继续部署", 'WARNING')

        return True  # 备份失败不阻止部署

    def run_deployment(self) -> Tuple[bool, Dict]:
        """运行完整部署流程"""
        self.start_time = datetime.now()

        self.log("\n" + "=" * 60)
        self.log("PL5 系统部署开始")
        self.log(f"环境: {self.environment}")
        self.log(f"时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 60 + "\n")

        # 创建备份
        if 'backup' not in self.skip_steps:
            self.create_backup()

        # 执行部署步骤
        steps = [
            ('environment_check', self.step_environment_check),
            ('install_dependencies', self.step_install_dependencies),
            ('init_config', self.step_init_config),
            ('prepare_data', self.step_prepare_data),
            ('verify_deployment', self.step_verify_deployment),
            ('start_service', self.step_start_service),
        ]

        all_passed = True
        for step_name, step_func in steps:
            if step_name in self.skip_steps:
                self.log(f"跳过步骤: {step_name}")
                continue

            try:
                if not step_func():
                    all_passed = False
                    # 关键步骤失败，停止部署
                    if step_name in ['environment_check', 'install_dependencies', 'init_config']:
                        self.log(f"关键步骤失败，停止部署: {step_name}", 'ERROR')
                        break
            except Exception as e:
                self.log(f"步骤 {step_name} 执行出错: {e}", 'ERROR')
                all_passed = False
                if step_name in ['environment_check', 'install_dependencies', 'init_config']:
                    break

        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()

        # 生成部署报告
        self.log("\n" + "=" * 60)
        if all_passed:
            self.log("✓ 部署成功完成")
        else:
            self.log(f"✗ 部署失败: {len(self.errors)} 个错误")
        self.log(f"耗时: {duration:.2f} 秒")
        self.log("=" * 60 + "\n")

        report = {
            'success': all_passed,
            'environment': self.environment,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': duration,
            'errors': self.errors,
            'warnings': self.warnings,
            'results': self.deploy_results
        }

        # 保存部署报告
        self.save_report(report)

        return all_passed, report

    def save_report(self, report: Dict):
        """保存部署报告"""
        report_file = os.path.join(
            PROJECT_ROOT,
            'logs',
            f'deploy_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.log(f"部署报告已保存: {report_file}")
        except Exception as e:
            self.log(f"保存部署报告失败: {e}", 'WARNING')


def print_usage():
    """打印使用说明"""
    print("""
PL5 部署脚本

用法: python deploy.py [选项]

选项:
  -h, --help            显示帮助信息
  -e, --env ENV         部署环境 (默认: production)
  -s, --skip STEPS      跳过的步骤，逗号分隔
  --dry-run             试运行（不实际执行）

可用步骤:
  environment_check     环境检查
  install_dependencies  安装依赖
  init_config          初始化配置
  prepare_data         准备数据
  verify_deployment    验证部署
  start_service        启动服务
  backup               创建备份

示例:
  python deploy.py                              # 完整部署
  python deploy.py -e staging                   # 部署到测试环境
  python deploy.py -s backup,start_service      # 跳过备份和启动服务
  python deploy.py --dry-run                    # 试运行
""")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PL5 部署脚本', add_help=False)
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助')
    parser.add_argument('-e', '--env', default='production', help='部署环境')
    parser.add_argument('-s', '--skip', default='', help='跳过的步骤')
    parser.add_argument('--dry-run', action='store_true', help='试运行')

    args = parser.parse_args()

    if args.help:
        print_usage()
        return 0

    environment = args.env
    skip_steps = [s.strip() for s in args.skip.split(',') if s.strip()]

    if args.dry_run:
        print("【试运行模式】")
        print(f"环境: {environment}")
        print(f"跳过步骤: {skip_steps}")
        print("部署步骤:")
        for i, step in enumerate(DEPLOY_STEPS, 1):
            status = "跳过" if step in skip_steps else "执行"
            print(f"  {i}. {step} - {status}")
        return 0

    # 运行部署
    manager = DeployManager(environment=environment, skip_steps=skip_steps)
    success, report = manager.run_deployment()

    # 输出JSON格式的结果
    if '--json' in sys.argv:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
