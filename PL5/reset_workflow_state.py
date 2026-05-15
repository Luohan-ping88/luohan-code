#!/usr/bin/env python3
"""
重置工作流状态
"""

import sys
from pathlib import Path
import pickle

sys.path.insert(0, str(Path(__file__).parent))

from src.core.workflow.orchestrator import IntelligentWorkflowOrchestrator


def main():
    print("=" * 80)
    print("重置工作流状态")
    print("=" * 80)
    
    orchestrator = IntelligentWorkflowOrchestrator()
    
    print("\n当前状态:")
    state = orchestrator.get_current_workflow_state()
    print(f"  工作流状态: {state.get('workflow_status')}")
    print(f"  当前任务: {state.get('current_task')}")
    
    print("\n重置工作流...")
    orchestrator.reset_workflow()
    
    print("\n重置后状态:")
    state = orchestrator.get_current_workflow_state()
    print(f"  工作流状态: {state.get('workflow_status')}")
    print(f"  当前任务: {state.get('current_task')}")
    
    print("\n" + "=" * 80)
    print("✓ 工作流状态已重置")
    print("=" * 80)


if __name__ == "__main__":
    main()
