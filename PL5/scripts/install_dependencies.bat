@echo off

REM 自动安装依赖库脚本
REM 版本: 1.0
REM 描述: 自动安装项目所需的所有依赖库，包括处理PyTorch安装错误

echo ===============================================
echo 排列五预测系统 - 自动依赖安装脚本
 echo ===============================================

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: Python 未安装或不在系统PATH中
    echo 请先安装Python 3.10+，然后重试
    pause
    exit /b 1
)

echo 正在升级pip...
python -m pip install --upgrade pip >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: pip升级失败，将使用当前版本
)

echo 正在安装核心依赖库...
python -m pip install numpy==1.26.2 pandas==2.1.4 scikit-learn==1.3.2 >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 核心依赖安装失败
    pause
    exit /b 1
)

echo 正在安装模型依赖库...
python -m pip install lightgbm==4.1.0 xgboost==2.0.3 >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: 模型依赖安装失败，将使用基础模型
)

echo 正在安装工具依赖库...
python -m pip install python-dotenv==1.0.0 requests==2.31.0 beautifulsoup4==4.12.2 lxml==4.9.3 >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: 工具依赖安装失败，部分功能可能无法使用
)

echo 正在尝试安装PyTorch (可选，用于RL模块)...
python -m pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: PyTorch安装失败，将使用NumPy实现的RL优化器
    echo 这不会影响系统的核心功能
)

echo 正在安装其他依赖库...
python -m pip install fastapi==0.104.1 uvicorn==0.24.0 openai==1.3.5 llama-cpp-python==0.2.43 >nul 2>&1

echo ===============================================
echo 依赖安装完成！
echo 系统现在应该可以正常运行了。
echo 即使PyTorch安装失败，系统也能使用NumPy实现的RL优化器。
echo ===============================================

pause
