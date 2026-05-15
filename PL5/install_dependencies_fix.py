#!/usr/bin/env python3
"""
PL5 依赖自动安装和修复脚本
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path("/workspace/PL5")

def log(message: str):
    """输出日志"""
    print(f"[安装脚本] {message}")

def install_package(package: str) -> bool:
    """安装单个包"""
    try:
        log(f"正在安装 {package}...")
        result = subprocess.run(
            ['pip', 'install', package, '-q', '--no-cache-dir'],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            log(f"✓ {package} 安装成功")
            return True
        else:
            log(f"✗ {package} 安装失败: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ {package} 安装失败: {str(e)}")
        return False

def install_all_dependencies():
    """安装所有必需依赖"""
    log("=" * 60)
    log("开始安装PL5项目依赖")
    log("=" * 60)

    # 核心依赖
    core_packages = [
        'numpy>=1.26.0',
        'pandas>=2.0.0',
        'scipy>=1.10.0',
        'scikit-learn>=1.3.0',  # 修复 sklearn
        'requests>=2.31.0',
        'psutil>=5.9.0',
        'joblib>=1.3.0',
        'matplotlib>=3.7.0',
        'tqdm>=4.65.0',
        'schedule>=1.2.0',
        'watchdog>=3.0.0',
    ]

    # 测试依赖
    test_packages = [
        'pytest>=7.0.0',
        'pytest-asyncio>=0.21.0',
    ]

    # 建议安装（可选）
    optional_packages = [
        'torch>=2.0.0',  # 修复 torch
        'lightgbm>=4.0.0',
        'xgboost>=2.0.0',
        'catboost>=1.0.0',
    ]

    success_count = 0
    total_count = len(core_packages) + len(test_packages) + len(optional_packages)

    log("\n安装核心依赖:")
    for pkg in core_packages:
        if install_package(pkg):
            success_count += 1

    log("\n安装测试依赖:")
    for pkg in test_packages:
        if install_package(pkg):
            success_count += 1

    log("\n安装可选依赖:")
    for pkg in optional_packages:
        if install_package(pkg):
            success_count += 1

    log("\n" + "=" * 60)
    log(f"依赖安装完成: {success_count}/{total_count} 成功")
    log("=" * 60)

    return success_count == total_count

def check_installation():
    """检查依赖安装情况"""
    log("\n检查依赖安装情况:")

    packages = [
        'numpy',
        'pandas',
        'scipy',
        'sklearn',  # scikit-learn
        'requests',
        'psutil',
        'joblib',
        'matplotlib',
        'tqdm',
        'schedule',
        'watchdog',
        'pytest',
    ]

    all_ok = True
    for pkg in packages:
        try:
            if pkg == 'sklearn':
                import sklearn
            else:
                __import__(pkg)
            log(f"✓ {pkg}")
        except ImportError:
            log(f"✗ {pkg} 未安装")
            all_ok = False

    return all_ok

def verify_modules():
    """验证关键模块是否可以导入"""
    log("\n验证关键模块:")

    modules = [
        'src.core.models.predictor',
        'src.core.models.model_evaluator',
        'src.core.data.collector',
        'src.ai.tools.pl5_tool',
        'src.ai.agents.agent_orchestrator',
        'src.app.intelligent_scheduler_integration',
        'src.core.utils.unified_error_handler'
    ]

    all_ok = True
    for module in modules:
        try:
            __import__(module)
            log(f"✓ {module}")
        except Exception as e:
            log(f"✗ {module}: {str(e)}")
            all_ok = False

    return all_ok

def main():
    """主函数"""
    print("=" * 60)
    print("PL5 依赖自动安装和修复工具")
    print("=" * 60)

    # 1. 安装依赖
    install_all_dependencies()

    # 2. 检查安装
    check_installation()

    # 3. 验证模块
    if verify_modules():
        print("\n✓ 所有模块验证通过！")
    else:
        print("\n✗ 部分模块验证失败，请检查错误信息")
        print("可能需要重新运行此脚本或手动安装缺失依赖")

if __name__ == "__main__":
    main()
