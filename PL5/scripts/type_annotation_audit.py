"""
优化模块类型注解审核检查脚本

更精确地检查类型注解的完整性
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Any, Set, Optional
import re


class TypeAnnotationChecker:
    """类型注解检查器"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.passed: List[Dict[str, Any]] = []

    def check_file(self, file_path: Path) -> bool:
        """检查单个文件的类型注解"""
        if not file_path.exists():
            self.issues.append({
                'file': str(file_path),
                'type': 'missing_file',
                'message': f'文件不存在'
            })
            return False

        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)

            has_issues = False

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    result = self._check_function_def(node, file_path)
                    if not result:
                        has_issues = True

            return not has_issues

        except SyntaxError as e:
            self.issues.append({
                'file': str(file_path),
                'type': 'syntax_error',
                'message': f'语法错误: {e}'
            })
            return False

    def _check_function_def(self, node: ast.FunctionDef, file_path: Path) -> bool:
        """检查函数定义的类型注解"""
        func_name = node.name
        lineno = node.lineno

        has_return_annotation = node.returns is not None

        missing_arg_annotations = []
        for arg in node.args.args:
            if arg.annotation is None and not arg.arg.startswith('_'):
                missing_arg_annotations.append(arg.arg)

        if not has_return_annotation:
            self.issues.append({
                'file': str(file_path.relative_to(self.project_root)),
                'line': lineno,
                'type': 'missing_return_annotation',
                'function': func_name,
                'message': f'函数 {func_name} 缺少返回类型注解'
            })
            return False

        if missing_arg_annotations:
            filtered = [arg for arg in missing_arg_annotations if arg != 'self']
            if filtered:
                self.warnings.append({
                    'file': str(file_path.relative_to(self.project_root)),
                    'line': lineno,
                    'type': 'missing_arg_annotations',
                    'function': func_name,
                    'missing_args': filtered,
                    'message': f'函数 {func_name} 参数缺少类型注解: {filtered}'
                })

        if has_return_annotation:
            self.passed.append({
                'file': str(file_path.relative_to(self.project_root)),
                'function': func_name,
                'message': f'{func_name} ✓'
            })

        return True

    def check_all(self) -> Dict[str, Any]:
        """检查所有文件"""
        files_to_check = [
            'src/core/features/adaptive_selector.py',
            'src/core/features/interaction_extractor.py',
            'src/core/models/context_weight_fusion.py',
            'src/core/models/enhanced_stacking.py',
            'src/core/models/tail_aware_copula.py',
            'src/core/models/optimization_integration.py',
            'src/core/models/optimized_predictor.py',
        ]

        for file_rel in files_to_check:
            file_path = self.project_root / file_rel
            self.check_file(file_path)

        return {
            'issues': self.issues,
            'warnings': self.warnings,
            'passed': self.passed,
            'total_issues': len(self.issues),
            'total_warnings': len(self.warnings),
            'total_passed': len(self.passed),
            'status': 'PASS' if not self.issues else 'FAIL'
        }


def run_type_annotation_audit(project_root: str = '/workspace/PL5') -> Dict[str, Any]:
    """运行类型注解审核"""
    project_path = Path(project_root)

    checker = TypeAnnotationChecker(project_path)
    report = checker.check_all()

    print("\n" + "="*70)
    print("类型注解审核报告")
    print("="*70)

    print(f"\n状态: {report['status']}")
    print(f"通过: {report['total_passed']}")
    print(f"问题: {report['total_issues']}")
    print(f"警告: {report['total_warnings']}")

    if report['issues']:
        print("\n" + "-"*70)
        print("问题列表 (必须修复)")
        print("-"*70)
        for issue in report['issues']:
            print(f"  [{issue['type']}] {issue['file']}:{issue.get('line', '?')}")
            print(f"    → {issue['message']}")

    if report['warnings']:
        print("\n" + "-"*70)
        print("警告列表 (建议修复)")
        print("-"*70)
        for warning in report['warnings'][:10]:
            print(f"  [{warning['type']}] {warning['file']}:{warning.get('line', '?')}")
            print(f"    → {warning['message']}")
        if len(report['warnings']) > 10:
            print(f"  ... 还有 {len(report['warnings']) - 10} 个警告")

    if report['passed']:
        print("\n" + "-"*70)
        print("通过检查")
        print("-"*70)
        for p in report['passed'][:20]:
            print(f"  ✓ {p['file']}::{p['function']}")
        if len(report['passed']) > 20:
            print(f"  ... 还有 {len(report['passed']) - 20} 个通过")

    return report


if __name__ == '__main__':
    report = run_type_annotation_audit()
    sys.exit(0 if report['status'] == 'PASS' else 1)
