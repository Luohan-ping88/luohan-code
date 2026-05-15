#!/bin/bash
# PL5 24小时持续监控系统启动脚本

cd /workspace/PL5

echo "=================================="
echo "PL5 24小时持续监控系统"
echo "=================================="
echo "启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "日志目录: /workspace/PL5/logs/daily_audit/"
echo ""

# 检查依赖
echo "检查依赖..."
python -c "import numpy; import pandas; import sklearn; import requests; import psutil; import pytest" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ 所有依赖已安装"
else
    echo "✗ 部分依赖缺失，正在安装..."
    python install_dependencies_fix.py
fi

echo ""
echo "启动模式:"
echo "1. 单次审计模式 (测试)"
echo "2. 持续监控模式 (24小时)"
echo ""

read -p "请选择启动模式 [1/2]: " mode

case $mode in
    1)
        echo "运行单次审计..."
        python pl5_24hour_monitor.py
        ;;
    2)
        echo "启动24小时持续监控..."
        echo "按 Ctrl+C 停止"
        echo ""
        python pl5_24hour_monitor.py --continuous
        ;;
    *)
        echo "无效选择，运行单次审计..."
        python pl5_24hour_monitor.py
        ;;
esac
