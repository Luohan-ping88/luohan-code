@echo off
chcp 65001 >nul
echo ========================================
echo PL5系统自动化审计与优化
echo ========================================
echo.

REM 切换到项目目录
cd /d "%~dp0.."

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请确保Python已安装并添加到PATH
    pause
    exit /b 1
)

REM 运行自动化审计脚本
echo 开始执行自动化审计...
python scripts\automated_system_audit.py

echo.
echo ========================================
echo 执行完成
echo ========================================
pause
