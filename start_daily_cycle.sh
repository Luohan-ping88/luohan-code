
#!/bin/bash
cd /workspace/PL5

echo "=== 彻底重置工作流和日志 ==="
rm -f logs/workflow_state.pkl
rm -f scheduler_full.log
rm -f scheduler.log
rm -f crash.log
rm -f performance.log

echo "当前运行中的 Python 任务:"
ps aux | grep python | grep -v grep

echo "=== 启动完整日循环 ==="
nohup python main.py schedule --once > scheduler_full.log 2>&1 &
PID=$!
echo "完整日循环已启动，PID: $PID"
echo "日志文件: /workspace/PL5/scheduler_full.log"

sleep 30
echo "=== 初始运行日志 ==="
tail -300 scheduler_full.log
