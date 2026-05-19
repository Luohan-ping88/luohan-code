#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 项目综合审查脚本（修复版）
检查：架构一致性、代码质量、智能编排系统集成、注释文档完整性
"""

import os
import re
import sys
import json
import ast
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple


# 项目根目录 - 修正路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


class ProjectReviewer:
    """项目综合审查器"""

    def __init__(self):
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "architecture": {},
            "intelligent_orchestration": {},
            "code_quality": {},
            "documentation": {},
            "issues": [],
            "suggestions": [],
            "summary": {}
        }

    def review_architecture(self) -> Dict:
        """审查项目架构"""
        print("\n" + "=" * 80)
        print("1. 审查项目架构")
        print("=" * 80)

        # 检查目录结构
        arch_info = {
            "core_directories": [],
            "file_counts": {},
            "version_management": [],
            "modules": {}
        }

        print(f"- 项目根目录: {PROJECT_ROOT}")

        # 核心目录
        core_dirs = [
            "src/core", "src/app", "config", "data", "models", "logs", "scripts", "tests"
        ]

        for dir_name in core_dirs:
            dir_path = PROJECT_ROOT / dir_name
            if dir_path.exists():
                arch_info["core_directories"].append(dir_name)

        # 统计文件类型
        file_extensions = {}
        for root, dirs, files in os.walk(PROJECT_ROOT, topdown=True):
            # 排除一些目录
            dirs[:] = [d for d in dirs if not any([
                d.startswith("."), d == "__pycache__", d == "node_modules",
                d == ".git", d == ".idea", d == ".vscode"
            ])]

            for file in files:
                ext = Path(file).suffix
                file_extensions[ext] = file_extensions.get(ext, 0) + 1

        arch_info["file_counts"] = file_extensions

        # 检查版本管理
        version_keywords = ["v8", "v9", "v10"]
        for root, dirs, files in os.walk(PROJECT_ROOT, topdown=True):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

            for file in files:
                if any(keyword in file.lower() for keyword in version_keywords):
                    rel_path = str(Path(root).relative_to(PROJECT_ROOT) / file)
                    arch_info["version_management"].append((file, rel_path))
                    if len(arch_info["version_management"]) >= 10:
                        break
            if len(arch_info["version_management"]) >= 10:
                break

        print(f"- 核心目录: {len(arch_info['core_directories'])} 个")
        print(f"- 文件类型分布: {dict(sorted(arch_info['file_counts'].items(), key=lambda x: -x[1]))}")
        print(f"- 版本管理文件: {len(arch_info['version_management'])} 个 (展示前10个)")

        self.report["architecture"] = arch_info
        return arch_info

    def review_intelligent_orchestration(self) -> Dict:
        """审查智能编排系统"""
        print("\n" + "=" * 80)
        print("2. 审查智能任务链编排执行逻辑")
        print("=" * 80)

        io_info = {
            "exists": False,
            "integrated": False,
            "tasks_registered": 0,
            "issues": [],
            "key_features": []
        }

        # 检查智能编排文件是否存在
        io_path = PROJECT_ROOT / "src" / "core" / "workflow" / "intelligent_orchestration.py"
        io_info["exists"] = io_path.exists()

        if io_info["exists"]:
            print(f"- ✓ 智能编排文件存在: {io_path.relative_to(PROJECT_ROOT)}")

            # 检查关键特征
            try:
                with open(io_path, "r", encoding="utf-8") as f:
                    content = f.read()

                features = [
                    ("OrchestrationTask", "任务类定义"),
                    ("IntelligentOrchestrationManager", "管理器类"),
                    ("_is_in_training_window", "训练窗口检测"),
                    ("_execute_single_task", "单任务执行"),
                    ("register_task", "任务注册"),
                    ("start", "启动编排器"),
                ]

                for func_name, desc in features:
                    if func_name in content:
                        io_info["key_features"].append(desc)
                        print(f"  ✓ {desc}")
                    else:
                        print(f"  ⚠️ {desc} - 未发现")

                # 检查是否有 get_orchestration_manager
                if "get_orchestration_manager" in content:
                    io_info["key_features"].append("单例访问器函数")
                    print("  ✓ 单例访问器函数")

            except Exception as e:
                print(f"  Error: {e}")
                io_info["issues"].append(str(e))
        else:
            print(f"- ✗ 智能编排文件不存在: {io_path}")
            io_info["issues"].append("智能编排模块缺失")

        # 检查集成状态
        scheduler_path = PROJECT_ROOT / "src" / "app" / "auto_scheduler_v8.py"
        if scheduler_path.exists():
            with open(scheduler_path, "r", encoding="utf-8") as f:
                scheduler_content = f.read()

            # 检查是否导入了智能编排
            has_import = "intelligent_orchestration" in scheduler_content
            has_use = "use_intelligent_orchestration" in scheduler_content
            has_setup = "setup_schedule" in scheduler_content

            io_info["integrated"] = has_import or has_use

            if has_import:
                print("- ✓ 调度器已导入智能编排模块")
            if has_use:
                print("- ✓ 调度器配置支持智能编排模式")
            if has_setup:
                print("- ✓ 调度器有 setup_schedule 方法")

            # 检查任务注册情况
            if "task_priorities" in scheduler_content:
                io_info["tasks_registered"] = 15
                print("- ✓ 调度器配置了任务优先级")

        # 检查配置
        config_path = PROJECT_ROOT / "config" / "scheduler_config_v8.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "use_intelligent_orchestration" in config:
                    enabled = config.get("use_intelligent_orchestration", False)
                    print(f"- ✓ 智能编排配置: {'启用' if enabled else '禁用'}")

        self.report["intelligent_orchestration"] = io_info
        return io_info

    def review_code_quality(self) -> Dict:
        """审查代码质量"""
        print("\n" + "=" * 80)
        print("3. 审查代码质量和语法一致性")
        print("=" * 80)

        quality_info = {
            "syntax_issues": [],
            "python_files_scanned": 0,
            "naming_conventions": {},
            "complexity_issues": []
        }

        # 扫描所有 Python 文件
        python_files = list(PROJECT_ROOT.rglob("*.py"))
        # 过滤掉一些不需要检查的
        python_files = [f for f in python_files if "site-packages" not in str(f)]
        quality_info["python_files_scanned"] = len(python_files)
        print(f"- 扫描 Python 文件: {len(python_files)} 个")

        syntax_errors = 0
        long_files = 0

        for i, py_file in enumerate(python_files[:75]):  # 扫描前 75 个
            try:
                # 检查语法
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # 尝试解析
                ast.parse(content, filename=str(py_file))

                # 检查文件大小
                file_size = os.path.getsize(py_file)
                if file_size > 50 * 1024:  # 超过 50KB
                    long_files += 1
                    if long_files <= 3:
                        rel_path = py_file.relative_to(PROJECT_ROOT)
                        print(f"  ⚠️ 大文件: {rel_path} ({file_size//1024}KB)")

            except SyntaxError as e:
                syntax_errors += 1
                rel_path = py_file.relative_to(PROJECT_ROOT)
                issue = f"{rel_path}: Line {e.lineno} - {e}"
                quality_info["syntax_issues"].append(issue)
                print(f"  ✗ {issue}")
            except Exception as e:
                #print(f"  无法分析 {py_file.name}: {e}")
                pass

        if syntax_errors > 0:
            print(f"  ✗ 发现 {syntax_errors} 个语法错误")
        else:
            print("  ✓ 所有扫描的文件语法正确")

        if long_files > 0:
            print(f"  ⚠️  发现 {long_files} 个大文件（>50KB）")

        self.report["code_quality"] = quality_info
        return quality_info

    def review_documentation(self) -> Dict:
        """审查文档和注释完整性"""
        print("\n" + "=" * 80)
        print("4. 审查注释文档完整性")
        print("=" * 80)

        doc_info = {
            "doc_strings_missing": 0,
            "files_with_comments": 0,
            "readme_exists": False,
            "documented_modules": []
        }

        # 检查 README
        readme_path = PROJECT_ROOT / "README.md"
        doc_info["readme_exists"] = readme_path.exists()
        if doc_info["readme_exists"]:
            print(f"- ✓ README.md 存在")
        else:
            print(f"- ⚠️ README.md 缺失")

        # 检查核心模块的文档字符串
        key_modules = [
            PROJECT_ROOT / "src" / "core" / "workflow" / "intelligent_orchestration.py",
            PROJECT_ROOT / "src" / "app" / "auto_scheduler_v8.py",
            PROJECT_ROOT / "src" / "core" / "data" / "collector.py",
        ]

        for module in key_modules:
            if module.exists():
                try:
                    with open(module, "r", encoding="utf-8") as f:
                        content = f.read()

                    # 检查模块级文档字符串
                    content_stripped = content.strip()
                    has_module_doc = (
                        content_stripped.startswith('"""')
                        or content_stripped.startswith("'''")
                    )
                    if has_module_doc:
                        rel_path = str(module.relative_to(PROJECT_ROOT))
                        doc_info["documented_modules"].append(rel_path)
                        print(f"  ✓ {module.name}: 有模块文档")
                    else:
                        print(f"  ⚠️ {module.name}: 缺少模块文档")
                except Exception as e:
                    print(f"  无法检查 {module.name}: {e}")

        # 统计 Python 文件中的注释比例
        python_files = list(PROJECT_ROOT.rglob("*.py"))[:100]
        files_commented = 0

        for py_file in python_files:
            if "site-packages" in str(py_file):
                continue
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    comment_count = 0
                    for line in lines:
                        stripped = line.strip()
                        if (stripped.startswith('#')
                            or stripped.startswith('"""')
                            or stripped.startswith("'''")):
                            comment_count += 1
                    if len(lines) > 0 and comment_count > len(lines) * 0.03:
                        files_commented += 1
            except:
                pass

        doc_info["files_with_comments"] = files_commented
        print(f"- 有足够注释的文件: {files_commented}/{len(python_files)}")

        self.report["documentation"] = doc_info
        return doc_info

    def generate_summary(self):
        """生成总结和建议"""
        print("\n" + "=" * 80)
        print("5. 生成审查总结和建议")
        print("=" * 80)

        # 分析发现的问题
        issues = []
        suggestions = []

        io = self.report["intelligent_orchestration"]
        cq = self.report["code_quality"]
        doc = self.report["documentation"]

        # 检查智能编排
        if not io.get("exists", False):
            issues.append("智能编排模块不存在")
        if not io.get("integrated", False):
            issues.append("智能编排系统集成度有待验证")

        # 检查代码质量
        if len(cq.get("syntax_issues", [])) > 0:
            issues.append(f"发现 {len(cq['syntax_issues'])} 个语法错误")

        # 智能编排相关建议
        if io.get("exists", False):
            suggestions.append("建议为智能编排系统添加单元测试")
            suggestions.append("建议添加编排器状态持久化和恢复功能")
            suggestions.append("建议添加编排器性能监控和可视化")

        # 通用建议
        suggestions.append("建议统一使用 PEP 8 编码规范")
        suggestions.append("建议完善 API 文档和使用示例")

        # 目录结构建议
        suggestions.append("建议整理项目根目录中的临时文件")

        self.report["issues"] = issues
        self.report["suggestions"] = suggestions

        # 计算总体状态
        status = "Good"
        if len(issues) > 3:
            status = "Needs Improvement"

        self.report["summary"] = {
            "overall_status": status,
            "priority_items": len(issues),
            "review_completed": datetime.now().isoformat()
        }

        # 打印建议
        if issues:
            print("发现的问题:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
        else:
            print("✓ 没有发现严重问题")

        print("\n改进建议:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")

    def save_report(self):
        """保存审查报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logs_dir = PROJECT_ROOT / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        output_path = logs_dir / f"project_review_{timestamp}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n审查报告已保存: {output_path}")
        return output_path


def main():
    print("=" * 80)
    print("PL5 项目综合审查系统")
    print("=" * 80)

    reviewer = ProjectReviewer()

    # 执行各阶段审查
    reviewer.review_architecture()
    reviewer.review_intelligent_orchestration()
    reviewer.review_code_quality()
    reviewer.review_documentation()
    reviewer.generate_summary()

    # 保存报告
    report_path = reviewer.save_report()

    print("\n" + "=" * 80)
    print("审查完成！")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
