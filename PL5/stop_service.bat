@echo off
chcp 65001 >nul
title PL5 服务停止器 V10.3
color 0C

echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                                                                       ║
echo ║       PL5排列五智能分析系统 - 服务停止程序 V3.0                        ║
echo ║       【修复V3.0】严格三重匹配，不杀外部Python进程                      ║
echo ║                                                                       ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

echo 正在安全停止 PL5 后台服务...
echo.

:: 停止计划任务
echo [1/4] 停止计划任务...
powershell -Command "Stop-ScheduledTask -TaskName PL5_Intelligent_System -ErrorAction SilentlyContinue" 2>nul
echo   计划任务已停止

:: 使用Python精确停止PL5进程（V3.0三重匹配模式）
echo [2/4] 精确终止PL5相关进程（V3.0安全版）...
echo   三重匹配规则：Python进程 + PL5特定标识符 + PL5项目路径
echo.

python scripts\deploy\stop_pl5_processes.py

echo.
echo   PL5相关进程已安全终止

:: 验证（V3.0严格模式）
echo [3/4] 验证状态（V3.0严格模式）...
echo   验证是否还有PL5相关进程残留...

python -c "
import psutil
PL5_PATHS = ['\\\\PL5\\\\', '/PL5/', 'E:\\\\PL5', 'D:\\\\PL5']
PL5_IDS = ['auto_scheduler_v8', 'process_watchdog', 'prevent_sleep', 'pl5_intelligent_system', 'start_system', 'start_sentinel', 'launch_simple', 'src.app.auto_scheduler_v8']
def check_module_mode(cmdline_str):
    if not cmdline_str: return False
    cmdline_lower = cmdline_str.lower()
    if 'src.app.auto_scheduler_v8' in cmdline_lower and 'python' in cmdline_lower:
        return True
    return False
def is_pl5(cmdline_str, proc_name):
    if not cmdline_str: return False
    cmdline_str_lower = cmdline_str.lower()
    is_python = 'python' in proc_name.lower() if proc_name else False
    if not is_python: return False
    has_id = any(pid in cmdline_str_lower for pid in PL5_IDS)
    if not has_id: return False
    has_path = any(p.lower() in cmdline_str_lower for p in PL5_PATHS)
    has_module_mode = check_module_mode(cmdline_str_lower)
    return has_path or has_module_mode
r = [p.info['pid'] for p in psutil.process_iter(['pid', 'name', 'cmdline']) if p.info['cmdline'] and is_pl5(' '.join(p.info['cmdline']), p.info['name'])]
print('  [警告] 仍有 %d 个PL5进程残留' % len(r)) if r else print('  [确认] 无PL5相关进程残留')
"

echo [4/4] 完成
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                                                                       ║
echo ║              PL5 服务已安全停止！                                      ║
echo ║       （V3.0三重匹配：外部Python进程不受影响）                        ║
echo ║                                                                       ║
echo ║  重新启动: start_daemon.bat 或 deploy_end_to_end.bat                ║
echo ║                                                                       ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo 停止服务完成
