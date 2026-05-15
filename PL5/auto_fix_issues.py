#!/usr/bin/env python3
"""
PL5 问题自动修复脚本
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path("/workspace/PL5")
sys.path.insert(0, str(PROJECT_ROOT))

def log(message: str):
    """输出日志"""
    print(f"[修复脚本] {message}")

def fix_data_collector():
    """修复数据收集器导入问题"""
    log("检查数据收集器...")

    collector_file = PROJECT_ROOT / "src" / "core" / "data" / "collector.py"

    if not collector_file.exists():
        log("collector.py 不存在，跳过")
        return False

    # 读取文件内容
    with open(collector_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已经有别名
    if 'DataCollector' in content and 'PL5DataCollectorV8' in content:
        log("DataCollector 别名已存在")
        return True

    # 找到 __all__ 或类定义附近，添加别名
    if 'class PL5DataCollectorV8' in content:
        # 在 __all__ 中添加 DataCollector
        if '__all__' in content:
            content = content.replace(
                '__all__ = [',
                '__all__ = [\n    "DataCollector",'
            )

        # 在文件末尾添加别名
        content = content.rstrip() + '\n\n\n# 别名以保持向后兼容\nDataCollector = PL5DataCollectorV8\n'

        with open(collector_file, 'w', encoding='utf-8') as f:
            f.write(content)

        log("✓ 已添加 DataCollector 别名")
        return True

    return False

def fix_pl5_tool():
    """修复PL5工具缺少的方法"""
    log("检查PL5工具...")

    tool_file = PROJECT_ROOT / "src" / "ai" / "tools" / "pl5_tool.py"

    if not tool_file.exists():
        log("pl5_tool.py 不存在，跳过")
        return False

    # 读取文件内容
    with open(tool_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已经有 get_schema 方法
    if 'def get_schema' in content:
        log("get_schema 方法已存在")
        return True

    # 如果有 PL5Tool 类但不包含 get_schema，添加一个基础实现
    if 'class PL5Tool' in content:
        # 找到类定义结束位置，在最后一个方法后添加 get_schema
        # 这是一个简单的占位符实现
        schema_method = '''

    def get_schema(self):
        """获取工具的JSON Schema
        
        Returns:
            dict: 工具的schema定义
        """
        return {
            "name": "pl5_predict",
            "description": "PL5预测工具，用于执行训练和预测任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "要执行的操作",
                        "enum": ["train", "predict", "evaluate"]
                    },
                    "params": {
                        "type": "object",
                        "description": "操作参数"
                    }
                },
                "required": ["action"]
            }
        }
'''
        # 在 class 结束前添加方法（需要找到类的结尾）
        # 简单方法：在最后一个方法定义后添加
        lines = content.split('\n')
        last_def_line = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('def ') and 'class PL5Tool' not in line:
                # 检查是否在类内（通过缩进来判断）
                if i > 0 and lines[i-1].strip().startswith('#') or lines[i-1].startswith('        ') or lines[i-1].startswith('\t'):
                    last_def_line = i

        if last_def_line > 0:
            lines.insert(last_def_line + 1, schema_method)
            content = '\n'.join(lines)

            with open(tool_file, 'w', encoding='utf-8') as f:
                f.write(content)

            log("✓ 已添加 get_schema 方法")
            return True

    return False

def fix_async_queue():
    """修复 AsyncQueue 导入问题"""
    log("检查 AsyncQueue 问题...")

    # AsyncQueue 应该是 asyncio.Queue
    # 查找相关导入
    files_to_check = [
        PROJECT_ROOT / "src" / "ai" / "agents" / "agent_orchestrator.py",
        PROJECT_ROOT / "src" / "app" / "intelligent_scheduler_integration.py",
    ]

    fixed = False
    for file_path in files_to_check:
        if not file_path.exists():
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if 'from typing import' in content and 'AsyncQueue' in content:
            # 替换为 asyncio.Queue
            content = content.replace('AsyncQueue', 'asyncio.Queue')
            # 确保导入了 asyncio
            if 'import asyncio' not in content:
                content = 'import asyncio\n' + content

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            log(f"✓ 已修复 {file_path.name} 中的 AsyncQueue 问题")
            fixed = True

    return fixed

def run_all_fixes():
    """运行所有修复"""
    print("=" * 60)
    print("PL5 问题自动修复工具")
    print("=" * 60)

    fixes_applied = []

    # 1. 修复 DataCollector
    if fix_data_collector():
        fixes_applied.append("DataCollector 别名")

    # 2. 修复 PL5Tool get_schema
    if fix_pl5_tool():
        fixes_applied.append("PL5Tool get_schema 方法")

    # 3. 修复 AsyncQueue
    if fix_async_queue():
        fixes_applied.append("AsyncQueue 导入问题")

    print()
    print("=" * 60)
    print("修复结果:")
    print("=" * 60)

    if fixes_applied:
        print("已应用的修复:")
        for fix in fixes_applied:
            print(f"  ✓ {fix}")
    else:
        print("  无需修复或未找到可修复的问题")

    print("=" * 60)

    return len(fixes_applied) > 0

if __name__ == "__main__":
    success = run_all_fixes()
    sys.exit(0 if success else 1)
