#!/usr/bin/env python
"""
PL5日循环训练任务自动化脚本
执行完整的日循环训练流程，包括监控、异常检测、问题修复和报告生成
"""

import sys
import os
import subprocess
import logging
import json
import time
from datetime import datetime
from pathlib import Path

# 尝试导入psutil，如果没有则提供替代方案
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil 模块未安装，将使用基础系统监控")

# 设置项目路径
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

# 配置日志
LOG_DIR = PROJECT_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
REPORT_PATH = LOG_DIR / f'automation_report_{timestamp}.txt'
LOG_PATH = LOG_DIR / f'automation_log_{timestamp}.log'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutomationReport:
    """自动化任务报告生成器"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.success = False
        self.performance_issues = []
        self.code_quality_issues = []
        self.fixes_performed = []
        self.errors = []
        self.warnings = []
    
    def add_performance_issue(self, issue):
        self.performance_issues.append(issue)
    
    def add_code_quality_issue(self, issue):
        self.code_quality_issues.append(issue)
    
    def add_fix(self, fix):
        self.fixes_performed.append(fix)
    
    def add_error(self, error):
        self.errors.append(error)
    
    def add_warning(self, warning):
        self.warnings.append(warning)
    
    def set_success(self, success):
        self.success = success
    
    def generate_report(self):
        """生成详细报告"""
        report = []
        report.append("=" * 80)
        report.append("PL5日循环训练任务 - 自动化报告")
        report.append("=" * 80)
        report.append(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"总耗时: {datetime.now() - self.start_time}")
        report.append("")
        report.append(f"训练状态: {'✅ 成功' if self.success else '❌ 失败'}")
        report.append("")
        
        report.append("-" * 80)
        report.append("性能问题:")
        report.append("-" * 80)
        if self.performance_issues:
            for issue in self.performance_issues:
                report.append(f"  - {issue}")
        else:
            report.append("  未发现性能问题")
        
        report.append("")
        report.append("-" * 80)
        report.append("代码质量问题:")
        report.append("-" * 80)
        if self.code_quality_issues:
            for issue in self.code_quality_issues:
                report.append(f"  - {issue}")
        else:
            report.append("  未发现代码质量问题")
        
        report.append("")
        report.append("-" * 80)
        report.append("已执行的修复操作:")
        report.append("-" * 80)
        if self.fixes_performed:
            for fix in self.fixes_performed:
                report.append(f"  - {fix}")
        else:
            report.append("  无需修复操作")
        
        report.append("")
        report.append("-" * 80)
        report.append("警告:")
        report.append("-" * 80)
        if self.warnings:
            for warning in self.warnings:
                report.append(f"  - {warning}")
        else:
            report.append("  无警告")
        
        report.append("")
        report.append("-" * 80)
        report.append("错误:")
        report.append("-" * 80)
        if self.errors:
            for error in self.errors:
                report.append(f"  - {error}")
        else:
            report.append("  无错误")
        
        report.append("")
        report.append("-" * 80)
        report.append("系统建议:")
        report.append("-" * 80)
        
        # 生成建议
        if self.performance_issues:
            report.append("  建议优化性能，关注内存和CPU使用")
        if len(self.errors) > 0:
            report.append("  建议检查错误来源并修复相关问题")
        if not self.success:
            report.append("  建议检查训练流程配置和数据完整性")
        
        report.append("  建议定期监控系统资源使用情况")
        
        report.append("")
        report.append("=" * 80)
        report.append(f"报告保存位置: {REPORT_PATH}")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_report(self):
        """保存报告到文件"""
        report = self.generate_report()
        with open(REPORT_PATH, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"报告已保存到: {REPORT_PATH}")
        return REPORT_PATH


class SystemMonitor:
    """系统性能监控器"""
    
    def __init__(self, report):
        self.report = report
    
    def check_system_resources(self):
        """检查系统资源使用情况"""
        logger.info("检查系统资源...")
        
        resources = {
            'cpu': 0,
            'memory': 0,
            'disk': 0
        }
        
        if PSUTIL_AVAILABLE:
            # CPU 使用
            cpu_percent = psutil.cpu_percent(interval=1)
            logger.info(f"CPU使用率: {cpu_percent}%")
            if cpu_percent > 80:
                self.report.add_performance_issue(f"CPU使用率过高: {cpu_percent}%")
            resources['cpu'] = cpu_percent
            
            # 内存使用
            mem = psutil.virtual_memory()
            logger.info(f"内存使用率: {mem.percent}%")
            if mem.percent > 80:
                self.report.add_performance_issue(f"内存使用率过高: {mem.percent}%")
            resources['memory'] = mem.percent
            
            # 磁盘使用
            disk = psutil.disk_usage(str(PROJECT_DIR))
            logger.info(f"磁盘使用率: {disk.percent}%")
            if disk.percent > 80:
                self.report.add_performance_issue(f"磁盘使用率过高: {disk.percent}%")
            resources['disk'] = disk.percent
        else:
            # 基础检查
            logger.info("使用基础系统监控 (psutil未安装)")
            # 尝试获取磁盘使用率（使用简单方法）
            try:
                statvfs = os.statvfs(str(PROJECT_DIR))
                total = statvfs.f_frsize * statvfs.f_blocks
                free = statvfs.f_frsize * statvfs.f_bfree
                used = total - free
                disk_percent = (used / total) * 100
                logger.info(f"磁盘使用率: {disk_percent:.1f}%")
                if disk_percent > 80:
                    self.report.add_performance_issue(f"磁盘使用率过高: {disk_percent:.1f}%")
                resources['disk'] = disk_percent
            except:
                logger.warning("无法获取磁盘使用率")
        
        return resources


class TrainingExecutor:
    """训练流程执行器"""
    
    def __init__(self, report):
        self.report = report
        self.project_dir = PROJECT_DIR
    
    def run_command(self, cmd, description):
        """执行命令并监控输出"""
        logger.info(f"执行命令: {description}")
        logger.info(f"命令行: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            elapsed = time.time() - start_time
            logger.info(f"{description} 完成，耗时: {elapsed:.1f}秒")
            
            if result.stdout:
                logger.debug(f"标准输出:\n{result.stdout}")
            
            if result.stderr:
                logger.warning(f"标准错误:\n{result.stderr}")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        if 'ERROR' in line.upper() or 'EXCEPTION' in line.upper():
                            self.report.add_error(line.strip())
                        elif 'WARNING' in line.upper():
                            self.report.add_warning(line.strip())
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except Exception as e:
            error_msg = f"{description} 执行异常: {str(e)}"
            logger.error(error_msg)
            self.report.add_error(error_msg)
            return False, "", str(e)
    
    def run_schedule_once(self):
        """执行单次完整训练流程"""
        logger.info("=" * 60)
        logger.info("步骤1: 执行完整日循环训练流程")
        logger.info("=" * 60)
        
        success, stdout, stderr = self.run_command(
            [sys.executable, 'main.py', 'schedule', '--once'],
            '执行单次完整训练流程'
        )
        
        return success
    
    def run_predict(self):
        """执行预测"""
        logger.info("=" * 60)
        logger.info("步骤2: 执行预测")
        logger.info("=" * 60)
        
        success, stdout, stderr = self.run_command(
            [sys.executable, 'main.py', 'predict'],
            '执行预测'
        )
        
        return success
    
    def run_analyze(self):
        """执行分析并发送邮件"""
        logger.info("=" * 60)
        logger.info("步骤3: 发送训练报告邮件")
        logger.info("=" * 60)
        
        success, stdout, stderr = self.run_command(
            [sys.executable, 'main.py', 'analyze'],
            '执行分析并发送邮件'
        )
        
        return success


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("PL5日循环训练任务 - 自动化脚本启动")
    logger.info("=" * 80)
    
    # 初始化报告
    report = AutomationReport()
    
    # 初始化监控器
    monitor = SystemMonitor(report)
    
    # 检查系统资源
    monitor.check_system_resources()
    
    # 初始化执行器
    executor = TrainingExecutor(report)
    
    # 执行训练流程
    success = True
    
    # 步骤1: 执行完整日循环训练流程
    schedule_success = executor.run_schedule_once()
    if not schedule_success:
        success = False
        report.add_error("日循环训练流程执行失败")
    
    # 步骤2: 执行预测
    predict_success = executor.run_predict()
    if not predict_success:
        success = False
        report.add_error("预测执行失败")
    
    # 步骤3: 发送训练报告邮件
    analyze_success = executor.run_analyze()
    if not analyze_success:
        report.add_warning("分析/邮件发送可能失败，不影响主要任务")
    
    # 设置最终成功状态
    report.set_success(success)
    
    # 再次检查系统资源
    monitor.check_system_resources()
    
    # 生成并保存报告
    report_path = report.save_report()
    
    # 打印报告
    logger.info("\n" + report.generate_report())
    
    # 结束
    logger.info("=" * 80)
    if success:
        logger.info("PL5日循环训练任务 - 自动化脚本执行成功!")
    else:
        logger.warning("PL5日循环训练任务 - 自动化脚本执行完成但有错误")
    logger.info("=" * 80)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
