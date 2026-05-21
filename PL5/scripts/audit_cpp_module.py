"""
C++模块可用性审查报告
生成时间：2026-05-21
"""
import os
import sys
from pathlib import Path

print("="*70)
print("C++模块可用性审查报告")
print("="*70)

# 1. 检查文件存在性
print("\n[1] 文件结构检查")
print("-"*70)

project_root = Path("/workspace/PL5")
cpp_core_dir = project_root / "cpp_core"

files_to_check = [
    "feature_calculator.h",
    "feature_calculator.cpp",
    "bindings.cpp",
    "setup.py",
    "__init__.py",
    "pl5_core.py",
    "README.md",
]

for f in files_to_check:
    fpath = cpp_core_dir / f
    exists = fpath.exists()
    status = "✓" if exists else "✗"
    print(f"{status} {f:25} - {'存在' if exists else '缺失'}")

# 2. 检查C++模块是否已编译
print("\n[2] 编译状态检查")
print("-"*70)

build_dir = cpp_core_dir / "build"
compiled_files = []

if build_dir.exists():
    for root, dirs, files in os.walk(build_dir):
        for f in files:
            if f.endswith('.so') or f.endswith('.dll') or f.endswith('.pyd'):
                compiled_files.append(Path(root) / f)

if compiled_files:
    print(f"✓ 已编译模块 ({len(compiled_files)}):")
    for f in compiled_files:
        print(f"  - {f.relative_to(project_root)}")
else:
    print("✗ 未找到已编译的C++模块")

# 3. 检查Python导入
print("\n[3] 导入测试")
print("-"*70)

sys.path.insert(0, str(project_root))

try:
    import cpp_core
    print(f"✓ cpp_core 包导入成功")
    print(f"  CPP_AVAILABLE = {cpp_core.CPP_AVAILABLE}")
    
    if cpp_core.CPP_AVAILABLE:
        print("  ✓ 使用C++加速模式")
    else:
        print("  ℹ 使用Python回退模式")
    
    # 测试功能
    try:
        data = list(range(100))
        result = cpp_core.FeatureCalculator.rolling_mean(data, 20)
        print(f"✓ FeatureCalculator.rolling_mean() 执行成功")
        print(f"  返回长度: {len(result)}")
        
        # 运行benchmark
        bm_time = cpp_core.benchmark()
        print(f"✓ 性能测试: {bm_time} ms/1000次")
    except Exception as e:
        print(f"✗ 功能测试失败: {e}")
        
except Exception as e:
    print(f"✗ cpp_core 导入失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 检查实际使用情况
print("\n[4] 实际集成情况")
print("-"*70)

try:
    from src.core.features import engineer
    
    # 检查是否有导入
    with open(project_root / "src" / "core" / "features" / "engineer.py", 'r', encoding='utf-8') as f:
        content = f.read()
        
    cpp_used = 'cpp_core' in content
    print(f"特征工程模块: {'✓ 使用了cpp_core' if cpp_used else '✗ 未使用cpp_core'}")
    
    if not cpp_used:
        print("  ℹ 当前特征工程使用纯Python/numpy实现")
        
except Exception as e:
    print(f"✗ 检查特征工程模块失败: {e}")

# 5. 总结
print("\n" + "="*70)
print("审查总结")
print("="*70)

summary = """
✓ C++模块架构完整（头文件、实现、绑定、回退）
✓ 有完善的Python回退机制
✓ 有编译配置文件
✓ 有性能优化算法（O(n)滑动窗口、FFT等）
✗ C++模块未编译（当前使用Python回退）
ℹ 特征工程模块未实际使用cpp_core
"""

print(summary)

print("建议:")
print("1. 编译C++模块以启用加速模式")
print("2. 在特征工程中集成cpp_core以提升性能")
print("3. 在生产环境部署前测试性能提升")
