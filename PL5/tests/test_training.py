"""
测试训练流程是否能够正常完成
"""

import asyncio
from src.core.orchestrator import PL5Orchestrator


async def main():
    # 初始化编排器
    orchestrator = PL5Orchestrator()

    # 执行训练流程
    print("开始训练流程...")
    try:
        result = await orchestrator.execute_training_pipeline()
        if result["success"]:
            print("训练流程执行成功！")
            print(f"总耗时: {result['execution_time']:.2f}秒")
            print(f"数据处理: {result['results']['data_processing']['success']}")
            print(f"特征工程: {result['results']['feature_engineering']['success']}")
            print(f"模型训练: {result['results']['model_training']['success']}")
            print(f"模型评估: {result['results']['model_evaluation']['success']}")
            print(f"报告生成: {result['results']['report_generation']['success']}")
        else:
            print(f"训练流程执行失败: {result['error']}")
    except Exception as e:
        print(f"训练流程执行异常: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
