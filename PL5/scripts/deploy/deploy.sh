#!/bin/bash

# PL5 自动化部署脚本
# 用于部署PL5排列五预测系统

set -e

# 颜色定义
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# 日志文件
LOG_FILE="$PROJECT_ROOT/logs/deploy.log"

# 确保日志目录存在
mkdir -p "$PROJECT_ROOT/logs"

echo -e "${GREEN}=== PL5 自动化部署脚本 ===${NC}"
echo "$(date) - 开始部署" >> "$LOG_FILE"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: Python 3 未安装${NC}"
    echo "$(date) - 错误: Python 3 未安装" >> "$LOG_FILE"
    exit 1
fi

echo -e "${GREEN}✓ Python 3 已安装${NC}"

# 检查pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}错误: pip 未安装${NC}"
    echo "$(date) - 错误: pip 未安装" >> "$LOG_FILE"
    exit 1
fi

echo -e "${GREEN}✓ pip 已安装${NC}"

# 检查依赖文件
if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo -e "${RED}错误: requirements.txt 未找到${NC}"
    echo "$(date) - 错误: requirements.txt 未找到" >> "$LOG_FILE"
    exit 1
fi

echo -e "${GREEN}✓ 依赖文件已找到${NC}"

# 安装依赖
echo -e "${YELLOW}正在安装依赖...${NC}"
echo "$(date) - 开始安装依赖" >> "$LOG_FILE"
pip3 install --upgrade pip
pip3 install -r "$PROJECT_ROOT/requirements.txt"
echo -e "${GREEN}✓ 依赖安装完成${NC}"
echo "$(date) - 依赖安装完成" >> "$LOG_FILE"

# 检查Docker
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker 已安装${NC}"
    
    # 构建Docker镜像
    echo -e "${YELLOW}正在构建Docker镜像...${NC}"
    echo "$(date) - 开始构建Docker镜像" >> "$LOG_FILE"
    docker build -t pl5-system "$PROJECT_ROOT"
    echo -e "${GREEN}✓ Docker镜像构建完成${NC}"
    echo "$(date) - Docker镜像构建完成" >> "$LOG_FILE"
else
    echo -e "${YELLOW}警告: Docker 未安装，跳过Docker构建${NC}"
    echo "$(date) - 警告: Docker 未安装，跳过Docker构建" >> "$LOG_FILE"
fi

# 运行测试
echo -e "${YELLOW}正在运行测试...${NC}"
echo "$(date) - 开始运行测试" >> "$LOG_FILE"
python3 -m pytest "$PROJECT_ROOT" -v
echo -e "${GREEN}✓ 测试完成${NC}"
echo "$(date) - 测试完成" >> "$LOG_FILE"

# 检查系统状态
echo -e "${YELLOW}正在检查系统状态...${NC}"
echo "$(date) - 开始检查系统状态" >> "$LOG_FILE"
python3 "$PROJECT_ROOT/main.py" --action status
echo -e "${GREEN}✓ 系统状态检查完成${NC}"
echo "$(date) - 系统状态检查完成" >> "$LOG_FILE"

# 启动服务
echo -e "${YELLOW}正在启动服务...${NC}"
echo "$(date) - 开始启动服务" >> "$LOG_FILE"

# 检查是否已存在运行的服务
if command -v lsof &> /dev/null; then
    if lsof -i :8000 &> /dev/null; then
        echo -e "${YELLOW}警告: 端口8000已被占用，可能有服务正在运行${NC}"
        echo "$(date) - 警告: 端口8000已被占用" >> "$LOG_FILE"
    fi
fi

# 启动API服务
cd "$PROJECT_ROOT"
python3 "src/ai/api.py" &
API_PID=$!
echo "API服务启动，PID: $API_PID"
echo "$(date) - API服务启动，PID: $API_PID" >> "$LOG_FILE"

# 等待服务启动
sleep 5

# 检查服务状态
echo -e "${YELLOW}正在检查服务状态...${NC}"
if curl -s http://localhost:8000/api/health | grep -q "healthy"; then
    echo -e "${GREEN}✓ 服务启动成功${NC}"
    echo "$(date) - 服务启动成功" >> "$LOG_FILE"
else
    echo -e "${RED}错误: 服务启动失败${NC}"
    echo "$(date) - 错误: 服务启动失败" >> "$LOG_FILE"
    kill $API_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}=== 部署完成 ===${NC}"
echo "$(date) - 部署完成" >> "$LOG_FILE"
echo ""
echo "服务已启动，可访问: http://localhost:8000"
echo "健康检查: http://localhost:8000/api/health"
echo ""
