#!/usr/bin/env python3
"""重置今日工作流状态 - 让系统从干净状态重新开始"""

import os
import sys
import pickle
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# 工作流状态文件
WORKFLOW_STATE_FILE = "logs/workflow_state.pkl"

def reset_workflow():
    """重置工作流状态"""
    
    if not os.path.exists(WORKFLOW_STATE_FILE):
        logger.info("工作流状态文件不存在，无需重置")
        return
    
    logger.info(f"正在读取现有工作流状态: {WORKFLOW_STATE_FILE}")
    
    try:
        with open(WORKFLOW_STATE_FILE, 'rb') as f:
            state = pickle.load(f)
    except Exception as e:
        logger.error(f"读取失败: {e}")
        return
    
    logger.info(f"现有工作流状态: workflow_status={state.get('workflow_status')}")
    logger.info(f"现有任务状态:")
    for task_name, task_data in state.get('tasks', {}).items():
        status = task_data.get('status')
        last_exec = task_data.get('last_executed_time')
        logger.info(f"  {task_name}: status={status}, last_exec={last_exec}")
    
    # 备份现有状态
    backup_file = f"logs/workflow_state_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
    logger.info(f"备份现有状态到: {backup_file}")
    with open(backup_file, 'wb') as f:
        pickle.dump(state, f)
    
    # 重置所有任务为 pending
    for task_name in state.get('tasks', {}):
        state['tasks'][task_name] = {
            'status': 'pending',
            'start_time': None,
            'end_time': None,
            'result': None,
            'error': None,
            'retry_count': 0,
            'last_executed_time': None,
            'is_missed': False
        }
    
    # 重置工作流状态
    state['workflow_status'] = 'idle'
    state['current_task'] = None
    state['missed_tasks'] = []
    state['updated_at'] = datetime.now().isoformat()
    
    # 保存重置后的状态
    logger.info("保存重置后的工作流状态")
    with open(WORKFLOW_STATE_FILE, 'wb') as f:
        pickle.dump(state, f)
    
    logger.info("工作流状态已重置完成！")
    logger.info("现在可以重启系统，从干净状态开始")

if __name__ == "__main__":
    logger.info("="*80)
    logger.info("重置今日工作流状态")
    logger.info("="*80)
    reset_workflow()
    logger.info("="*80)
