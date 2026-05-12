#!/bin/bash
# PL5 本地调度器启动脚本 (Linux/macOS)
# 用于在非 Windows 系统上测试或运行调度器

echo "=========================================="
echo "PL5 本地调度器启动脚本"
echo "=========================================="

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PL5_DIR="$(dirname "$SCRIPT_DIR")"

echo "PL5 目录: $PL5_DIR"
cd "$PL5_DIR"

# 检查依赖
echo ""
echo "检查依赖..."
python3 -c "import pandas, numpy, sklearn, requests, psutil" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "警告: 部分依赖可能未安装"
fi

# 检查调度器文件
if [ ! -f "src/app/auto_scheduler_v8.py" ]; then
    echo "错误: 找不到调度器文件 src/app/auto_scheduler_v8.py"
    exit 1
fi

echo ""
echo "=========================================="
echo "启动调度器..."
echo "=========================================="
echo ""
echo "提示: 按 Ctrl+C 停止"
echo ""

# 启动调度器
python3 src/app/auto_scheduler_v8.py
