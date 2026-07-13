@echo off
chcp 65001 >nul
::: 【修复V10.1】使用 %~dp0 动态获取脚本所在目录，移除硬编码路径
cd /d "%~dp0"
echo ============================================================
echo PL5智能分析系统启动中 (V10.3)...
echo ============================================================
echo.
python -m src.app.auto_scheduler_v8
if %errorlevel% neq 0 (
    echo.
    echo 系统异常退出！按任意键退出...
    pause >nul
)
