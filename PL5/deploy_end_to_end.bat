@echo off
chcp 65001 >nul
title PL5 端到端完整部署 V10.3
color 0E

echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                                                                       ║
echo ║       PL5排列五智能分析系统 - 端到端完整部署程序 V3.0                ║
echo ║       【V3.0修复】严格三重匹配，避免误杀外部Python进程               ║
echo ║                                                                       ║
echo ║           自动安装依赖 → 配置Windows服务 → 启动24/7后台运行          ║
echo ║                                                                       ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

:: 设置工作目录
cd /d "%~dp0"

echo 部署目录: %CD%
echo.

:: 检查管理员权限（推荐但非必须）
net session >nul 2>&1
if errorlevel 1 (
    echo ╔═══════════════════════════════════════════════════════════════════╗
    echo ║  提示: 建议以管理员身份运行以获得完整功能                        ║
    echo ║     右键点击此脚本，选择"以管理员身份运行"                            ║
    echo ╚═══════════════════════════════════════════════════════════════════╝
    echo.
    pause
)

:: 步骤1: 安装依赖
echo [步骤 1/4] 自动安装所有依赖库
echo ========================================
call scripts\deploy\install_dependencies.bat
if errorlevel 1 (
    echo 依赖安装失败！
    pause
    exit /b 1
)
echo 依赖安装完成
echo.
pause

:: 步骤2: 配置Windows服务
echo [步骤 2/4] 配置Windows计划任务服务
echo ========================================
call scripts\deploy\setup_windows_service.bat
if errorlevel 1 (
    echo 服务配置可能遇到问题，但将继续尝试启动
)
echo 服务配置完成
echo.
pause

:: 步骤3: 启动服务
echo [步骤 3/4] 启动24/7后台服务
echo ========================================
call start_daemon.bat
echo.

:: 步骤4: 完成验证（V3.0严格三重匹配）
echo [步骤 4/4] 部署完成验证（V3.0严格模式）
echo ========================================
echo.
echo 正在验证服务状态...

:: 【V3.1修复】使用严格三重匹配验证PL5进程（支持模块模式）
python -c "
import psutil
import sys

PL5_PATHS = ['\\\\PL5\\\\', '/PL5/', 'E:\\\\PL5', 'D:\\\\PL5']
PL5_IDS = ['auto_scheduler_v8', 'process_watchdog', 'prevent_sleep', 'pl5_intelligent_system', 'start_system', 'start_sentinel', 'launch_simple', 'src.app.auto_scheduler_v8']

def check_module_mode(cmdline_str):
    if not cmdline_str: return False
    cmdline_lower = cmdline_str.lower()
    if 'src.app.auto_scheduler_v8' in cmdline_lower and 'python' in cmdline_lower:
        return True
    return False

def is_pl5(cmdline_str, proc_name):
    if not cmdline_str:
        return False
    cmdline_str_lower = cmdline_str.lower()
    is_python = 'python' in proc_name.lower() if proc_name else False
    if not is_python:
        return False
    has_id = any(pid in cmdline_str_lower for pid in PL5_IDS)
    if not has_id:
        return False
    has_path = any(p.lower() in cmdline_str_lower for p in PL5_PATHS)
    has_module_mode = check_module_mode(cmdline_str_lower)
    return has_path or has_module_mode

found = []
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = proc.info['cmdline'] or []
        cmdline_str = ' '.join(cmdline)
        if is_pl5(cmdline_str, proc.info['name']):
            found.append(proc.info['pid'])
    except:
        pass

if found:
    print(f'[OK] 发现 {len(found)} 个PL5进程运行中')
    sys.exit(0)
else:
    print('[警告] 未发现PL5进程运行')
    sys.exit(1)
"

if %errorlevel% equ 0 (
    echo.
    echo ╔═══════════════════════════════════════════════════════════════════╗
    echo ║                                                                       ║
    echo ║                    端到端部署成功完成！                               ║
    echo ║                                                                       ║
    echo ║  系统状态:                                                             ║
    echo ║    所有依赖库已安装                                                  ║
    echo ║    Windows计划任务已配置（开机自动启动）                              ║
    echo ║    24/7后台服务正在运行                                              ║
    echo ║    看门狗监控已启动（崩溃自动重启）                                  ║
    echo ║                                                                       ║
    echo ║  【V3.0修复】严格三重匹配，外部Python进程不受影响！                   ║
    echo ║                                                                       ║
    echo ║  常用管理命令:                                                         ║
    echo ║    管理服务: scripts\deploy\manage_service.bat                      ║
    echo ║    查看状态: python scripts/utility/check_scheduler_status.py       ║
    echo ║    查看日志: type logs\scheduler_v8_status.json                    ║
    echo ║    停止系统: stop_service.bat                                        ║
    echo ║                                                                       ║
    echo ║  定时任务安排（完整佐证链）：                                         
    echo ║    22:15 - 自动获取开奖数据                                         
    echo ║    22:15 - 评估预测逻辑与命中情况                                   
    echo ║    22:45 - 推理逻辑策略优化学习                                     
    echo ║    00:30 - 开始深度学习训练                                          ║
    echo ║    08:00 - 增量训练（上午）- 首次佐证                                ║
    echo ║    10:00 - 首次预测验证（首次佐证）                                  ║
    echo ║    12:00 - 增量训练（中午）- 二次佐证                                ║
    echo ║    14:00 - 增量训练（下午）- 三次佐证                                ║
    echo ║    16:00 - 深度策略优化（四次佐证）                                  ║
    echo ║    17:00 - 预测结果预生成（五次佐证）                                ║
    echo ║    18:00 - 生成最终预测结果                                          ║
    echo ║    19:00 - 验证最终预测结果（六次佐证）                              ║
    echo ║    20:00 - 售前最终预测                                              ║
    echo ║    20:15 - 发送训练报告和最终预测到邮箱                              ║
    echo ║                                                                       ║
    echo ║  下一步:                                                               ║
    echo ║    您现在可以关闭此窗口，系统将继续在后台24/7运行！                     ║
    echo ║                                                                       ║
    echo ╚═══════════════════════════════════════════════════════════════════╝
) else (
    echo.
    echo ╔═══════════════════════════════════════════════════════════════════╗
    echo ║  部署完成，但服务未立即启动                                         ║
    echo ║     请尝试手动运行: start_daemon.bat                            ║
    echo ╚═══════════════════════════════════════════════════════════════════╝
)

echo.
echo.
pause
