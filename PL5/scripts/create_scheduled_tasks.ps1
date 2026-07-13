﻿# ================================================================
# 排列五自动化系统 V5.3 - Windows 任务计划程序配置
# 以管理员身份运行 PowerShell 执行此脚本
# 用法: PowerShell -ExecutionPolicy Bypass -File scripts\create_scheduled_tasks.ps1
# ================================================================

param(
    [switch]$RemoveOnly  # 仅删除旧任务
)

$Host.UI.RawUI.WindowTitle = "PL5 V5.3 - Task Scheduler Setup"

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  PL5 V5.3 - Windows 任务计划程序配置" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[FAIL] 需要以管理员身份运行" -ForegroundColor Red
    Write-Host "       请右键 PowerShell -> 以管理员身份运行" -ForegroundColor Yellow
    exit 1
}

# 自动探测项目路径（脚本所在目录的父目录）
$ProjectPath = (Split-Path -Parent $PSScriptRoot)
$PythonPath  = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonPath) {
    Write-Host "[FAIL] 未找到 Python，请确保 Python 已加入 PATH" -ForegroundColor Red
    exit 1
}

Write-Host "  项目路径:  $ProjectPath" -ForegroundColor Green
Write-Host "  Python:    $PythonPath"  -ForegroundColor Green
Write-Host ""

$TaskNamePrefix = "PL5_"

# ----------------------------------------------------------------
# 1. 清理旧任务
# ----------------------------------------------------------------
Write-Host "[1/3] 清理旧任务..." -ForegroundColor Yellow
$allTaskNames = @(
    "${TaskNamePrefix}DataFetch",
    "${TaskNamePrefix}Evaluate",
    "${TaskNamePrefix}Optimize",
    "${TaskNamePrefix}Train",
    "${TaskNamePrefix}SendReport",
    "${TaskNamePrefix}Monitor",
    "${TaskNamePrefix}Watchdog"
)
foreach ($tn in $allTaskNames) {
    if (Get-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $tn -Confirm:$false | Out-Null
        Write-Host "    Removed: $tn" -ForegroundColor Gray
    }
}
Write-Host "  [OK] 旧任务清理完成" -ForegroundColor Green
Write-Host ""

if ($RemoveOnly) {
    Write-Host "  --RemoveOnly 模式，清理完成退出" -ForegroundColor Yellow
    exit 0
}

# ----------------------------------------------------------------
# 2. 定义任务列表
# ----------------------------------------------------------------
# 【优化】统一时间配置，与 auto_scheduler_v8.py 保持一致
# 确保唤醒功能覆盖所有关键任务时间点
$tasks = @(
    @{
        Name        = "${TaskNamePrefix}DataFetch"
        Description = "PL5 - 自动获取开奖数据 (22:00)"
        Time        = "22:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task fetch"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}Evaluate"
        Description = "PL5 - 评估预测准确性 (22:15)"
        Time        = "22:15"
        Argument    = "-m src.app.auto_scheduler_v8 --task evaluate"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}Optimize"
        Description = "PL5 - 策略优化学习 (02:30)"
        Time        = "02:30"
        Argument    = "-m src.app.auto_scheduler_v8 --task optimize"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}Train"
        Description = "PL5 - 深度学习训练 (04:00)"
        Time        = "04:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task train"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}IncrementalTrain"
        Description = "PL5 - 上午增量训练 (08:00)"
        Time        = "08:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task incremental_train"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}FirstPrediction"
        Description = "PL5 - 首次预测验证 (10:00)"
        Time        = "10:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task first_prediction_verification"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}NoonTrain"
        Description = "PL5 - 中午增量训练 (12:00)"
        Time        = "12:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task incremental_train"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}AfternoonTrain"
        Description = "PL5 - 下午增量训练 (14:00)"
        Time        = "14:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task incremental_train"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}DeepOptimize"
        Description = "PL5 - 深度策略优化 (16:00)"
        Time        = "16:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task deep_strategy_optimization"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}PredictionPreview"
        Description = "PL5 - 预测预生成 (17:00)"
        Time        = "17:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task prediction_preview"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}FinalPrediction"
        Description = "PL5 - 最终预测 (18:00)"
        Time        = "18:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task final_prediction"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}FinalVerification"
        Description = "PL5 - 最终预测验证 (19:00)"
        Time        = "19:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task final_prediction_verification"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}PreSalePrediction"
        Description = "PL5 - 售前最终预测 (20:00)"
        Time        = "20:00"
        Argument    = "-m src.app.auto_scheduler_v8 --task pre_sale_prediction"
        WakeToRun   = $true
    },
    @{
        Name        = "${TaskNamePrefix}SendReport"
        Description = "PL5 - 发送训练报告 (20:15)"
        Time        = "20:15"
        Argument    = "-m src.app.auto_scheduler_v8 --task send_report"
        WakeToRun   = $true
    }
)

# ----------------------------------------------------------------
# 3. 创建定时任务
# ----------------------------------------------------------------
Write-Host "[2/3] 创建定时任务..." -ForegroundColor Yellow
$ok = 0; $fail = 0

foreach ($task in $tasks) {
    $trigger  = New-ScheduledTaskTrigger -Daily -At $task.Time
    $action   = New-ScheduledTaskAction  -Execute $PythonPath `
                    -Argument $task.Argument `
                    -WorkingDirectory $ProjectPath
    $settings = New-ScheduledTaskSettingsSet `
                    -WakeToRun:$task.WakeToRun `
                    -StartWhenAvailable `
                    -RunOnlyIfNetworkAvailable:$false `
                    -DontStopOnIdleEnd `
                    -AllowStartIfOnBatteries `
                    -DontStopIfGoingOnBatteries `
                    -ExecutionTimeLimit (New-TimeSpan -Hours 18)

    try {
        Register-ScheduledTask `
            -TaskName    $task.Name `
            -Description $task.Description `
            -Trigger     $trigger `
            -Action      $action `
            -Settings    $settings `
            -RunLevel    Highest `
            -Force | Out-Null
        Write-Host ("    [OK]  {0,-35} [{1}] (Wake={2})" -f $task.Name, $task.Time, $task.WakeToRun) -ForegroundColor Green
        $ok++
    } catch {
        Write-Host ("    [FAIL] {0} - {1}" -f $task.Name, $_.Exception.Message) -ForegroundColor Red
        $fail++
    }
}

# ----------------------------------------------------------------
# 4. 系统监控守护任务（开机自启，每30分钟刷新一次状态文件）
# ----------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] 创建系统监控守护任务..." -ForegroundColor Yellow

# 开机自启：启动 perfect_monitor
$monTrigger  = New-ScheduledTaskTrigger -AtStartup
$monAction   = New-ScheduledTaskAction  -Execute $PythonPath `
                   -Argument "monitor\perfect_monitor.py --save-report" `
                   -WorkingDirectory $ProjectPath
$monSettings = New-ScheduledTaskSettingsSet `
                   -StartWhenAvailable `
                   -DontStopOnIdleEnd `
                   -AllowStartIfOnBatteries `
                   -ExecutionTimeLimit (New-TimeSpan -Days 365)
try {
    Register-ScheduledTask `
        -TaskName    "${TaskNamePrefix}Monitor" `
        -Description "PL5 - 系统监控守护进程 (开机自启)" `
        -Trigger     $monTrigger `
        -Action      $monAction `
        -Settings    $monSettings `
        -RunLevel    Highest `
        -Force | Out-Null
    Write-Host "    [OK]  ${TaskNamePrefix}Monitor (开机自启)" -ForegroundColor Green
    $ok++
} catch {
    Write-Host ("    [FAIL] ${TaskNamePrefix}Monitor - {0}" -f $_.Exception.Message) -ForegroundColor Red
    $fail++
}

# Watchdog: check every 5 minutes if auto_scheduler is running
$wdTrigger    = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -Once -At "00:00"
$wdScriptPath = Join-Path $ProjectPath "scripts\watchdog.ps1"
$wdAction     = New-ScheduledTaskAction -Execute "PowerShell.exe" `
                    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$wdScriptPath`""
$wdSettings   = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries
try {
    Register-ScheduledTask `
        -TaskName    "${TaskNamePrefix}Watchdog" `
        -Description "PL5 - 调度器看门狗 (每5分钟检查)" `
        -Trigger     $wdTrigger `
        -Action      $wdAction `
        -Settings    $wdSettings `
        -RunLevel    Highest `
        -Force | Out-Null
    Write-Host "    [OK]  ${TaskNamePrefix}Watchdog (每5分钟守护)" -ForegroundColor Green
    $ok++
} catch {
    Write-Host ("    [FAIL] ${TaskNamePrefix}Watchdog - {0}" -f $_.Exception.Message) -ForegroundColor Red
    $fail++
}

# ----------------------------------------------------------------
# 汇总
# ----------------------------------------------------------------
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ("  任务创建完成: {0} 成功, {1} 失败" -f $ok, $fail) -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  已注册任务（与系统内部调度保持一致）:" -ForegroundColor Green
Write-Host "    22:00  自动获取开奖数据          (WakeToRun=True)"  -ForegroundColor White
Write-Host "    22:15  评估预测准确性          (WakeToRun=True)"  -ForegroundColor White
Write-Host "    02:30  策略优化学习            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    04:00  深度学习训练            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    08:00  上午增量训练            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    10:00  首次预测验证            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    12:00  中午增量训练            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    14:00  下午增量训练            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    16:00  深度策略优化            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    17:00  预测预生成              (WakeToRun=True)"  -ForegroundColor White
Write-Host "    18:00  最终预测                (WakeToRun=True)"  -ForegroundColor White
Write-Host "    19:00  最终预测验证            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    20:00  售前最终预测            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    20:15  发送训练报告            (WakeToRun=True)"  -ForegroundColor White
Write-Host "    开机   监控守护进程"                    -ForegroundColor White
Write-Host "    每5分  调度器看门狗"                 -ForegroundColor White
Write-Host ""
Write-Host "  重要提示:" -ForegroundColor Yellow
Write-Host "    1. 确保电脑连接电源（笔记本必须插电）" -ForegroundColor Yellow
Write-Host "    2. BIOS 中启用 Wake on Timer / RTC Wake" -ForegroundColor Yellow
Write-Host "    3. 运行 scripts\setup_wake_timers.bat 配置电源选项" -ForegroundColor Yellow
Write-Host ""
Write-Host "  查看任务: 任务计划程序 -> 任务计划程序库" -ForegroundColor Cyan
Write-Host ""

if ($fail -gt 0) { exit 1 } else { exit 0 }
