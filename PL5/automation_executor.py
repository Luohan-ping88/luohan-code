#!/usr/bin/env python
"""
PL5 日循环训练自动化执行器
执行完整训练流程并监控系统状态
"""

import os
import sys
import time
import subprocess
import psutil
import logging
from datetime import datetime
from pathlib import Path
import json
import traceback

# 配置日志
LOGS_DIR = Path(__file__).parent / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
REPORT_PATH = LOGS_DIR / f'automation_report_{timestamp}.txt'

# 配置日志记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / f'automation_{timestamp}.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class AutomationExecutor:
    def __init__(self):
        self.start_time = datetime.now()
        self.report_data = {
            'training_success': False,
            'performance_issues': [],
            'code_quality_issues': [],
            'fixes_applied': [],
            'system_warnings': [],
            'system_errors': [],
            'system_suggestions': []
        }
        self.process = None

    def monitor_system(self):
        """监控系统性能"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            logger.info(f"系统监控 - CPU: {cpu_percent}%, 内存: {memory.percent}%, 磁盘: {disk.percent}%")

            if cpu_percent > 90:
                self.report_data['performance_issues'].append(f"高CPU使用率: {cpu_percent}%")
            if memory.percent > 90:
                self.report_data['performance_issues'].append(f"高内存使用率: {memory.percent}%")
            if disk.percent > 90:
                self.report_data['performance_issues'].append(f"高磁盘使用率: {disk.percent}%")

            return {
                'cpu': cpu_percent,
                'memory': memory.percent,
                'disk': disk.percent
            }
        except Exception as e:
            logger.warning(f"系统监控失败: {e}")
            return None

    def run_command(self, command, description, cwd=None):
        """运行命令并监控输出"""
        logger.info(f"执行: {description}")
        logger.info(f"命令: {' '.join(command) if isinstance(command, list) else command}")

        try:
            # 启动子进程
            self.process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # 实时监控输出
            output_lines = []
            while True:
                output = self.process.stdout.readline()
                if output == '' and self.process.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    output_lines.append(line)
                    print(line, flush=True)

                    # 检测警告和错误
                    if 'WARNING' in line.upper() or 'WARN' in line.upper():
                        self.report_data['system_warnings'].append(line)
                    if 'ERROR' in line.upper() or 'EXCEPTION' in line.upper() or 'Traceback' in line:
                        self.report_data['system_errors'].append(line)

                    # 定期监控系统性能
                    if len(output_lines) % 50 == 0:
                        self.monitor_system()

            returncode = self.process.poll()

            if returncode == 0:
                logger.info(f"{description} 执行成功")
                return True, output_lines
            else:
                logger.error(f"{description} 执行失败，返回码: {returncode}")
                return False, output_lines

        except Exception as e:
            logger.error(f"{description} 执行异常: {e}")
            self.report_data['system_errors'].append(f"{description} 异常: {str(e)}")
            return False, [str(e)]

    def check_environment(self):
        """检查环境和依赖"""
        logger.info("检查运行环境...")

        # 检查Python版本
        if sys.version_info < (3, 8):
            self.report_data['code_quality_issues'].append(f"Python版本过低: {sys.version_info}")

        # 检查关键目录
        required_dirs = ['data', 'models', 'logs', 'config']
        for dir_name in required_dirs:
            if not Path(dir_name).exists():
                self.report_data['code_quality_issues'].append(f"缺失目录: {dir_name}")

        # 检查关键文件
        required_files = ['main.py', 'requirements.txt']
        for file_name in required_files:
            if not Path(file_name).exists():
                self.report_data['code_quality_issues'].append(f"缺失文件: {file_name}")

        return len(self.report_data['code_quality_issues']) == 0

    def execute_full_pipeline(self):
        """执行完整的日循环训练流程"""
        project_dir = Path(__file__).parent
        os.chdir(project_dir)

        # 步骤1: 检查环境
        logger.info("="*70)
        logger.info("步骤1: 检查运行环境")
        logger.info("="*70)
        self.check_environment()
        self.monitor_system()

        # 步骤2: 执行完整日循环训练流程
        logger.info("\n" + "="*70)
        logger.info("步骤2: 执行完整日循环训练流程 (schedule --once)")
        logger.info("="*70)
        schedule_success, schedule_output = self.run_command(
            [sys.executable, 'main.py', 'schedule', '--once'],
            "完整日循环训练流程",
            cwd=project_dir
        )

        # 尝试修复错误
        if not schedule_success:
            logger.warning("尝试修复训练问题...")
            self.attempt_repairs(schedule_output)
            # 重新尝试一次
            logger.info("重新执行训练流程...")
            schedule_success, _ = self.run_command(
                [sys.executable, 'main.py', 'schedule', '--once'],
                "重新执行完整日循环训练流程",
                cwd=project_dir
            )

        if not schedule_success:
            logger.error("训练流程失败，无法继续")
            return False

        # 步骤3: 执行预测
        logger.info("\n" + "="*70)
        logger.info("步骤3: 执行预测流程 (predict)")
        logger.info("="*70)
        predict_success, predict_output = self.run_command(
            [sys.executable, 'main.py', 'predict'],
            "预测流程",
            cwd=project_dir
        )

        if not predict_success:
            logger.warning("预测流程失败")

        # 步骤4: 执行分析和发送邮件
        logger.info("\n" + "="*70)
        logger.info("步骤4: 执行分析和发送邮件 (analyze)")
        logger.info("="*70)
        analyze_success, analyze_output = self.run_command(
            [sys.executable, 'main.py', 'analyze'],
            "分析和发送邮件",
            cwd=project_dir
        )

        if not analyze_success:
            logger.warning("分析流程失败")

        self.report_data['training_success'] = schedule_success
        return schedule_success

    def attempt_repairs(self, output):
        """根据错误尝试自动修复"""
        logger.info("分析错误并尝试修复...")

        error_text = '\n'.join(output)

        # 常见错误类型检查和修复
        if 'ModuleNotFoundError' in error_text:
            logger.info("检测到缺少依赖，尝试安装...")
            self.report_data['fixes_applied'].append("尝试安装缺失的依赖包")
            self.run_command(
                [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                "安装依赖",
                cwd=Path(__file__).parent
            )

        if 'PermissionError' in error_text:
            logger.info("检测到权限问题")
            self.report_data['system_suggestions'].append("建议检查文件和目录权限")

        if 'MemoryError' in error_text or 'OOM' in error_text.upper():
            logger.info("检测到内存问题")
            self.report_data['system_suggestions'].append("建议增加系统内存或使用顺序训练模式")

    def generate_report(self):
        """生成最终报告"""
        logger.info("\n" + "="*70)
        logger.info("生成执行报告")
        logger.info("="*70)

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        report_content = []
        report_content.append("="*70)
        report_content.append("PL5 日循环训练自动化执行报告")
        report_content.append("="*70)
        report_content.append(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_content.append(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_content.append(f"总耗时: {duration:.2f} 秒")
        report_content.append("")

        report_content.append("1. 训练状态")
        report_content.append("-"*70)
        report_content.append(f"训练成功: {'是' if self.report_data['training_success'] else '否'}")
        report_content.append("")

        report_content.append("2. 性能问题")
        report_content.append("-"*70)
        if self.report_data['performance_issues']:
            for issue in self.report_data['performance_issues']:
                report_content.append(f"  - {issue}")
        else:
            report_content.append("  未发现性能问题")
        report_content.append("")

        report_content.append("3. 代码质量问题")
        report_content.append("-"*70)
        if self.report_data['code_quality_issues']:
            for issue in self.report_data['code_quality_issues']:
                report_content.append(f"  - {issue}")
        else:
            report_content.append("  未发现代码质量问题")
        report_content.append("")

        report_content.append("4. 已执行的修复")
        report_content.append("-"*70)
        if self.report_data['fixes_applied']:
            for fix in self.report_data['fixes_applied']:
                report_content.append(f"  - {fix}")
        else:
            report_content.append("  无需修复")
        report_content.append("")

        report_content.append("5. 系统警告")
        report_content.append("-"*70)
        if self.report_data['system_warnings']:
            for warning in self.report_data['system_warnings'][:20]:  # 只显示前20个
                report_content.append(f"  - {warning}")
            if len(self.report_data['system_warnings']) > 20:
                report_content.append(f"  ... (还有 {len(self.report_data['system_warnings']) - 20} 个警告)")
        else:
            report_content.append("  无警告")
        report_content.append("")

        report_content.append("6. 系统错误")
        report_content.append("-"*70)
        if self.report_data['system_errors']:
            for error in self.report_data['system_errors'][:20]:  # 只显示前20个
                report_content.append(f"  - {error}")
            if len(self.report_data['system_errors']) > 20:
                report_content.append(f"  ... (还有 {len(self.report_data['system_errors']) - 20} 个错误)")
        else:
            report_content.append("  无错误")
        report_content.append("")

        report_content.append("7. 系统建议")
        report_content.append("-"*70)
        if self.report_data['system_suggestions']:
            for suggestion in self.report_data['system_suggestions']:
                report_content.append(f"  - {suggestion}")
        else:
            report_content.append("  无特殊建议")
        report_content.append("")

        report_content.append("="*70)
        report_content.append("报告结束")
        report_content.append("="*70)

        # 写入报告文件
        with open(REPORT_PATH, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_content))

        # 打印报告
        for line in report_content:
            logger.info(line)

        logger.info(f"\n报告已保存至: {REPORT_PATH}")
        return REPORT_PATH


def main():
    """主函数"""
    executor = AutomationExecutor()

    try:
        # 执行完整流程
        success = executor.execute_full_pipeline()

        # 生成报告
        report_path = executor.generate_report()

        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("用户中断执行")
        return 130
    except Exception as e:
        logger.error(f"执行器异常: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
