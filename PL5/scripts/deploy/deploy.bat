@echo off

REM PL5 自动化部署脚本 V10.3
REM 用于部署PL5排列五预测系统

REM 脚本目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\.."

REM 日志文件
set "LOG_FILE=%PROJECT_ROOT%\logs\deploy.log"

REM 确保日志目录存在
mkdir "%PROJECT_ROOT%\logs" 2>nul

echo === PL5 自动化部署脚本 V10.3 ===
echo %date% %time% - 开始部署 >> "%LOG_FILE%"

REM 检查Python环境
echo 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: Python 未安装
    echo %date% %time% - 错误: Python 未安装 >> "%LOG_FILE%"
    pause
    exit /b 1
)

echo [OK] Python 已安装

REM 检查pip
echo 检查pip...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: pip 未安装
    echo %date% %time% - 错误: pip 未安装 >> "%LOG_FILE%"
    pause
    exit /b 1
)

echo [OK] pip 已安装

REM 【修复V10.1】依赖文件在 config/requirements.txt（不是根目录）
echo 检查依赖文件...
if not exist "%PROJECT_ROOT%\config\requirements.txt" (
    echo 错误: config\requirements.txt 未找到
    echo %date% %time% - 错误: config\requirements.txt 未找到 >> "%LOG_FILE%"
    pause
    exit /b 1
)

echo [OK] 依赖文件已找到（config/requirements.txt）

REM 安装依赖
echo 正在安装依赖...
echo %date% %time% - 开始安装依赖 >> "%LOG_FILE%"
pip install --upgrade pip
pip install -r "%PROJECT_ROOT%\config\requirements.txt"
if %errorlevel% neq 0 (
    echo 错误: 依赖安装失败
    echo %date% %time% - 错误: 依赖安装失败 >> "%LOG_FILE%"
    pause
    exit /b 1
)
echo [OK] 依赖安装完成
echo %date% %time% - 依赖安装完成 >> "%LOG_FILE%"

REM 【修复V10.1】检查Docker（非必须，仅在存在时构建）
echo 检查Docker...
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Docker 已安装

    REM 构建Docker镜像
    echo 正在构建Docker镜像...
    echo %date% %time% - 开始构建Docker镜像 >> "%LOG_FILE%"
    docker build -t pl5-system "%PROJECT_ROOT%"
    if %errorlevel% neq 0 (
        echo 警告: Docker镜像构建失败，跳过Docker构建
        echo %date% %time% - 警告: Docker镜像构建失败 >> "%LOG_FILE%"
    ) else (
        echo [OK] Docker镜像构建完成
        echo %date% %time% - Docker镜像构建完成 >> "%LOG_FILE%"
    )
) else (
    echo [跳过] Docker 未安装，跳过Docker构建
    echo %date% %time% - 跳过Docker构建 >> "%LOG_FILE%"
)

REM 【修复V10.1】运行快速冒烟测试（不依赖pytest）
echo 正在运行快速冒烟测试...
echo %date% %time% - 开始冒烟测试 >> "%LOG_FILE%"
cd /d "%PROJECT_ROOT%"
python "scripts\utility\smoke_test_v8.py" >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: 冒烟测试发现问题，建议手动检查
    echo %date% %time% - 警告: 冒烟测试失败 >> "%LOG_FILE%"
) else (
    echo [OK] 冒烟测试通过
    echo %date% %time% - 冒烟测试通过 >> "%LOG_FILE%"
)

REM 【修复V10.1】检查系统状态（使用正确命令 python main.py status）
echo 正在检查系统状态...
echo %date% %time% - 开始检查系统状态 >> "%LOG_FILE%"
python "%PROJECT_ROOT%\main.py" status
if %errorlevel% neq 0 (
    echo 警告: 系统状态检查失败，建议手动检查
    echo %date% %time% - 警告: 系统状态检查失败 >> "%LOG_FILE%"
) else (
    echo [OK] 系统状态检查完成
    echo %date% %time% - 系统状态检查完成 >> "%LOG_FILE%"
)

REM 启动服务
echo 正在启动服务...
echo %date% %time% - 开始启动服务 >> "%LOG_FILE%"

REM 检查主程序文件
if not exist "%PROJECT_ROOT%\src\app\auto_scheduler_v8.py" (
    echo 错误: src\app\auto_scheduler_v8.py 未找到
    echo %date% %time% - 错误: 主程序文件未找到 >> "%LOG_FILE%"
    pause
    exit /b 1
)

echo [OK] 主程序文件检查通过
echo [OK] 部署完成！
echo.
echo 启动方式:
echo   前台: start_pl5_foreground.bat
echo   后台: start_daemon.bat
echo   调度: python main.py schedule
echo.
pause
