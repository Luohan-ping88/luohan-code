#!/usr/bin/env python
"""系统诊断脚本 - 检查导入和依赖问题"""
import sys
import traceback
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("PL5 系统诊断")
print("=" * 80)

# 1. 检查Python版本
print(f"\n[1] Python版本: {sys.version}")

# 2. 检查关键依赖
dependencies = [
    ("numpy", "1.26.2"),
    ("pandas", "2.1.4"),
    ("sklearn", "1.3.2"),  # scikit-learn
]

print("\n[2] 依赖检查:")
for module, expected_version in dependencies:
    try:
        mod = __import__(module)
        version = getattr(mod, "__version__", "未知")
        status = "✓"
        if module == "sklearn":
            module = "scikit-learn"
        print(f"  {status} {module}: {version}")
    except ImportError as e:
        print(f"  ✗ {module}: 未安装 - {e}")

# 3. 测试特征模块的分步导入
print("\n[3] 特征模块导入测试:")

# 先测试独立的导入
test_modules = [
    "src.core.features.feature_config_manager",
    "src.core.features.engineer_v10",  # 先测试V10
]

for module_path in test_modules:
    try:
        __import__(module_path)
        print(f"  ✓ {module_path}")
    except Exception as e:
        print(f"  ✗ {module_path}: {e}")
        traceback.print_exc()

print("\n[4] 测试engineer.py (带sklearn):")
try:
    from src.core.features import engineer
    print("  ✓ engineer模块导入成功")
except Exception as e:
    print(f"  ✗ 导入失败: {e}")
    traceback.print_exc()

print("\n[5] 检查src/core/features目录:")
features_dir = Path(__file__).parent.parent / "src" / "core" / "features"
print(f"  目录存在: {features_dir.exists()}")
if features_dir.exists():
    files = list(features_dir.glob("*.py"))
    print(f"  文件数: {len(files)}")
    for f in sorted(files):
        print(f"    - {f.name}")

print("\n" + "=" * 80)
print("诊断完成")
print("=" * 80)
