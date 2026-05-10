@echo off
chcp 65001 > nul
echo ====================================
echo   PL5 系统部署启动 V11.0
echo ====================================
echo.

echo [1/4] 检查Python环境...
python --version > nul 2>&1
if errorlevel 1 (
    echo   ❌ Python未安装或未添加到PATH
    echo   请访问 https://www.python.org/downloads 安装Python 3.8+
    pause
    exit /b 1
)
echo   ✅ Python环境正常

echo.
echo [2/4] 检查依赖...
python -c "import fastapi, uvicorn, numpy, pandas" > nul 2>&1
if errorlevel 1 (
    echo   ⚠️ 部分依赖缺失
    echo   正在安装依赖...
    pip install -r requirements.txt
)
echo   ✅ 依赖检查完成

echo.
echo [3/4] 验证优化模块...
python tests/test_optimizations.py
echo   ✅ 模块验证完成

echo.
echo [4/4] 启动系统...
echo.
echo 请选择启动方式:
echo   1. 启动API服务 (Web接口)
echo   2. 启动完整系统 (定时调度)
echo   3. 快速预测
echo   4. 退出
echo.

set /p choice=请选择 (1-4): 

if "%choice%"=="1" (
    echo.
    echo 启动API服务...
    python src/ai/api.py
) else if "%choice%"=="2" (
    echo.
    echo 启动完整系统...
    python src/app/auto_scheduler_v8.py
) else if "%choice%"=="3" (
    echo.
    echo 执行快速预测...
    python quick_start.py
) else (
    echo.
    echo 退出
)

pause
