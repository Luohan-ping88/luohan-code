"""
检查系统定时任务运行状态
"""
import sys
sys.path.insert(0, '.')

import psutil
import json
from datetime import datetime
from pathlib import Path

print('='*70)
print('排列五智能自动化分析系统 - 定时任务状态检查')
print('='*70)
print()

# 1. 检查Python进程
print('【1/4】检查Python进程...')
pl5_processes = []
for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        if proc.info['name'] == 'python.exe':
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            if 'auto_scheduler' in cmdline or 'PL5' in cmdline or 'pl5' in cmdline:
                pl5_processes.append({
                    'pid': proc.info['pid'],
                    'cmdline': cmdline[:80],
                    'start_time': datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                })
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

if pl5_processes:
    print(f'  ✅ 发现 {len(pl5_processes)} 个PL5相关进程')
    for proc in pl5_processes:
        print(f'     PID: {proc["pid"]}, 启动时间: {proc["start_time"]}')
else:
    print('  ❌ 未发现PL5相关进程')
print()

# 2. 检查调度器配置
print('【2/4】检查调度器配置...')
config_file = Path('config/scheduler_config.json')
if config_file.exists():
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    print(f'  ✅ 调度器配置存在')
    print(f'     数据获取时间: {config.get("data_fetch_time", "未设置")}')
    print(f'     邮件发送时间: {config.get("email_send_time", "未设置")}')
else:
    print('  ❌ 调度器配置不存在')
print()

# 3. 检查日志文件
print('【3/4】检查日志文件...')
log_file = Path('logs/scheduler.log')
if log_file.exists():
    size_kb = log_file.stat().st_size / 1024
    mtime = datetime.fromtimestamp(log_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    print(f'  ✅ 调度器日志存在')
    print(f'     大小: {size_kb:.1f} KB')
    print(f'     最后更新: {mtime}')
    
    # 读取最后几行
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                print(f'     总行数: {len(lines)}')
                print('     最后5行日志:')
                for line in lines[-5:]:
                    print(f'       {line.strip()[:70]}')
    except Exception as e:
        print(f'     读取日志失败: {e}')
else:
    print('  ❌ 调度器日志不存在')
print()

# 4. 检查学习历史
print('【4/4】检查学习历史...')
history_file = Path('models/learning_history.json')
if history_file.exists():
    with open(history_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    evaluations = data.get('evaluations', [])
    if evaluations:
        last_eval = evaluations[-1]
        # 转换期号格式
        period = last_eval.get("period", "未知")
        if len(str(period)) == 5 and str(period).startswith('26'):
            full_period = f"20{period}"  # 26030 -> 2026030
        else:
            full_period = period
        print(f'  ✅ 学习历史存在')
        print(f'     评估记录数: {len(evaluations)} 条')
        print(f'     最后评估期号: {full_period}')
        print(f'     最后评估时间: {last_eval.get("timestamp", "未知")[:19]}')
        print(f'     最后评估准确率: {last_eval.get("accuracy", 0):.2%}')
    else:
        print('  ⚠️ 学习历史为空')
else:
    print('  ❌ 学习历史不存在')
print()

# 总结
print('='*70)
print('状态总结')
print('='*70)
if pl5_processes:
    print('✅ 系统正在后台运行')
    print('   - 自动定时任务已启用')
    print('   - 数据获取: 每日 00:00')
    print('   - 评估预测: 每日 00:30')
    print('   - 策略优化: 每日 01:00')
    print('   - 深度学习: 每日 02:00')
    print('   - 邮件报告: 每日 17:30')
else:
    print('❌ 系统未在后台运行')
    print('   启动方式:')
    print('   1. 双击 scripts\\launcher.bat')
    print('   2. 或运行: python -m app.auto_scheduler')
print('='*70)
