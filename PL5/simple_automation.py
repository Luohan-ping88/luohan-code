#!/usr/bin/env python
"""简单版自动化执行脚本"""
import sys
import os
import time
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
LOG_DIR = Path("/workspace/PL5/logs")
LOG_DIR.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'simple_automation_{timestamp}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_command(cmd, description):
    """运行命令并返回结果"""
    logger.info(f"\n{'='*60}")
    logger.info(f"执行: {description}")
    logger.info(f"命令: {cmd}")
    logger.info(f"{'='*60}")
    
    start_time = time.time()
    result = os.system(cmd)
    elapsed = time.time() - start_time
    
    if result == 0:
        logger.info(f"✅ {description} 成功完成 (耗时: {elapsed:.2f}s)")
        return True
    else:
        logger.error(f"❌ {description} 失败 (返回码: {result}, 耗时: {elapsed:.2f}s)")
        return False


def main():
    """主函数"""
    os.chdir("/workspace/PL5")
    logger.info(f"工作目录: {os.getcwd()}")
    
    # 记录开始
    start_time = time.time()
    logger.info("="*80)
    logger.info("PL5 日循环训练开始")
    logger.info("="*80)
    
    # 步骤1: 运行训练
    train_success = run_command(f"{sys.executable} main.py train", "模型训练")
    
    # 步骤2: 如果训练成功，运行预测
    predict_success = True
    if train_success:
        predict_success = run_command(f"{sys.executable} main.py predict", "预测生成")
    else:
        logger.warning("跳过预测，因为训练失败")
    
    # 步骤3: 如果预测成功，运行分析和邮件
    analyze_success = True
    if predict_success:
        analyze_success = run_command(f"{sys.executable} main.py analyze", "分析和报告")
    else:
        logger.warning("跳过分析，因为预测失败")
    
    # 生成总结报告
    total_elapsed = time.time() - start_time
    overall_success = train_success and predict_success and analyze_success
    
    report_file = LOG_DIR / f"simple_report_{timestamp}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write("PL5 日循环训练报告\n")
        f.write("="*80 + "\n")
        f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总耗时: {total_elapsed:.2f}秒\n\n")
        f.write("执行结果:\n")
        f.write(f"  - 模型训练: {'✅ 成功' if train_success else '❌ 失败'}\n")
        f.write(f"  - 预测生成: {'✅ 成功' if predict_success else '❌ 失败'}\n")
        f.write(f"  - 分析报告: {'✅ 成功' if analyze_success else '❌ 失败'}\n")
        f.write(f"\n总体状态: {'✅ 全部成功' if overall_success else '❌ 存在失败'}\n")
        f.write("="*80 + "\n")
    
    logger.info(f"\n报告已保存: {report_file}")
    logger.info(f"总耗时: {total_elapsed:.2f}秒")
    logger.info(f"总体状态: {'✅ 成功' if overall_success else '❌ 失败'}")
    
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
