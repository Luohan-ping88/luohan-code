#!/bin/bash
# PL5 24小时持续训练预测系统 - 守护进程启动脚本
# 用法: ./run_pl5_daemon.sh [持续时间(小时)] [日志文件]

set -e

# 项目目录
PROJECT_DIR="/workspace/PL5"
cd "$PROJECT_DIR"

# 默认参数
DURATION=${1:-24}
LOG_PREFIX=${2:-"pl5_continuous"}

# 生成日志文件名
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$PROJECT_DIR/logs/${LOG_PREFIX}_${TIMESTAMP}.log"
PID_FILE="$PROJECT_DIR/logs/${LOG_PREFIX}.pid"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}PL5 24小时持续训练预测系统${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "计划运行时长: ${DURATION} 小时"
echo "日志文件: ${LOG_FILE}"
echo "进程ID文件: ${PID_FILE}"
echo ""

# 检查是否已有进程在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}警告: 检测到已有进程运行 (PID: $OLD_PID)${NC}"
        echo "是否要终止旧进程并启动新进程? (y/n)"
        read -r answer
        if [ "$answer" != "y" ]; then
            echo "取消启动"
            exit 0
        fi
        echo "终止旧进程..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

# 确保日志目录存在
mkdir -p "$PROJECT_DIR/logs"

# 启动Python进程
echo "启动PL5持续训练系统..."
nohup python "$PROJECT_DIR/pl5_continuous_training_system.py" --duration "$DURATION" > "$LOG_FILE" 2>&1 &
PYTHON_PID=$!

# 保存进程ID
echo "$PYTHON_PID" > "$PID_FILE"

echo ""
echo -e "${GREEN}✓ 系统已启动!${NC}"
echo "进程ID: $PYTHON_PID"
echo "日志文件: $LOG_FILE"
echo ""
echo "查看日志: tail -f $LOG_FILE"
echo "查看进程: ps aux | grep pl5_continuous"
echo "停止系统: kill $PYTHON_PID"
echo ""

# 等待几秒后显示初始日志
sleep 3
if [ -f "$LOG_FILE" ]; then
    echo "========================================"
    echo "初始日志输出 (最后20行):"
    echo "========================================"
    tail -20 "$LOG_FILE"
fi

echo ""
echo -e "${GREEN}系统正在后台运行...${NC}"
echo "完整审计将在每6小时执行一次"
echo "预测循环每5分钟执行一次"
echo "训练循环每30分钟执行一次"
echo "系统优化每1小时执行一次"
echo ""
echo "下次完整审计将在6小时后执行"
