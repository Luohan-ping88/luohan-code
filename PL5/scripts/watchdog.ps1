# PL5系统看门狗 PowerShell脚本 V2.0
# 功能：监控PL5系统进程，崩溃时自动重启
# 【修复】使用精确匹配，避免误杀外部Python进程

$ErrorActionPreference = "SilentlyContinue"

# PL5系统进程标识符
$PL5_IDENTIFIERS = @(
    'auto_scheduler_v8',
    'process_watchdog',
    'prevent_sleep',
    'pl5_intelligent_system'
)

# 配置
$checkInterval = 30  # 检查间隔（秒）
$maxRestarts = 5     # 最大重启次数
$restartWindow = 3600 # 重启窗口（秒）
$restartHistory = @()

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Write-Host $logEntry
    
    # 同时写入日志文件
    $logDir = Join-Path $PSScriptRoot "..\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $logFile = Join-Path $logDir "watchdog.log"
    Add-Content -Path $logFile -Value $logEntry -Encoding UTF8
}

function Test-PL5ProcessRunning {
    # 【修复V2.0】精确匹配PL5进程
    $processes = Get-Process -Name python*, pythonw* -ErrorAction SilentlyContinue
    foreach ($proc in $processes) {
        try {
            $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)").CommandLine
            if ($cmdline) {
                $cmdlineLower = $cmdline.ToLower()
                $hasPL5Id = $PL5_IDENTIFIERS | Where-Object { $cmdlineLower.Contains($_) }
                if ($hasPL5Id) {
                    return $true
                }
            }
        } catch {
            # 忽略访问被拒绝的进程
        }
    }
    return $false
}

function Get-PL5Processes {
    # 【修复V2.0】获取所有PL5相关进程
    $pl5Procs = @()
    $processes = Get-Process -Name python*, pythonw* -ErrorAction SilentlyContinue
    foreach ($proc in $processes) {
        try {
            $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)").CommandLine
            if ($cmdline) {
                $cmdlineLower = $cmdline.ToLower()
                $hasPL5Id = $PL5_IDENTIFIERS | Where-Object { $cmdlineLower.Contains($_) }
                if ($hasPL5Id) {
                    $pl5Procs += [PSCustomObject]@{
                        Id = $proc.Id
                        Name = $proc.ProcessName
                        CommandLine = $cmdline.Substring(0, [Math]::Min(100, $cmdline.Length))
                    }
                }
            }
        } catch {
            # 忽略访问被拒绝的进程
        }
    }
    return $pl5Procs
}

function Stop-PL5Processes {
    # 【修复V2.0】只停止PL5相关进程
    Write-Log "正在停止所有PL5相关进程..."
    $pl5Procs = Get-PL5Processes
    
    if ($pl5Procs.Count -eq 0) {
        Write-Log "未发现PL5相关进程"
        return
    }
    
    foreach ($proc in $pl5Procs) {
        try {
            Write-Log "  终止PL5进程 PID=$($proc.Id): $($proc.CommandLine)..."
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Log "  无法终止进程 $($proc.Id): $($_.Exception.Message)" "WARN"
        }
    }
    
    # 等待进程终止
    Start-Sleep -Seconds 2
    
    # 验证
    $remaining = Get-PL5Processes
    if ($remaining.Count -eq 0) {
        Write-Log "所有PL5进程已安全停止"
    } else {
        Write-Log "警告: 仍有 $($remaining.Count) 个PL5进程残留" "WARN"
    }
}

function Start-PL5System {
    Write-Log "正在启动PL5系统..."
    
    # 清理过期的重启记录
    $cutoff = (Get-Date).AddSeconds(-$restartWindow)
    $restartHistory = $restartHistory | Where-Object { $_ -gt $cutoff }
    
    if ($restartHistory.Count -ge $maxRestarts) {
        Write-Log "重启次数过多 ($($restartHistory.Count)次/$restartWindow秒)，停止重启" "ERROR"
        return $false
    }
    
    $baseDir = Join-Path $PSScriptRoot ".."
    $scriptPath = Join-Path $baseDir "src\app\auto_scheduler_v8.py"
    
    if (-not (Test-Path $scriptPath)) {
        Write-Log "找不到主程序: $scriptPath" "ERROR"
        return $false
    }
    
    try {
        # 使用Start-Process启动，不等待
        $pythonPath = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
        if (-not $pythonPath) {
            $pythonPath = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
        }
        
        if (-not $pythonPath) {
            Write-Log "找不到Python解释器" "ERROR"
            return $false
        }
        
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $pythonPath
        $startInfo.Arguments = "-m src.app.auto_scheduler_v8"
        $startInfo.WorkingDirectory = $baseDir
        $startInfo.UseShellExecute = $true
        $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        
        [System.Diagnostics.Process]::Start($startInfo) | Out-Null
        
        $restartHistory += Get-Date
        Write-Log "PL5系统已启动"
        return $true
    } catch {
        Write-Log "启动失败: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

# 主循环
Write-Log "=" * 80
Write-Log "PL5系统看门狗 V2.0 启动"
Write-Log "【修复】精确匹配PL5系统进程，避免误杀外部Python进程"
Write-Log "=" * 80

# 启动时如果PL5未运行，则启动
if (-not (Test-PL5ProcessRunning)) {
    Write-Log "启动时检测到PL5未运行，正在启动..."
    Start-PL5System
}

while ($true) {
    try {
        $isRunning = Test-PL5ProcessRunning
        
        if (-not $isRunning) {
            Write-Log "检测到PL5系统未运行，准备重启..." "WARN"
            Start-PL5System
        } else {
            # 可选：健康检查
            $pl5Procs = Get-PL5Processes
            Write-Log "PL5系统运行正常，监控 $($pl5Procs.Count) 个进程" "DEBUG"
        }
        
        Start-Sleep -Seconds $checkInterval
    } catch {
        Write-Log "看门狗异常: $($_.Exception.Message)" "ERROR"
        Start-Sleep -Seconds 5
    }
}
