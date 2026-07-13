@echo off
chcp 65001 >nul
title PL5 Windows服务设置
color 0B

echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                                                                       ║
echo ║            PL5排列五智能分析系统 - Windows服务部署                    ║
echo ║                                                                       ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

:: 检查管理员权限
net session >nul 2>&1
if errorlevel 1 (
    echo ⚠ 警告: 建议以管理员身份运行以获得完整功能
    echo   右键点击此脚本，选择"以管理员身份运行"
    echo.
)

:: 设置工作目录
cd /d "%~dp0.."
cd /d "%~dp0.."

set "PROJECT_DIR=%CD%"
echo 项目目录: %PROJECT_DIR%
echo.

:: 查找Python路径
echo [1/5] 定位Python解释器...
set "PYTHON_PATH="
for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_PATH set "PYTHON_PATH=%%i"
)

if not defined PYTHON_PATH (
    echo ❌ 错误: 未找到Python
    pause
    exit /b 1
)

echo ✓ Python路径: %PYTHON_PATH%
echo.

:: 查找pythonw.exe（无窗口模式）
echo [2/5] 查找无窗口Python...
set "PYTHONW_PATH="
for /f "delims=" %%i in ('where pythonw 2^>nul') do (
    if not defined PYTHONW_PATH set "PYTHONW_PATH=%%i"
)

if not defined PYTHONW_PATH (
    for %%i in ("%PYTHON_PATH%") do (
        set "PYTHONW_PATH=%%~dpipythonw.exe"
    )
)

if exist "%PYTHONW_PATH%" (
    echo ✓ Pythonw路径: %PYTHONW_PATH%
) else (
    echo ⚠ 未找到pythonw.exe，将使用python.exe
    set "PYTHONW_PATH=%PYTHON_PATH%"
)
echo.

:: 创建启动脚本
echo [3/5] 创建启动脚本...
set "LAUNCH_SCRIPT=%PROJECT_DIR%\scripts\deploy\launch_service.vbs"

(
echo Set WshShell = CreateObject("WScript.Shell"^)
echo WshShell.Run chr(34^) ^& "%PYTHONW_PATH%" ^& chr(34^) ^& " " ^& chr(34^) ^& "%PROJECT_DIR%\src\app\auto_scheduler_v8.py" ^& chr(34^), 0, False
) > "%LAUNCH_SCRIPT%"

echo ✓ 启动脚本已创建: %LAUNCH_SCRIPT%
echo.

:: 创建PowerShell脚本用于设置计划任务
echo [4/5] 创建计划任务配置...
set "TASK_SCRIPT=%PROJECT_DIR%\scripts\deploy\create_scheduled_task.ps1"

(
echo # PL5 系统计划任务创建脚本
echo $ErrorActionPreference = "Stop"
echo.
echo $taskName = "PL5_Intelligent_System"
echo $projectDir = "%PROJECT_DIR%"
echo $pythonPath = "%PYTHONW_PATH%"
echo $scriptPath = Join-Path $projectDir "src\app\auto_scheduler_v8.py"
echo $workingDir = $projectDir
echo.
echo Write-Host "正在创建计划任务: $taskName" -ForegroundColor Cyan
echo.
echo # 检查任务是否已存在
echo $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
echo if ($existingTask^) {
echo     Write-Host "任务已存在，正在删除旧任务..." -ForegroundColor Yellow
echo     Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
echo     Write-Host "旧任务已删除" -ForegroundColor Green
echo }
echo.
echo # 创建任务动作
echo $action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $workingDir
echo.
echo # 创建触发器：系统启动时 + 用户登录时
echo $trigger1 = New-ScheduledTaskTrigger -AtStartup
echo $trigger2 = New-ScheduledTaskTrigger -AtLogon
echo.
echo # 创建设置：允许按需运行、即使电池供电也运行、不停止长时间任务
echo $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Days 365^) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1^)
echo.
echo # 注册任务
echo Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger1, $trigger2 -Settings $settings -RunLevel Highest -Force ^| Out-Null
echo.
echo Write-Host "✓ 计划任务创建成功！" -ForegroundColor Green
echo Write-Host ""
echo Write-Host "任务信息:" -ForegroundColor Cyan
echo Write-Host "  名称: $taskName"
echo Write-Host "  触发: 系统启动 + 用户登录"
echo Write-Host "  脚本: $scriptPath"
echo Write-Host ""
echo Write-Host "管理命令:" -ForegroundColor Yellow
echo Write-Host "  启动任务: Start-ScheduledTask -TaskName $taskName"
echo Write-Host "  停止任务: Stop-ScheduledTask -TaskName $taskName"
echo Write-Host "  查看状态: Get-ScheduledTaskInfo -TaskName $taskName"
echo Write-Host "  删除任务: Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
echo Write-Host ""
) > "%TASK_SCRIPT%"

echo ✓ 计划任务脚本已创建: %TASK_SCRIPT%
echo.

:: 执行PowerShell脚本设置计划任务
echo [5/5] 注册Windows计划任务...
powershell -ExecutionPolicy Bypass -File "%TASK_SCRIPT%"

if errorlevel 1 (
    echo ⚠ 计划任务创建可能遇到问题，但启动脚本已就绪
    echo   您可以手动运行: %LAUNCH_SCRIPT%
)
echo.

:: 创建快捷管理脚本
echo 正在创建管理工具...
set "MANAGE_BAT=%PROJECT_DIR%\scripts\deploy\manage_service.bat"

(
echo @echo off
echo chcp 65001 ^>nul
echo title PL5 服务管理
echo color 0A
echo.
echo echo PL5 系统服务管理
echo echo ====================
echo echo.
echo echo 1. 启动服务
echo echo 2. 停止服务
echo echo 3. 查看状态
echo echo 4. 重启服务
echo echo 5. 删除服务
echo echo 0. 退出
echo echo.
echo set /p choice="请选择操作 [0-5]: "
echo.
echo if "%%choice%%"=="1" goto start
echo if "%%choice%%"=="2" goto stop
echo if "%%choice%%"=="3" goto status
echo if "%%choice%%"=="4" goto restart
echo if "%%choice%%"=="5" goto delete
echo if "%%choice%%"=="0" goto end
echo.
echo echo 无效选择
echo pause
echo goto end
echo.
echo :start
echo echo 正在启动 PL5 服务...
echo powershell -Command "Start-ScheduledTask -TaskName PL5_Intelligent_System"
echo echo ✓ 服务启动命令已发送
echo echo 稍候几秒后服务将开始运行
echo pause
echo goto end
echo.
echo :stop
echo echo 正在停止 PL5 服务...
echo powershell -Command "Stop-ScheduledTask -TaskName PL5_Intelligent_System"
echo echo 正在终止PL5相关进程...
echo powershell -Command "Get-WmiObject Win32_Process -Filter 'name=''pythonw.exe'' OR name=''python.exe''' | Where-Object { $_.CommandLine -match 'auto_scheduler_v8^|process_watchdog^|prevent_sleep^|pl5_intelligent_system^|start_system^|start_sentinel^|launch_simple' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host '  已终止进程 PID:' $_.ProcessId }"
echo echo ✓ 服务已停止
echo pause
echo goto end
echo.
echo :status
echo echo PL5 服务状态
echo echo ==============
echo powershell -Command "Get-ScheduledTask -TaskName PL5_Intelligent_System | Select-Object TaskName, State, LastRunTime, NextRunTime | Format-List"
echo echo.
echo echo 进程状态:
echo powershell -Command "Get-WmiObject Win32_Process -Filter 'name=''pythonw.exe'' OR name=''python.exe''' | Where-Object { $_.CommandLine -match 'auto_scheduler_v8^|process_watchdog^|prevent_sleep^|pl5_intelligent_system^|start_system^|start_sentinel^|launch_simple' } | Select-Object ProcessId, Name, @{Name='Memory(KB)';Expression={[math]::Round($_.WorkingSetSize/1KB)}} | Format-Table -AutoSize"
echo pause
echo goto end
echo.
echo :restart
echo echo 正在重启 PL5 服务...
echo powershell -Command "Stop-ScheduledTask -TaskName PL5_Intelligent_System; Start-Sleep -Seconds 2; Start-ScheduledTask -TaskName PL5_Intelligent_System"
echo echo ✓ 服务已重启
echo pause
echo goto end
echo.
echo :delete
echo echo 警告: 这将删除 PL5 计划任务！
echo set /p confirm="确认删除? (y/N): "
echo if /i not "%%confirm%%"=="y" goto end
echo powershell -Command "Unregister-ScheduledTask -TaskName PL5_Intelligent_System -Confirm:`$false"
echo echo 正在终止PL5相关进程...
echo powershell -Command "Get-WmiObject Win32_Process -Filter 'name=''pythonw.exe'' OR name=''python.exe''' | Where-Object { $_.CommandLine -match 'auto_scheduler_v8^|process_watchdog^|prevent_sleep^|pl5_intelligent_system^|start_system^|start_sentinel^|launch_simple' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo echo ✓ 任务已删除
echo pause
echo goto end
echo.
echo :end
) > "%MANAGE_BAT%"

echo ✓ 管理工具已创建: %MANAGE_BAT%
echo.

echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                                                                       ║
echo ║                    ✓ Windows服务设置完成！                            ║
echo ║                                                                       ║
echo ║  快速操作:                                                            ║
echo ║    • 立即启动服务: start_24x7_service.bat                            ║
echo ║    • 管理服务: scripts\deploy\manage_service.bat                      ║
echo ║    • 查看日志: logs\scheduler_v8_status.json                         ║
echo ║                                                                       ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
pause
