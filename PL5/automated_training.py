#!/usr/bin/env python
"""
PL5 日循环训练自动化执行脚本
监控系统性能、检测问题、自动修复并生成报告
"""

import os
import sys
import time
import psutil
import logging
import subprocess
import json
from datetime import datetime
from pathlib import Path

# 配置日志
LOG_DIR = Path("/workspace/PL5/logs")
LOG_DIR.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_FILE = LOG_DIR / f"automation_report_{timestamp}.txt"

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'automation_{timestamp}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 报告数据
report_data = {
    "execution_time": timestamp,
    "training_success": False,
    "performance_issues": [],
    "code_quality_issues": [],
    "fixes_applied": [],
    "system_errors": [],
    "recommendations": []
}


class SystemMonitor:
    """系统性能监控器"""
    
    def __init__(self):
        self.start_time = None
        self.process = None
    
    def start(self):
        """开始监控"""
        self.start_time = time.time()
        logger.info("开始系统性能监控")
    
    def get_metrics(self):
        """获取当前系统指标"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/workspace')
        
        metrics = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": memory.used / (1024 ** 3),
            "disk_percent": disk.percent,
            "disk_used_gb": disk.used / (1024 ** 3),
            "disk_free_gb": disk.free / (1024 ** 3)
        }
        
        # 检查性能问题
        if cpu_percent > 90:
            report_data["performance_issues"].append(f"高CPU使用率: {cpu_percent}%")
        if memory.percent > 90:
            report_data["performance_issues"].append(f"高内存使用率: {memory.percent}%")
        if disk.percent > 90:
            report_data["performance_issues"].append(f"高磁盘使用率: {disk.percent}%")
        
        return metrics
    
    def stop(self):
        """停止监控"""
        elapsed = time.time() - self.start_time
        logger.info(f"监控结束，总耗时: {elapsed:.2f}秒")
        return elapsed


def run_command(cmd, description, cwd="/workspace/PL5"):
    """执行命令并监控"""
    logger.info(f"\n{'='*60}")
    logger.info(f"执行: {description}")
    logger.info(f"命令: {cmd}")
    logger.info(f"{'='*60}")
    
    monitor = SystemMonitor()
    monitor.start()
    
    try:
        process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 实时输出
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            line = line.rstrip()
            print(line)
            output_lines.append(line)
            
            # 检测警告和错误
            if 'WARNING' in line.upper() or 'WARN' in line.upper():
                report_data["system_errors"].append(f"警告: {line}")
            if 'ERROR' in line.upper() or 'EXCEPTION' in line.upper() or 'TRACEBACK' in line.upper():
                report_data["system_errors"].append(f"错误: {line}")
        
        process.wait()
        elapsed = monitor.stop()
        
        if process.returncode == 0:
            logger.info(f"✅ {description} 执行成功 (耗时: {elapsed:.2f}s)")
            return True, output_lines
        else:
            logger.error(f"❌ {description} 执行失败 (返回码: {process.returncode})")
            report_data["system_errors"].append(f"{description} 失败，返回码: {process.returncode}")
            return False, output_lines
            
    except Exception as e:
        elapsed = monitor.stop()
        logger.error(f"❌ {description} 执行异常: {e}")
        report_data["system_errors"].append(f"{description} 异常: {str(e)}")
        return False, [str(e)]


def check_code_quality():
    """检查代码质量"""
    logger.info("\n检查代码质量...")
    
    # 检查是否有常见的代码问题
    issues = []
    
    # 检查语法
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "main.py"],
            cwd="/workspace/PL5",
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            issues.append("main.py 存在语法错误")
    except Exception as e:
        issues.append(f"代码检查异常: {e}")
    
    # 检查依赖
    try:
        import numpy
        import pandas
        import catboost
    except ImportError as e:
        issues.append(f"缺少依赖: {e}")
        report_data["fixes_applied"].append(f"检测到依赖问题，建议运行 pip install -r requirements.txt")
    
    report_data["code_quality_issues"] = issues
    return len(issues) == 0


def attempt_recovery():
    """尝试恢复/修复常见问题"""
    logger.info("\n尝试自动修复...")
    fixes = []
    
    # 确保目录存在
    dirs_to_check = ['data/raw', 'data/processed', 'models', 'logs', 'results']
    for d in dirs_to_check:
        dir_path = Path(f"/workspace/PL5/{d}")
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            fixes.append(f"创建目录: {d}")
    
    # 检查依赖
    requirements_path = Path("/workspace/PL5/requirements.txt")
    if requirements_path.exists():
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                cwd="/workspace/PL5",
                capture_output=True,
                timeout=300
            )
            if result.returncode == 0:
                fixes.append("检查并安装了依赖")
        except Exception as e:
            fixes.append(f"依赖安装跳过: {e}")
    
    report_data["fixes_applied"].extend(fixes)
    return fixes


def generate_report():
    """生成最终报告"""
    logger.info(f"\n生成报告: {REPORT_FILE}")
    
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("PL5 日循环训练自动化执行报告\n")
        f.write("=" * 80 + "\n")
        f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("1. 训练状态\n")
        f.write("-" * 40 + "\n")
        f.write(f"整体成功: {'✅ 是' if report_data['training_success'] else '❌ 否'}\n\n")
        
        f.write("2. 性能问题\n")
        f.write("-" * 40 + "\n")
        if report_data["performance_issues"]:
            for issue in report_data["performance_issues"]:
                f.write(f"  - {issue}\n")
        else:
            f.write("  无\n")
        f.write("\n")
        
        f.write("3. 代码质量问题\n")
        f.write("-" * 40 + "\n")
        if report_data["code_quality_issues"]:
            for issue in report_data["code_quality_issues"]:
                f.write(f"  - {issue}\n")
        else:
            f.write("  无\n")
        f.write("\n")
        
        f.write("4. 已执行的修复\n")
        f.write("-" * 40 + "\n")
        if report_data["fixes_applied"]:
            for fix in report_data["fixes_applied"]:
                f.write(f"  - {fix}\n")
        else:
            f.write("  无\n")
        f.write("\n")
        
        f.write("5. 系统错误和警告\n")
        f.write("-" * 40 + "\n")
        if report_data["system_errors"]:
            for i, error in enumerate(report_data["system_errors"][:50], 1):  # 限制数量
                f.write(f"  {i}. {error}\n")
        else:
            f.write("  无\n")
        f.write("\n")
        
        f.write("6. 系统建议\n")
        f.write("-" * 40 + "\n")
        if report_data["recommendations"]:
            for rec in report_data["recommendations"]:
                f.write(f"  - {rec}\n")
        else:
            # 默认建议
            f.write("  - 定期清理日志文件\n")
            f.write("  - 监控系统资源使用情况\n")
            f.write("  - 定期备份模型和数据\n")
        f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("报告结束\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"报告已保存: {REPORT_FILE}")
    return REPORT_FILE


def main():
    """主执行流程"""
    logger.info("=" * 80)
    logger.info("PL5 日循环训练自动化任务启动")
    logger.info("=" * 80)
    
    # 切换目录
    os.chdir("/workspace/PL5")
    logger.info(f"当前目录: {os.getcwd()}")
    
    # 预检查和修复
    attempt_recovery()
    check_code_quality()
    
    # 步骤1: 执行完整日循环训练
    success1, _ = run_command(
        f"{sys.executable} main.py schedule --once",
        "完整日循环训练流程 (schedule --once)"
    )
    
    # 步骤2: 执行预测
    success2 = True
    if success1:
        success2, _ = run_command(
            f"{sys.executable} main.py predict",
            "预测流程 (predict)"
        )
    else:
        logger.warning("跳过预测流程，因为训练失败")
        report_data["recommendations"].append("检查训练流程中的错误")
    
    # 步骤3: 执行分析和邮件
    success3 = True
    if success2:
        success3, _ = run_command(
            f"{sys.executable} main.py analyze",
            "分析和邮件发送流程 (analyze)"
        )
    else:
        logger.warning("跳过分析流程，因为预测失败")
    
    # 总体成功状态
    report_data["training_success"] = success1 and success2 and success3
    
    # 生成报告
    generate_report()
    
    # 总结
    logger.info("\n" + "=" * 80)
    logger.info("任务执行总结")
    logger.info("=" * 80)
    logger.info(f"训练流程: {'✅ 成功' if success1 else '❌ 失败'}")
    logger.info(f"预测流程: {'✅ 成功' if success2 else '❌ 失败'}")
    logger.info(f"分析流程: {'✅ 成功' if success3 else '❌ 跳过/失败'}")
    logger.info(f"报告文件: {REPORT_FILE}")
    logger.info("=" * 80)
    
    return 0 if report_data["training_success"] else 1


if __name__ == "__main__":
    sys.exit(main())
