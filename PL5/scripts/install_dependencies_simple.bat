@echo off

REM Auto dependency installation script
REM Version: 1.0
REM Description: Automatically installs all required dependencies

echo ===============================================
echo PL5 Prediction System - Auto Dependency Installer
echo ===============================================

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10+ first
    pause
    exit /b 1
)

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing core dependencies...
python -m pip install numpy pandas scikit-learn

echo Installing model dependencies...
python -m pip install lightgbm xgboost

echo Installing tool dependencies...
python -m pip install python-dotenv requests beautifulsoup4 lxml

echo Installing PyTorch (optional, for RL module)...
python -m pip install torch torchvision torchaudio || echo Warning: PyTorch installation failed, will use NumPy implementation

echo Installing other dependencies...
python -m pip install fastapi uvicorn openai llama-cpp-python

echo ===============================================
echo Dependency installation completed!
echo The system should now be able to run normally.
echo Even if PyTorch fails to install, the system will use NumPy implementation for RL optimization.
echo ===============================================

pause
