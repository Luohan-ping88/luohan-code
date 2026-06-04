
import os
import pickle
import sys
from datetime import datetime

# 切换到 PL5 目录
os.chdir('/workspace/PL5')

# 1. 重置工作流状态
print("重置工作流状态...")
try:
    if os.path.exists('logs/workflow_state.pkl'):
        os.remove('logs/workflow_state.pkl')
        print("已删除 workflow_state.pkl")
except Exception as e:
    print(f"删除失败: {e}")

# 2. 导入并启动调度器
print("启动日循环任务...")

# 添加当前目录到路径
sys.path.insert(0, '/workspace/PL5')

from src.app.auto_scheduler_v8 import AutoSchedulerV8

# 初始化调度器
scheduler = AutoSchedulerV8()

# 运行完整流程 (单次)
print("执行完整日循环流程...")
result = scheduler.run_full_pipeline()

print("\n=== 日循环执行完成 ===")
print(f"执行结果: {result}")

# 检查最终状态
if os.path.exists('logs/workflow_state.pkl'):
    with open('logs/workflow_state.pkl', 'rb') as f:
        state = pickle.load(f)
    print(f"工作流状态: {state}")
