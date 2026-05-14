#!/bin/bash
# PL5 完整研发全生命周期一键执行脚本
# PL5 R&D Full Lifecycle One-Click Execution Script

set -e

PROJECT_DIR="/workspace/PL5"
LOG_DIR="$PROJECT_DIR/logs/rd_lifecycle"

echo "=========================================="
echo "PL5 完整研发全生命周期管理系统"
echo "PL5 R&D Full Lifecycle Management System"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 创建日志目录
mkdir -p "$LOG_DIR"

# 显示菜单
show_menu() {
    echo -e "${BLUE}请选择操作:${NC}"
    echo "1. 执行完整研发周期 (All Phases)"
    echo "2. 执行阶段1: 方向探讨 (Direction Discussion)"
    echo "3. 执行阶段2: 技术选型 (Technology Selection)"
    echo "4. 执行阶段3: 架构设计 (Architecture Design)"
    echo "5. 执行阶段4: 代码实现 (Code Implementation)"
    echo "6. 执行阶段5: 测试 (Testing)"
    echo "7. 执行阶段6: 部署 (Deployment)"
    echo "8. 执行阶段7: 运维 (Operations)"
    echo "9. 执行阶段8: 监控 (Monitoring)"
    echo "10. 查看报告 (View Reports)"
    echo "0. 退出 (Exit)"
    echo ""
    echo -n "请输入选项 [0-10]: "
}

# 执行完整生命周期
run_full_lifecycle() {
    echo -e "\n${GREEN}开始执行完整研发全生命周期...${NC}\n"
    echo "预计耗时: 30-60分钟"
    echo ""
    
    START_TIME=$(date +%s)
    
    python "$PROJECT_DIR/rd_lifecycle_manager.py"
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    echo ""
    echo -e "${GREEN}==========================================${NC}"
    echo -e "${GREEN}完整研发周期执行完成!${NC}"
    echo -e "${GREEN}总耗时: ${DURATION} 秒${NC}"
    echo -e "${GREEN}==========================================${NC}"
}

# 执行单个阶段
run_phase() {
    local phase=$1
    local phase_name=$2
    
    echo -e "\n${YELLOW}开始执行: ${phase_name}${NC}\n"
    
    START_TIME=$(date +%s)
    
    python "$PROJECT_DIR/rd_lifecycle_manager.py" --phase "$phase"
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    echo ""
    echo -e "${GREEN}阶段 [${phase_name}] 执行完成! 耗时: ${DURATION} 秒${NC}"
}

# 查看报告
view_reports() {
    echo -e "\n${BLUE}=========================================="
    echo "查看报告"
    echo -e "==========================================${NC}\n"
    
    if [ ! -d "$LOG_DIR" ]; then
        echo -e "${RED}暂无报告，请先执行研发流程${NC}"
        return
    fi
    
    echo "可用报告:"
    echo ""
    ls -lh "$LOG_DIR" | tail -20
    echo ""
    echo -n "请输入报告文件路径 (或按回车返回菜单): "
    read report_file
    
    if [ -n "$report_file" ] && [ -f "$report_file" ]; then
        less "$report_file"
    fi
}

# 主循环
main() {
    while true; do
        show_menu
        read choice
        
        case $choice in
            1)
                run_full_lifecycle
                ;;
            2)
                run_phase "方向探讨" "Direction Discussion"
                ;;
            3)
                run_phase "技术选型" "Technology Selection"
                ;;
            4)
                run_phase "架构设计" "Architecture Design"
                ;;
            5)
                run_phase "代码实现" "Code Implementation"
                ;;
            6)
                run_phase "测试" "Testing"
                ;;
            7)
                run_phase "部署" "Deployment"
                ;;
            8)
                run_phase "运维" "Operations"
                ;;
            9)
                run_phase "监控" "Monitoring"
                ;;
            10)
                view_reports
                ;;
            0)
                echo -e "\n${GREEN}感谢使用 PL5 研发全生命周期管理系统!${NC}\n"
                exit 0
                ;;
            *)
                echo -e "\n${RED}无效选项，请重新输入${NC}"
                ;;
        esac
        
        echo ""
        echo -n "按回车键继续..."
        read
    done
}

# 执行主函数
main
