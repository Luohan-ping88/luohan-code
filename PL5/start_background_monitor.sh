#!/bin/bash
# PL5 24小时持续监控 - 后台运行启动脚本
# 使用 nohup 在后台运行，并记录PID

cd /workspace/PL5

LOG_DIR="./logs/daily_audit"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/nohup_${TIMESTAMP}.log"
PID_FILE="$LOG_DIR/monitor_${TIMESTAMP}.pid"

echo "=========================================="
echo "PL5 24小时持续监控系统 - 后台模式"
echo "=========================================="
echo "启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "日志文件: $LOG_FILE"
echo "PID文件: $PID_FILE"
echo "=========================================="
echo ""

# 检查是否已有运行中的监控
if [ -f "$LOG_DIR"/*.pid 2>/dev/null ]; then
    echo "检测到已有的监控进程:"
    for pidfile in "$LOG_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            old_pid=$(cat "$pidfile")
            if ps -p "$old_pid" > /dev/null 2>&1; then
                echo "  PID $old_pid 正在运行"
                echo "  请先停止: kill $(cat "$pidfile")"
                exit 1
            else
                echo "  PID $old_pid 已停止，清理..."
                rm -f "$pidfile"
            fi
        fi
    done
fi

# 检查依赖
echo "[1/3] 检查依赖..."
python -c "import numpy, pandas, sklearn, requests, psutil, pytest" 2>&1 | grep -v "^$"
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "  ✓ 依赖检查通过"
else
    echo "  ✗ 缺少依赖，正在安装..."
    python install_dependencies_fix.py > /dev/null 2>&1
fi

# 检查前置条件
echo "[2/3] 检查前置条件..."
if [ -f "pl5_24hour_monitor.py" ] && [ -f "src/core/models/predictor.py" ]; then
    echo "  ✓ 前置条件满足"
else
    echo "  ✗ 缺少关键文件"
    exit 1
fi

# 启动监控
echo "[3/3] 启动持续监控..."
echo ""
echo "监控详情:"
echo "  - 审计周期: 10分钟"
echo "  - 预计周期数: 144 (24小时)"
echo "  - 日志目录: $LOG_DIR"
echo "  - 启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "使用以下命令查看日志:"
echo "  tail -f $LOG_FILE"
echo ""
echo "使用以下命令停止监控:"
echo "  kill \$(cat $PID_FILE)"
echo ""

# 使用 nohup 在后台运行
nohup python pl5_24hour_monitor.py --continuous > "$LOG_FILE" 2>&1 &

# 保存PID
MONITOR_PID=$!
echo $MONITOR_PID > "$PID_FILE"

echo "✓ 监控已启动"
echo "  PID: $MONITOR_PID"
echo "  日志: $LOG_FILE"
echo ""
echo "等待监控初始化..."
sleep 2

# 检查进程是否正在运行
if ps -p $MONITOR_PID > /dev/null 2>&1; then
    echo "✓ 监控进程运行正常"
    echo ""
    echo "=========================================="
    echo " 监控已成功启动！"
    echo " 继续监控直到手动停止或24小时后自动结束"
    echo "=========================================="
    exit 0
else
    echo "✗ 监控进程启动失败"
    echo "请检查日志: $LOG_FILE"
    exit 1
fi
