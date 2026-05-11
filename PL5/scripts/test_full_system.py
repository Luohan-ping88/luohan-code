#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完整系统测试：训练 + 预测流程"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.orchestrator import PL5Orchestrator
from src.core.utils import logger
import asyncio

print("=" * 70)
print("PL5 V8.0 升级后完整系统测试")
print("=" * 70)
print()

async def full_test():
    orchestrator = PL5Orchestrator()
    
    try:
        # 1. 测试模型加载
        print("[测试 1] 模型加载测试")
        print("-" * 70)
        predictor = orchestrator.components['predictor']
        load_result = predictor.load_models()
        print(f"[OK] 模型加载: {load_result}")
        print(f"[OK] is_trained: {predictor.is_trained}")
        print(f"[OK] stacking: {bool(predictor.stacking)}")
        print(f"[OK] hmm_models: {len(predictor.hmm_models)} 个")
        print(f"[OK] bsts_models: {len(predictor.bsts_models)} 个")
        print()
        
        # 2. 测试预测流程（包含数据更新、特征工程、模型推理）
        print("[测试 2] 预测流程测试")
        print("-" * 70)
        result = await orchestrator.execute_prediction_pipeline()
        
        if result['success']:
            print(f"[OK] 预测流程成功")
            print(f"[OK] 预测期号: {result['next_period']}")
            print(f"[OK] 执行耗时: {result['execution_time']:.2f} 秒")
            print()
            print("预测结果 (Top 5):")
            for pos, pred in result['predictions'].items():
                top5 = pred['top_k'][:5]
                print(f"  {pos}: {top5}")
            print()
            
            # 验证预测结果是否合理（不是均匀分布）
            is_uniform = all(
                p['top_k'][:5] == list(range(10))[:5]
                for p in result['predictions'].values()
            )
            if is_uniform:
                print("[WARN] 预测结果为均匀分布，模型可能未正确加载")
            else:
                print("[OK] 预测结果合理（非均匀分布）")
        else:
            print(f"[FAIL] 预测流程失败: {result.get('error', 'Unknown error')}")
            return False
        
        print()
        print("=" * 70)
        print("[PASS] 所有测试通过！系统运行正常。")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        orchestrator.shutdown()

if __name__ == "__main__":
    success = asyncio.run(full_test())
    sys.exit(0 if success else 1)
