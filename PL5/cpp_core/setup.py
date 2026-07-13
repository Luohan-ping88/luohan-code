"""
C++扩展模块编译配置
使用pybind11创建Python绑定
"""

from pybind11.setup_helpers import Pybind11Extension, build_ext
import pybind11
from setuptools import setup
import platform
import sys

# ──────────────────────────────────────────────────────────
# 编译参数：按平台选择最优标志
# ──────────────────────────────────────────────────────────
_sys = platform.system()

if _sys == "Windows":
    # MSVC: O2全速优化 | openmp | 关警告噪声 | 启用AVX2(可选)
    extra_compile_args = [
        '/O2',          # 全速优化（等价 GCC -O2）
        '/GL',          # 全程序优化 (Link-Time Optimization)
        '/openmp',      # OpenMP 并行支持
        '/EHsc',        # 异常处理
        '/std:c++17',   # C++17 标准
        '/W3',          # 中等警告级别（/W4 过于嘈杂）
        '/wd4267',      # 关闭 size_t → int 转换警告
        '/wd4244',      # 关闭 double → float 转换警告
    ]
    extra_link_args = ['/LTCG']     # 链接时代码生成（配合 /GL）
    define_macros = [('_USE_MATH_DEFINES', None)]  # 启用 M_PI 等常量

elif _sys == "Linux":
    extra_compile_args = [
        '-O3',          # 最高级别优化
        '-march=native', # 针对当前 CPU 架构（包括 AVX/AVX2/SSE4 等）
        '-funroll-loops',# 循环展开
        '-ffast-math',  # 放宽浮点精度以提速（适合统计场景）
        '-fopenmp',     # OpenMP 并行
        '-std=c++17',
        '-fPIC',
        '-Wall',
        '-Wno-unused-parameter',
    ]
    extra_link_args = ['-fopenmp', '-pthread']
    define_macros = []

elif _sys == "Darwin":  # macOS（clang 默认不支持 -fopenmp，用 libomp）
    extra_compile_args = [
        '-O3',
        '-march=native',
        '-funroll-loops',
        '-ffast-math',
        '-std=c++17',
        '-fPIC',
        '-Wall',
    ]
    extra_link_args = ['-pthread']
    define_macros = []

else:
    extra_compile_args = ['-O2', '-std=c++17']
    extra_link_args = []
    define_macros = []

ext_modules = [
    Pybind11Extension(
        "pl5_core",
        sources=[
            "bindings.cpp",
            "feature_calculator.cpp",
        ],
        include_dirs=[
            pybind11.get_include(),
        ],
        language='c++',
        cxx_std=17,
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
        define_macros=define_macros,
    ),
]

setup(
    name="pl5_core",
    version="1.1.0",      # 升级至 1.1.0 以标记本次优化
    author="PL5 Team",
    description="排列五高性能计算核心模块（O(n)滑动窗口 + Cooley-Tukey FFT + OpenMP）",
    long_description=(
        "使用C++实现的高性能特征计算和模型训练模块。\n"
        "V1.1优化：rollingMean/Std O(n²)→O(n)，FFT O(n²)→O(n log n)，"
        "rollingFrequency O(n×w)→O(n)，OpenMP并行支持。"
    ),
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.8",
)
