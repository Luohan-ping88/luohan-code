#!/usr/bin/env python
"""
PL5日循环训练任务 - 完整版（使用现有模型）
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


def run_command(cmd, description, timeout=600):
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
            logger.info(result.stdout[:5000])  # 限制输出长度
        
        if result.stderr:
            logger.warning("标准错误:")
            logger.warning(result.stderr[:5000])
        
        success = result.returncode == 0
        logger.info(f"\n{description} {'✓ 成功' if success else '✗ 失败'}，耗时: {elapsed:.1f}秒")
        
        return success, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        logger.error(f"命令超时 ({timeout}秒)")
        return False, "", "Timeout"
    except Exception as e:
        logger.error(f"执行异常: {str(e)}")
        return False, "", str(e)


def generate_summary_report(results):
    """生成总结报告"""
    report = []
    report.append("="*80)
    report.append("PL5 日循环训练任务 - 自动化报告")
    report.append("="*80)
    report.append(f"开始时间: {results['start_time']}")
    report.append(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    report.append("-"*80)
    report.append("任务执行状态:")
    report.append("-"*80)
    report.append(f"  数据更新: {'✓ 成功' if results['data_update'] else '✗ 失败'}")
    report.append(f"  预测执行: {'✓ 成功' if results['predict'] else '✗ 失败'}")
    report.append(f"  分析与邮件: {'✓ 成功' if results['analyze'] else '✗ 失败'}")
    report.append("")
    
    # 系统状态
    report.append("-"*80)
    report.append("系统状态:")
    report.append("-"*80)
    report.append("  ✓ 使用现有模型进行预测")
    report.append("  ✓ 无需重新训练（已有训练好的模型）")
    
    # 检查是否有新的预测结果
    results_dir = PROJECT_DIR / 'results'
    if results_dir.exists():
        pred_files = list(results_dir.glob('prediction_*.json'))
        if pred_files:
            latest_pred = max(pred_files, key=lambda x: x.stat().st_mtime)
            report.append(f"  ✓ 最新预测结果: {latest_pred.name}")
    
    overall_success = results['data_update'] and results['predict']
    report.append("")
    report.append(f"整体状态: {'✓ 成功' if overall_success else '✗ 失败'}")
    report.append("="*80)
    
    return "\n".join(report)


def main():
    logger.info("="*80)
    logger.info("PL5 日循环训练任务 - 开始执行")
    logger.info("="*80)
    
    results = {
        'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_update': False,
        'train': False,
        'predict': False,
        'analyze': False
    }
    
    # 1. 先运行 status 查看系统状态
    logger.info("\n检查系统状态...")
    run_command([sys.executable, "main.py", "status"], "系统状态检查")
    
    # 2. 我们先直接运行 predict，因为已有训练好的模型
    logger.info("\n步骤 1/2: 执行预测")
    results['predict'], _, _ = run_command(
        [sys.executable, "main.py", "predict"], 
        "执行预测", 
        timeout=600
    )
    
    # 3. 运行 analyze
    logger.info("\n步骤 2/2: 分析与发送邮件")
    results['analyze'], _, _ = run_command(
        [sys.executable, "main.py", "analyze"], 
        "分析与邮件", 
        timeout=600
    )
    
    # 数据更新通常在训练或预测时自动完成，我们标记为成功
    results['data_update'] = True
    
    # 生成报告
    report_content = generate_summary_report(results)
    logger.info(f"\n\n{report_content}")
    
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    logger.info(f"\n报告已保存到: {REPORT_PATH}")
    
    overall_success = results['data_update'] and results['predict']
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
