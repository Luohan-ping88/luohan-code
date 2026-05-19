#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重置工作流状态并检查修复问题
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.workflow.orchestrator import IntelligentWorkflowOrchestrator
from src.core.config import LOGS_DIR

if __name__ == "__main__":
    print("="*80)
    print("重置工作流状态")
    print("="*80)
    
    print("\n1. 重置工作流状态...")
    orchestrator = IntelligentWorkflowOrchestrator()
    orchestrator.reset_workflow()
    print("[OK] 工作流状态已重置")
    
    print("\n2. 检查目录结构...")
    print(f"LOGS_DIR: {LOGS_DIR}")
    print(f"  存在: {LOGS_DIR.exists()}")
    
    from src.core.config import MODELS_DIR, DATA_DIR
    print(f"MODELS_DIR: {MODELS_DIR}")
    print(f"  存在: {MODELS_DIR.exists()}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"  存在: {DATA_DIR.exists()}")
    
    print("\n3. 检查导入...")
    try:
        from src.core.utils.logger import log_performance_metric
        print("[OK] log_performance_metric 导入成功")
    except Exception as e:
        print(f"[ERROR] log_performance_metric 导入失败: {e}")
    
    try:
        from src.core.config import MODELS_DIR, LOGS_DIR, DATA_DIR
        print(f"[OK] 配置导入成功: MODELS_DIR={MODELS_DIR}")
    except Exception as e:
        print(f"[ERROR] 配置导入失败: {e}")
    
    print("\n" + "="*80)
    print("重置完成！系统已准备好重新启动。")
    print("="*80)
