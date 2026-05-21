#!/usr/bin/env python3
"""
PL5 核心依赖快速安装脚本
仅安装最关键的依赖包以快速验证系统
"""

import os
import sys
import subprocess
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

def log(message, level="INFO"):
    """简单日志"""
    print(f"[{level}] {message}")

def install_package(package, description=None):
    """安装单个包"""
    desc = f" ({description})" if description else ""
    log(f"正在安装 {package}{desc}...")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            log(f"✓ {package} 安装成功")
            return True
        else:
            log(f"✗ {package} 安装失败: {result.stderr[-200:]}", "ERROR")
            return False
    except Exception as e:
        log(f"✗ {package} 安装出错: {e}", "ERROR")
        return False

def verify_package(package):
    """验证包是否可导入"""
    try:
        __import__(package)
        return True
    except ImportError:
        return False

def main():
    log("=" * 60)
    log("PL5 核心依赖快速安装")
    log("=" * 60)
    
    # 核心依赖包列表
    core_packages = [
        ("numpy", "数值计算基础"),
        ("pandas", "数据处理"),
        ("scikit-learn", "机器学习"),
    ]
    
    # 安装核心包
    success_count = 0
    for package, desc in core_packages:
        if install_package(package, desc):
            success_count += 1
    
    # 验证安装
    log("\n" + "=" * 60)
    log("验证安装结果")
    log("=" * 60)
    
    all_ok = True
    import_map = {
        "numpy": "numpy",
        "pandas": "pandas",
        "sklearn": "scikit-learn"
    }
    
    for import_name, package_name in import_map.items():
        if verify_package(import_name):
            log(f"✓ {package_name} 验证通过")
        else:
            log(f"✗ {package_name} 验证失败", "ERROR")
            all_ok = False
    
    log("=" * 60)
    if all_ok:
        log("✓ 所有核心依赖安装成功！")
        return 0
    else:
        log("✗ 部分核心依赖安装失败！", "ERROR")
        return 1

if __name__ == "__main__":
    sys.exit(main())

