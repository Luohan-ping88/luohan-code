@echo off
chcp 65001 >nul
title PL5后台启动器 V10.3
color 0A

echo.
echo  ============================================
echo    PL5智能分析系统 - 后台守护进程启动器
echo    (关闭窗口后系统继续运行)
echo  ============================================
echo.

::: 设置工作目录
cd /d "%~dp0"
echo  [工作目录] %CD%
echo.

::: 【修复V2.0】使用精确匹配检查是否已有PL5实例在运行
echo  [检查] 检查是否已有PL5实例在运行...

python -c "
import psutil
import sys

PL5_PATHS = ['\\\\PL5\\\\', '/PL5/', 'e:\\\\PL5', 'E:\\\\PL5']
PL5_IDENTIFIERS = ['auto_scheduler_v8', 'process_watchdog', 'prevent_sleep', 'pl5_intelligent_system', 'start_system', 'start_sentinel', 'launch_simple', 'src.app.auto_scheduler_v8']

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
    has_id = any(pid in cmdline_str_lower for pid in PL5_IDENTIFIERS)
    if not has_id: return False
    has_path = any(p.lower() in cmdline_str_lower for p in PL5_PATHS)
    has_module_mode = check_module_mode(cmdline_str_lower)
    return has_path or has_module_mode

found = []

for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = proc.info['cmdline'] or []
        cmdline_str = ' '.join(cmdline)
        if is_pl5(cmdline_str, proc.info['name']):
            found.append((proc.info['pid'], cmdline_str[:80]))
    except:
        pass

if found:
    print(f'[警告] 发现 {len(found)} 个PL5进程已在运行:')
    for pid, cmd in found:
        print(f'  PID={pid}: {cmd}...')
    sys.exit(1)
else:
    print('[OK] 未发现PL5进程在运行')
    sys.exit(0)
"

if %errorlevel% equ 1 (
    echo.
    set /p confirm="是否继续启动? (y/N): "
    if /I not "%confirm%"=="y" (
        echo  已取消启动
        pause
        exit /b 1
    )
)

::: 查找pythonw.exe
set "PYTHONW=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\pythonw.exe"
if not exist "%PYTHONW%" (
    for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do set "PYTHONW=%%i"
)

if not exist "%PYTHONW%" (
    echo  [错误] 找不到pythonw.exe，尝试使用python.exe...
    set "PYTHONW=python.exe"
)

echo  [Python] %PYTHONW%
echo.

::: 【修复V10.1】增加监控文件存在性检查，防止静默失败
if not exist "monitor\prevent_sleep.py" (
    echo  [警告] monitor\prevent_sleep.py 不存在，将跳过防睡眠保护
)
if not exist "monitor\system_monitor.py" (
    echo  [警告] monitor\system_monitor.py 不存在，将跳过系统监控
)
echo.

::: 启动防睡眠保护（后台）
echo  [1/3] 启动防睡眠保护...
if exist "monitor\prevent_sleep.py" (
    start /min "" "%PYTHONW%" monitor\prevent_sleep.py
    timeout /t 1 >nul
    echo  [OK] 防睡眠保护已启动
) else (
    echo  [跳过] 防睡眠保护未启动（文件不存在）
)
echo.

::: 启动系统监控（后台）
echo  [2/3] 启动系统监控服务...
if exist "monitor\system_monitor.py" (
    start /min "" "%PYTHONW%" monitor\system_monitor.py --watch --interval 30
    timeout /t 1 >nul
    echo  [OK] 监控服务已启动
) else (
    echo  [跳过] 系统监控未启动（文件不存在）
)
echo.

::: 启动主调度器（使用pythonw - 无窗口后台运行）
echo  [3/3] 启动主调度器（守护进程模式）...
echo.
echo  定时任务安排（完整佐证链）：
echo    22:15  - 自动获取开奖数据
echo    22:15  - 评估预测逻辑与命中情况
echo    22:45  - 推理逻辑策略优化学习
echo    00:30  - 开始深度学习训练
echo    08:00  - 增量训练（上午）- 首次佐证前训练
echo    10:00  - 首次预测验证（首次佐证）
echo    12:00  - 增量训练（中午）- 二次佐证前训练
echo    13:00  - 二次预测验证（二次佐证）
echo    14:00  - 增量训练（下午）- 三次佐证前训练
echo    15:00  - 三次预测验证（三次佐证）
echo    16:00  - 深度策略优化（四次佐证）
echo    17:00  - 预测结果预生成（五次佐证）
echo    18:00  - 生成最终预测结果
echo    19:00  - 验证最终预测结果（六次佐证）
echo    20:00  - 售前最终预测
echo    20:15  - 发送训练报告和最终预测到邮箱
echo.
echo  正在启动守护进程...
echo.

::: 使用pythonw.exe以模块方式启动（无控制台窗口）
start /B "" "%PYTHONW%" -m src.app.auto_scheduler_v8

timeout /t 3 >nul

::: 【修复V2.0】验证进程启动成功（精确匹配PL5进程）
python -c "
import psutil
import sys
import time

time.sleep(2)

PL5_PATHS = ['\\\\PL5\\\\', '/PL5/', 'e:\\\\PL5', 'E:\\\\PL5']
PL5_IDENTIFIERS = ['auto_scheduler_v8', 'process_watchdog', 'prevent_sleep', 'pl5_intelligent_system', 'start_system', 'start_sentinel', 'launch_simple', 'src.app.auto_scheduler_v8']

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
    has_id = any(pid in cmdline_str_lower for pid in PL5_IDENTIFIERS)
    if not has_id: return False
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
    print(f'[OK] 守护进程启动成功！发现 {len(found)} 个PL5进程')
    sys.exit(0)
else:
    print('[错误] 守护进程启动失败，请检查日志')
    sys.exit(1)
"

if %errorlevel% equ 0 (
    echo.
    echo  ============================================
    echo   [OK] 守护进程启动成功！
    echo  ============================================
    echo.
    echo   系统已在后台运行，可以安全关闭此窗口
    echo.
    echo   查看状态: python scripts/utility/check_scheduler_status.py
    echo   查看日志: type logs/scheduler_v8_status.json
    echo   停止系统: stop_service.bat
    echo.
) else (
    echo  [错误] 守护进程启动失败，请检查日志
)

echo.
echo  按任意键关闭此窗口（系统将继续在后台运行）...
pause >nul
