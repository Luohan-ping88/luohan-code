#!/usr/bin/env python3
"""
C++模块兼容性测试脚本
检查C++加速模块的可用性、性能和兼容性
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("C++ 模块兼容性测试")
print("=" * 80)

# 1. 检查文件结构
print("\n[1] 检查文件结构:")
cpp_core_dir = Path(__file__).parent.parent / "cpp_core"
print(f"  目录存在: {cpp_core_dir.exists()}")

if cpp_core_dir.exists():
    files = {
        "C++头文件": cpp_core_dir / "feature_calculator.h",
        "C++实现": cpp_core_dir / "feature_calculator.cpp",
        "Python绑定": cpp_core_dir / "bindings.cpp",
        "Python包装器": cpp_core_dir / "pl5_core.py",
        "初始化文件": cpp_core_dir / "__init__.py",
        "编译配置": cpp_core_dir / "setup.py",
    }
    
    for name, path in files.items():
        status = "✓" if path.exists() else "✗"
        print(f"  {status} {name}: {path.name}")

# 2. 检查编译产物
print("\n[2] 检查编译产物:")
build_dirs = [
    cpp_core_dir / "build" / "lib.win-amd64-cpython-312",
    cpp_core_dir / "build" / "lib.linux-x86_64-cpython-312",
]

pyd_files = list(cpp_core_dir.glob("**/*.pyd"))
pyd_so_files = list(cpp_core_dir.glob("**/*.so"))

print(f"  找到 .pyd 文件: {len(pyd_files)}")
for f in pyd_files:
    if ".disabled" not in str(f):
        print(f"    ✓ {f.name}")
    else:
        print(f"    ✗ {f.name} (已禁用)")

print(f"  找到 .so 文件: {len(pyd_so_files)}")
for f in pyd_so_files:
    print(f"    ✓ {f.name}")

# 3. 测试C++模块导入
print("\n[3] 测试C++模块导入:")
try:
    from cpp_core import CPP_AVAILABLE, FeatureCalculator, HMMModel, CopulaModel, benchmark
    print(f"  ✓ 成功导入 cpp_core 模块")
    print(f"  C++可用状态: {CPP_AVAILABLE}")
    
    # 测试基本功能
    if CPP_AVAILABLE:
        print("\n[4] 测试C++功能:")
        test_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 100
        
        # 测试rolling_mean
        start = time.time()
        result = FeatureCalculator.rolling_mean(test_data, 5)
        elapsed = time.time() - start
        print(f"  ✓ rolling_mean: {len(result)} 结果, 耗时 {elapsed*1000:.2f}ms")
        
        # 测试rolling_std
        start = time.time()
        result = FeatureCalculator.rolling_std(test_data, 5)
        elapsed = time.time() - start
        print(f"  ✓ rolling_std: {len(result)} 结果, 耗时 {elapsed*1000:.2f}ms")
        
        # 测试calculate_hurst
        start = time.time()
        result = FeatureCalculator.calculate_hurst(test_data)
        elapsed = time.time() - start
        print(f"  ✓ calculate_hurst: {result:.4f}, 耗时 {elapsed*1000:.2f}ms")
        
        # 测试HMMModel
        print("\n[5] 测试HMMModel:")
        hmm = HMMModel(n_components=3)
        hmm.fit(test_data)
        states = hmm.predict(test_data)
        print(f"  ✓ HMM训练和预测成功, 状态数: {len(set(states))}")
        
        # 性能基准测试
        print("\n[6] 性能基准测试:")
        start = time.time()
        bench_result = benchmark()
        elapsed = time.time() - start
        print(f"  ✓ benchmark() 结果: {bench_result}ms")
        
    else:
        print("\n[4] C++模块未加载，使用Python回退实现")
        
except ImportError as e:
    print(f"  ✗ 导入失败: {e}")
    print("\n[4] Python回退测试:")
    try:
        from cpp_core import pl5_core
        print("  ✓ Python回退模块可用")
        
        # 测试Python实现
        test_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 100
        
        start = time.time()
        result = pl5_core.FeatureCalculator.rolling_mean(test_data, 5)
        elapsed = time.time() - start
        print(f"  ✓ Python rolling_mean: {len(result)} 结果, 耗时 {elapsed*1000:.2f}ms")
        
    except Exception as e2:
        print(f"  ✗ Python回退也失败: {e2}")

# 7. 检查与主系统的集成
print("\n[7] 检查与主系统的集成:")
try:
    from src.core.features.engineer import FeatureEngineer
    print("  ✓ FeatureEngineer 导入成功")
    
    # 检查是否有 cpp_available 属性
    engineer = FeatureEngineer.__new__(FeatureEngineer)
    if hasattr(engineer, 'cpp_available'):
        print(f"  ✓ FeatureEngineer 有 cpp_available 属性")
    else:
        print(f"  ⚠ FeatureEngineer 缺少 cpp_available 属性")
    
except Exception as e:
    print(f"  ✗ FeatureEngineer 导入失败: {e}")

# 8. 兼容性建议
print("\n[8] 兼容性建议:")
print("  1. 如果 C++模块未加载，检查是否已编译")
print("     Linux/Mac: cd cpp_core && python setup.py build_ext --inplace")
print("     Windows: 双击运行 build_cpp.bat")
print("  2. 确保已安装 pybind11: pip install pybind11")
print("  3. 检查Python版本 (需要 >= 3.8)")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
