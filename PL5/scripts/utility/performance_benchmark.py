#!/usr/bin/env python3
"""
系统性能基准测试脚本
测试PL5系统的各个模块性能
"""

import time
import cProfile
import pstats
import memory_profiler
import sys
import os
sys.path.insert(0, '.')

from src.core.orchestrator import PL5Orchestrator
from src.core.utils import logger


import asyncio

def benchmark_training():
    """基准测试训练流程"""
    print("\n=== 训练流程基准测试 ===")
    
    # 测量内存使用的函数
    def training_memory_test():
        async def run_training():
            orchestrator = PL5Orchestrator()
            result = await orchestrator.execute_training_pipeline()
            orchestrator.shutdown()
            return result
        return asyncio.run(run_training())
    
    # 测量内存使用
    memory_result = memory_profiler.memory_usage(proc=training_memory_test, interval=0.1, timeout=60)
    print(f"内存使用情况: 最小={min(memory_result):.2f}MB, 最大={max(memory_result):.2f}MB, 平均={sum(memory_result)/len(memory_result):.2f}MB")
    
    # 测量执行时间
    start_time = time.time()
    result = training_memory_test()
    execution_time = time.time() - start_time
    
    print(f"\n训练流程总耗时: {execution_time:.2f}秒")
    if result['success']:
        accuracy = result['results']['model_evaluation']['evaluation']['overall_accuracy']
        print(f"训练准确率: {accuracy:.4f}")
    else:
        print(f"训练失败: {result['error']}")
    
    return result


def benchmark_prediction():
    """基准测试预测流程"""
    print("\n=== 预测流程基准测试 ===")
    
    # 测量内存使用的函数
    def prediction_memory_test():
        async def run_prediction():
            orchestrator = PL5Orchestrator()
            result = await orchestrator.execute_prediction_pipeline()
            orchestrator.shutdown()
            return result
        return asyncio.run(run_prediction())
    
    # 测量内存使用
    memory_result = memory_profiler.memory_usage(proc=prediction_memory_test, interval=0.1, timeout=60)
    print(f"内存使用情况: 最小={min(memory_result):.2f}MB, 最大={max(memory_result):.2f}MB, 平均={sum(memory_result)/len(memory_result):.2f}MB")
    
    # 测量执行时间
    start_time = time.time()
    result = prediction_memory_test()
    execution_time = time.time() - start_time
    
    print(f"\n预测流程总耗时: {execution_time:.2f}秒")
    if result['success']:
        print(f"预测期号: {result['next_period']}")
    else:
        print(f"预测失败: {result['error']}")
    
    return result


def profile_training():
    """使用cProfile分析训练流程"""
    print("\n=== 训练流程详细性能分析 ===")
    
    async def profile_task():
        orchestrator = PL5Orchestrator()
        result = await orchestrator.execute_training_pipeline()
        orchestrator.shutdown()
        return result
    
    def run_async():
        asyncio.run(profile_task())
    
    # 使用cProfile分析
    cProfile.run('run_async()', 'training_profile.out')
    
    # 分析结果
    print("\n性能分析结果（累计时间）:")
    p = pstats.Stats('training_profile.out')
    p.strip_dirs().sort_stats('cumulative').print_stats(20)
    
    print("\n性能分析结果（执行时间）:")
    p.strip_dirs().sort_stats('time').print_stats(20)


def analyze_system_resources():
    """分析系统资源使用情况"""
    print("\n=== 系统资源分析 ===")
    
    # 检查模型文件大小
    print("\n模型文件大小:")
    models_dir = "models"
    if os.path.exists(models_dir):
        for file in os.listdir(models_dir):
            if file.endswith('.pkl'):
                file_path = os.path.join(models_dir, file)
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"{file}: {size_mb:.2f} MB")
    
    # 检查数据文件大小
    print("\n数据文件大小:")
    data_dir = "data/processed"
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            file_path = os.path.join(data_dir, file)
            if os.path.isfile(file_path):
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"{file}: {size_mb:.2f} MB")


def main():
    """主函数"""
    print("PL5系统性能基准测试")
    print("=" * 60)
    
    # 执行基准测试
    training_result = benchmark_training()
    prediction_result = benchmark_prediction()
    
    # 执行详细性能分析
    profile_training()
    
    # 分析系统资源
    analyze_system_resources()
    
    print("\n" + "=" * 60)
    print("性能基准测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
