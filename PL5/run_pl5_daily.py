#!/usr/bin/env python
"""
PL5日循环训练任务 - 简化版自动化脚本
"""

import sys
import os
import subprocess
import time
import logging
from datetime import datetime
from pathlib import Path

# 设置项目路径
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

# 配置日志
LOG_DIR = PROJECT_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
REPORT_PATH = LOG_DIR / f'automation_report_{timestamp}.txt'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_command(cmd, description, timeout=300):
    """运行命令并返回结果"""
    logger.info(f"\n{'='*80}")
    logger.info(f"执行: {description}")
    logger.info(f"命令: {' '.join(cmd)}")
    logger.info(f"{'='*80}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=timeout
        )
        
        elapsed = time.time() - start_time
        
        if result.stdout:
            logger.info("标准输出:")
            logger.info(result.stdout)
        
        if result.stderr:
            logger.warning("标准错误:")
            logger.warning(result.stderr)
        
        success = result.returncode == 0
        logger.info(f"\n{description} {'✓ 成功' if success else '✗ 失败'}，耗时: {elapsed:.1f}秒")
        
        return success, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        logger.error(f"命令超时 ({timeout}秒)")
        return False, "", "Timeout"
    except Exception as e:
        logger.error(f"执行异常: {str(e)}")
        return False, "", str(e)


def main():
    logger.info("="*80)
    logger.info("PL5 日循环训练任务 - 开始执行")
    logger.info("="*80)
    
    report = []
    report.append("="*80)
    report.append("PL5 日循环训练任务 - 自动化报告")
    report.append("="*80)
    report.append(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 1. 训练
    logger.info("\n步骤 1/3: 训练模型")
    train_success, train_out, train_err = run_command(
        [sys.executable, "main.py", "train"],
        "模型训练"
    )
    report.append(f"模型训练: {'✓ 成功' if train_success else '✗ 失败'}")
    
    # 2. 预测
    logger.info("\n步骤 2/3: 执行预测")
    predict_success, predict_out, predict_err = run_command(
        [sys.executable, "main.py", "predict"],
        "执行预测"
    )
    report.append(f"预测执行: {'✓ 成功' if predict_success else '✗ 失败'}")
    
    # 3. 分析与邮件
    logger.info("\n步骤 3/3: 分析与发送邮件")
    analyze_success, analyze_out, analyze_err = run_command(
        [sys.executable, "main.py", "analyze"],
        "分析与邮件"
    )
    report.append(f"分析与邮件: {'✓ 成功' if analyze_success else '✗ 失败'}")
    
    # 生成报告
    overall_success = train_success and predict_success
    report.append("")
    report.append(f"整体状态: {'✓ 成功' if overall_success else '✗ 失败'}")
    report.append(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("="*80)
    
    # 保存报告
    report_content = "\n".join(report)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    logger.info(f"\n\n{report_content}")
    logger.info(f"\n报告已保存到: {REPORT_PATH}")
    
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
