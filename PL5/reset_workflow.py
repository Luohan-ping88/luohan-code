#!/usr/bin/env python3
"""
重置工作流状态脚本
"""

import os
import pickle
from src.core.workflow import IntelligentWorkflowOrchestrator

# 重置工作流状态
orchestrator = IntelligentWorkflowOrchestrator()
orchestrator.reset_workflow()

print("工作流状态已重置")
print("系统将重新检测今天的任务")