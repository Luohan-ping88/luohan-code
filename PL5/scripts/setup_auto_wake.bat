@echo off
chcp 65001 >nul
title 配置自动唤醒定时任务 - 排列五自动化系统
color 0A

echo.
echo  ╔════════════════════════════════════════════════════════════════════════════════╗
echo  ║                                                                                ║
echo  ║         配置自动唤醒定时任务 - 确保电脑睡眠时也能自动执行                        ║
echo  ║                                                                                ║
echo  ╚════════════════════════════════════════════════════════════════════════════════╝
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  ❌ 错误：需要以管理员身份运行此脚本
    echo  请右键点击此文件，选择"以管理员身份运行"
    pause
    exit /b 1
)

echo  🔧 开始配置自动唤醒功能...
echo.
echo  此配置将确保即使电脑处于睡眠状态，
echo  系统也会在设定的时间自动唤醒并执行定时任务。
echo.
pause
cls

:: 步骤1：配置电源设置
echo.
echo  【步骤 1/3】配置系统电源设置...
echo  ----------------------------------------
echo  正在启用唤醒定时器...
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
echo  ✅ 唤醒定时器已启用
echo.
echo  正在禁用混合睡眠...
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0
echo  ✅ 混合睡眠已禁用
echo.
echo  正在应用电源设置...
powercfg /SetActive SCHEME_CURRENT
echo  ✅ 电源设置已应用
echo.
pause
cls

:: 步骤2：创建Windows定时任务
echo.
echo  【步骤 2/3】创建Windows任务计划程序...
echo  ----------------------------------------
echo  正在启动PowerShell创建定时任务...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0create_scheduled_tasks.ps1"

if %errorLevel% neq 0 (
    echo.
echo  ⚠️  PowerShell脚本执行可能出现问题
echo  请手动运行: scripts\create_scheduled_tasks.ps1
)

echo.
pause
cls

:: 步骤3：验证配置
echo.
echo  【步骤 3/3】验证配置结果...
echo  ----------------------------------------
echo.
echo  唤醒定时器状态:
powercfg /QUERY SCHEME_CURRENT SUB_SLEEP RTCWAKE | findstr "当前电源"
echo.
echo  已创建的定时任务:
schtasks /query /tn "PL5_*" /fo table 2>nul
if %errorLevel% neq 0 (
    echo  (任务列表可能为空，请检查任务计划程序)
)
echo.

:: 完成
echo.
echo  ╔════════════════════════════════════════════════════════════════════════════════╗
echo  ║                          自动唤醒配置完成                                       ║
echo  ╚════════════════════════════════════════════════════════════════════════════════╝
echo.
echo  ✅ 配置完成！系统现在支持睡眠状态下自动唤醒执行任务。
echo.
echo  📋 配置内容：
echo    1. 启用系统唤醒定时器
echo    2. 禁用混合睡眠模式
echo    3. 创建Windows定时任务（支持唤醒）
echo.
echo  ⏰ 定时任务时间表（与系统内部调度保持一致）：
echo    22:00  - 自动获取开奖数据（唤醒电脑）
echo    22:15  - 评估预测逻辑与命中情况（唤醒电脑）
echo    02:30  - 推理逻辑策略优化学习（唤醒电脑）
echo    04:00  - 开始深度学习训练（唤醒电脑）
echo    08:00  - 增量训练（上午）- 首次佐证（唤醒电脑）
echo    10:00  - 首次预测验证（首次佐证）（唤醒电脑）
echo    12:00  - 增量训练（中午）- 二次佐证（唤醒电脑）
echo    14:00  - 增量训练（下午）- 三次佐证（唤醒电脑）
echo    16:00  - 深度策略优化（四次佐证）（唤醒电脑）
echo    17:00  - 预测结果预生成（五次佐证）（唤醒电脑）
echo    18:00  - 生成最终预测结果（唤醒电脑）
echo    19:00  - 验证最终预测结果（六次佐证）（唤醒电脑）
echo    20:00  - 售前最终预测（唤醒电脑）
echo    20:15  - 发送训练报告和最终预测到邮箱（唤醒电脑）
echo.
echo  ⚠️  重要提醒：
echo    1. 笔记本电脑必须连接电源适配器
echo    2. 需要在BIOS中启用"Wake on Timer"或"RTC Wake"选项
echo    3. 首次配置后建议测试：让电脑睡眠，观察是否能按时唤醒
echo    4. 某些品牌电脑（如部分联想、戴尔）可能需要在BIOS中额外设置
echo.
echo  🔍 查看和管理任务：
echo    1. 按 Win+R，输入 taskschd.msc 打开任务计划程序
echo    2. 在"任务计划程序库"中找到 PL5_* 开头的任务
echo    3. 可以右键任务选择"运行"进行测试
echo.
pause
