#!/usr/bin/env python3
"""
日志迁移工具 — 将旧版日志结构迁移到统一格式
执行：
  1. 移动业务 JSON → logs/data/
  2. 删除旧版冗余日志文件
  3. 备份旧日志到 logs/archive/
"""
import shutil
from pathlib import Path

BASE = Path(__file__).parent.parent
LOGS = BASE / 'logs'
DATA = LOGS / 'data'
ARCHIVE = LOGS / 'archive'

# ── 需要移到 data/ 的业务 JSON ──
BUSINESS_FILES = [
    'final_prediction.json',
    'pre_sale_prediction.json',
    'prediction_preview.json',
    'prediction_verification.json',
    'first_prediction_verification.json',
    'second_prediction_verification.json',
    'third_prediction_verification.json',
    'deep_strategy_optimization.json',
    'training_info.json',
    'report_info.json',
    'alerts.json',
    'best_feature_config.json',
    'health_metrics.json',
    'scheduler_v8_status.json',
]

# ── 需要删除的旧版冗余日志文件 ──
REDUNDANT_LOG_FILES = [
    '__main__.log',
    'main.log',
    'app.log', 'app.log.20260420', 'app.log.20260421',
    'app.log.20260422', 'app.log.20260423', 'app.log.20260424',
    'app.info.log', 'app.warning.log',
    'app.json.log',
    'deploy.log',
    'log_config.json',
    'src.app.auto_scheduler_v8.log',
    'src.core.monitoring.performance_monitor.log',
]

# ── 需要保留的二进制文件 ──
KEEP_BINARY = [
    'task_history_v8.pkl',
    'workflow_state.pkl',
    'workflow_state_backup_20260428_112113.pkl',
    'workflow_state_backup_20260428_112544.pkl',
]


def migrate():
    DATA.mkdir(parents=True, exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    print('=' * 50)
    print('日志迁移工具')
    print('=' * 50)

    # 1. 移动业务 JSON
    print(f'\n[1/3] 移动业务 JSON → data/')
    moved = 0
    for name in BUSINESS_FILES:
        src = LOGS / name
        if src.exists():
            dst = DATA / name
            shutil.move(str(src), str(dst))
            print(f'  → {name}  → data/')
            moved += 1
    print(f'  共移动 {moved} 个文件')

    # 2. 归档旧版日志
    print(f'\n[2/3] 归档旧版冗余日志 → archive/')
    archived = 0
    for name in REDUNDANT_LOG_FILES:
        src = LOGS / name
        if src.exists():
            dst = ARCHIVE / name
            shutil.move(str(src), str(dst))
            print(f'  → {name}  → archive/')
            archived += 1
    print(f'  共归档 {archived} 个文件')

    # 3. 列示保留文件
    print(f'\n[3/3] 保留文件:')
    for name in KEEP_BINARY:
        f = LOGS / name
        if f.exists():
            size = f.stat().st_size / 1024
            print(f'  ✅ {name} ({size:.0f} KB)')

    # system.log 和 system.json.log
    for name in ['system.log', 'system.json.log']:
        f = LOGS / name
        if f.exists():
            size = f.stat().st_size / 1024
            print(f'  ✅ {name} ({size:.0f} KB)')

    # data/ 目录内容
    print(f'\n  logs/data/ 内容:')
    for f in sorted(DATA.glob('*')):
        size = f.stat().st_size / 1024
        print(f'    {f.name} ({size:.0f} KB)')

    print('\n' + '=' * 50)
    print('迁移完成')
    print('=' * 50)


if __name__ == '__main__':
    migrate()
