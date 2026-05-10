@echo off
chcp 65001 >nul
title 排列五智能分析系统 - 完美启动器 V10.3
color 0A

:: 设置窗口大小
mode con: cols=100 lines=40

echo.
echo  ╔════════════════════════════════════════════════════════════════════════════════╗
echo  ║                                                                                ║
echo  ║           排列五高阶数理分析与预测系统 - 完美启动器 V10.3                        ║
echo  ║                                                                                ║
echo  ║     基于HMM、Copula、BSTS、极值理论、混沌分析等高级数学模型                    ║
echo  ║                                                                                ║
echo  ╚════════════════════════════════════════════════════════════════════════════════╝
echo.

:: 检查管理员权限（可选）
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  [提示] 建议以管理员身份运行以获得最佳性能
    echo.
    timeout /t 2 >nul
)

:: 设置工作目录（返回到项目根目录）
cd /d "%~dp0\.."
echo  [工作目录] %CD%
echo.

:: 检查Python环境
echo  [1/4] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)
for /f "tokens=*" %%a in ('python --version 2^>^&1') do echo  [OK] Python版本: %%a
echo.

:: 检查必要文件
echo  [2/4] 检查系统文件...
if not exist "src\app\auto_scheduler_v8.py" (
    echo  [错误] 找不到 src\app\auto_scheduler_v8.py
    pause
    exit /b 1
)
if not exist "src\core\config.py" (
    echo  [错误] 找不到 src\core\config.py
    pause
    exit /b 1
)
echo  [OK] 系统文件检查通过
echo.

:: 创建必要目录
echo  [3/4] 创建系统目录...
if not exist "data\raw" mkdir "data\raw"
if not exist "data\processed" mkdir "data\processed"
REM 【修复】models 目录在项目根目录，不是 src\models（已由 src/core/config.py 自动创建）
if not exist "logs" mkdir "logs"
if not exist "results" mkdir "results"
if not exist "config" mkdir "config"
echo  [OK] 目录创建完成
echo.

:: 检查依赖
echo  [4/4] 检查系统依赖...
python -c "import pandas, numpy, scipy, sklearn, schedule" >nul 2>&1
if errorlevel 1 (
    echo  [警告] 部分依赖未安装，请运行: pip install -r config\requirements.txt
) else (
    echo  [OK] 依赖检查通过
)
echo.

:: 【修复V10.1】增加监控文件存在性检查，防止静默失败
:: 启动防睡眠程序
echo.
echo  ============================================
if exist "monitor\prevent_sleep.py" (
    echo   启动防睡眠保护...
    start /min "PL5-防睡眠" python monitor\prevent_sleep.py
    timeout /t 2 >nul
    echo   [OK] 防睡眠保护已启动
) else (
    echo   [跳过] monitor\prevent_sleep.py 不存在，跳过防睡眠保护
)
echo.

:: 启动系统监控
if exist "monitor\system_monitor.py" (
    echo   启动系统监控服务...
    start /min "PL5-监控" python monitor\system_monitor.py --watch --interval 30
    timeout /t 2 >nul
    echo   [OK] 监控服务已启动
) else (
    echo   [跳过] monitor\system_monitor.py 不存在，跳过系统监控
)
echo.
echo  ============================================
echo.

:: 显示定时任务信息（与客户配置一致）
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
echo  报告将发送至配置的邮箱
echo.
timeout /t 3 >nul

:: 启动主系统
:start_system
echo.
echo  ============================================
echo   启动主程序 (auto_scheduler_v8)...
echo  ============================================
:: 设置Python编码环境变量
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python -m src.app.auto_scheduler_v8

:: 如果程序异常退出，自动重启
echo.
echo  [警告] 主程序已停止，5秒后尝试重启...
timeout /t 5 >nul
goto :start_system
