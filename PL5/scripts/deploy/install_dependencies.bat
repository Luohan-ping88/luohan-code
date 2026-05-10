@echo off
chcp 65001 >nul
title PL5 依赖自动安装
color 0A

echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                                                                       ║
echo ║           PL5排列五智能分析系统 - 依赖自动安装程序                    ║
echo ║                                                                       ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

:: 设置工作目录为PL5根目录
cd /d "%~dp0\..\.."

echo 工作目录: %CD%
echo.

:: 检查Python是否安装
echo [1/6] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到Python，请先安装Python 3.8或更高版本
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] Python已安装: %PYTHON_VERSION%
echo.

:: 检查并升级pip
echo [2/6] 检查pip版本...
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip未正确安装
    exit /b 1
)

echo [OK] 正在升级pip到最新版本...
python -m pip install --upgrade pip -q
echo [OK] pip升级完成
echo.

:: 创建虚拟环境（可选）
echo [3/6] 检查虚拟环境...
if not exist "venv" (
    echo 正在创建Python虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [WARN] 虚拟环境创建失败，将使用系统Python
    ) else (
        echo [OK] 虚拟环境创建成功
    )
) else (
    echo [OK] 虚拟环境已存在
)

:: 激活虚拟环境（如果存在）
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] 虚拟环境已激活
)
echo.

:: 安装核心依赖
echo [4/6] 安装核心依赖库...
echo 正在读取 requirements.txt...
if exist "config\requirements.txt" (
    echo 使用 config\requirements.txt
    python -m pip install -r config\requirements.txt
) else if exist "requirements.txt" (
    echo 使用根目录 requirements.txt
    python -m pip install -r requirements.txt
) else (
    echo [ERROR] 未找到依赖文件！
    exit /b 1
)

if errorlevel 1 (
    echo [ERROR] 依赖安装过程中出现错误
    exit /b 1
)

echo [OK] 核心依赖安装完成
echo.

:: 验证依赖安装
echo [5/6] 验证依赖安装...
set ALL_OK=1

python -c "import numpy; print('[OK] numpy '+numpy.__version__)" 2>nul || (
    echo [FAIL] numpy 未安装
    set ALL_OK=0
)

python -c "import pandas; print('[OK] pandas '+pandas.__version__)" 2>nul || (
    echo [FAIL] pandas 未安装
    set ALL_OK=0
)

python -c "import scipy; print('[OK] scipy '+scipy.__version__)" 2>nul || (
    echo [FAIL] scipy 未安装
    set ALL_OK=0
)

python -c "import sklearn; print('[OK] scikit-learn '+sklearn.__version__)" 2>nul || (
    echo [FAIL] scikit-learn 未安装
    set ALL_OK=0
)

python -c "import schedule; print('[OK] schedule installed')" 2>nul || (
    echo [FAIL] schedule 未安装
    set ALL_OK=0
)

python -c "import psutil; print('[OK] psutil '+psutil.__version__)" 2>nul || (
    echo [FAIL] psutil 未安装
    set ALL_OK=0
)

echo.

if "%ALL_OK%"=="0" (
    echo [WARN] 部分依赖未正确安装，请检查错误信息
) else (
    echo [OK] 所有核心依赖验证通过
)
echo.

:: 创建必要的目录
echo [6/6] 创建必要的目录结构...
if not exist "logs" mkdir logs
if not exist "data\raw" mkdir data\raw
if not exist "data\processed" mkdir data\processed
if not exist "models" mkdir models
if not exist "backups" mkdir backups
if not exist "health" mkdir health
echo [OK] 目录结构创建完成
echo.

echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                                                                       ║
echo ║                    [OK] 依赖安装完成！                                 ║
echo ║                                                                       ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo 依赖安装完成
