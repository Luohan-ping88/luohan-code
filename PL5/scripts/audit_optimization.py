"""
优化模块集成审核检查清单

审核内容:
1. 代码质量检查
2. 接口一致性检查
3. 依赖关系检查
4. 性能影响评估
5. 兼容性检查
"""

import ast
import inspect
from pathlib import Path
from typing import List, Dict, Any, Set
import logging

logger = logging.getLogger(__name__)


class CodeAuditChecker:
    """代码审核检查器"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    def check_all(self) -> Dict[str, Any]:
        """执行所有检查"""
        logger.info("开始代码审核...")

        self.check_import_consistency()
        self.check_interface_compatibility()
        self.check_type_annotations()
        self.check_error_handling()
        self.check_documentation()

        return {
            'issues': self.issues,
            'warnings': self.warnings,
            'total_issues': len(self.issues),
            'total_warnings': len(self.warnings),
            'status': 'PASS' if not self.issues else 'FAIL'
        }

    def check_import_consistency(self):
        """检查导入一致性"""
        logger.info("检查导入一致性...")

        required_imports = {
            'AdaptiveFeatureSelector': 'src.core.features.adaptive_selector',
            'FeatureInteractionExtractor': 'src.core.features.interaction_extractor',
            'ContextAwareWeightFusion': 'src.core.models.context_weight_fusion',
            'EnhancedStackingEnsemble': 'src.core.models.enhanced_stacking',
            'TailAwareCopula': 'src.core.models.tail_aware_copula',
        }

        integration_file = self.project_root / 'src/core/models/optimization_integration.py'
        if not integration_file.exists():
            self.issues.append({
                'type': 'missing_file',
                'file': str(integration_file),
                'message': '集成文件不存在'
            })
            return

        content = integration_file.read_text()

        for cls_name, module_path in required_imports.items():
            if cls_name not in content:
                self.warnings.append({
                    'type': 'import_check',
                    'class': cls_name,
                    'message': f'{cls_name} 导入未检查'
                })

    def check_interface_compatibility(self):
        """检查接口兼容性"""
        logger.info("检查接口兼容性...")

        integration_file = self.project_root / 'src/core/models/optimization_integration.py'
        if not integration_file.exists():
            return

        try:
            tree = ast.parse(integration_file.read_text())

            required_methods = [
                'optimize_features',
                'fit_optimized_copula',
                'predict_with_optimization',
                'update_optimization_with_feedback',
                'get_optimization_summary'
            ]

            class_methods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if node.name in ['OptimizationIntegrationMixin', 'OptimizedEnhancedPredictorAdapter']:
                        class_methods.update([n.name for n in node.body if isinstance(n, ast.FunctionDef)])

            for method in required_methods:
                if method not in class_methods:
                    self.issues.append({
                        'type': 'interface',
                        'method': method,
                        'message': f'缺少必需方法: {method}'
                    })

        except SyntaxError as e:
            self.issues.append({
                'type': 'syntax_error',
                'file': str(integration_file),
                'message': f'语法错误: {e}'
            })

    def check_type_annotations(self):
        """检查类型注解"""
        logger.info("检查类型注解...")

        files_to_check = [
            'src/core/features/adaptive_selector.py',
            'src/core/features/interaction_extractor.py',
            'src/core/models/context_weight_fusion.py',
            'src/core/models/enhanced_stacking.py',
            'src/core/models/tail_aware_copula.py',
            'src/core/models/optimization_integration.py',
        ]

        for file_path in files_to_check:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue

            try:
                content = full_path.read_text()
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    if 'def ' in line and ':' not in line.split('def ')[1].split('(')[0]:
                        if 'async def' not in line:
                            self.warnings.append({
                                'type': 'type_hint',
                                'file': file_path,
                                'line': i,
                                'message': '函数缺少返回类型注解'
                            })
            except Exception as e:
                self.warnings.append({
                    'type': 'check_error',
                    'file': file_path,
                    'message': f'检查失败: {e}'
                })

    def check_error_handling(self):
        """检查错误处理"""
        logger.info("检查错误处理...")

        files_to_check = [
            'src/core/models/optimization_integration.py',
        ]

        for file_path in files_to_check:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue

            content = full_path.read_text()

            try_blocks = content.count('try:')
            except_blocks = content.count('except')

            if try_blocks > 0 and except_blocks < try_blocks:
                self.warnings.append({
                    'type': 'error_handling',
                    'file': file_path,
                    'message': f'try块({try_blocks}) 与 except块({except_blocks}) 数量不匹配'
                })

    def check_documentation(self):
        """检查文档"""
        logger.info("检查文档...")

        required_docs = [
            'src/core/features/adaptive_selector.py',
            'src/core/features/interaction_extractor.py',
            'src/core/models/context_weight_fusion.py',
            'src/core/models/enhanced_stacking.py',
            'src/core/models/tail_aware_copula.py',
        ]

        for file_path in required_docs:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue

            content = full_path.read_text()

            has_docstring = '"""' in content or "'''" in content
            has_class_doc = content.count('"""') >= 2 or content.count("'''") >= 2

            if not has_class_doc:
                self.warnings.append({
                    'type': 'documentation',
                    'file': file_path,
                    'message': '缺少类文档字符串'
                })


def run_audit(project_root: str = '/workspace/PL5') -> Dict[str, Any]:
    """
    运行代码审核

    Args:
        project_root: 项目根目录

    Returns:
        审核报告
    """
    project_path = Path(project_root)

    checker = CodeAuditChecker(project_path)
    report = checker.check_all()

    print("\n" + "="*60)
    print("代码审核报告")
    print("="*60)

    print(f"\n状态: {report['status']}")
    print(f"问题数: {report['total_issues']}")
    print(f"警告数: {report['total_warnings']}")

    if report['issues']:
        print("\n--- 问题 ---")
        for issue in report['issues']:
            print(f"[{issue['type']}] {issue.get('message', 'N/A')}")

    if report['warnings']:
        print("\n--- 警告 ---")
        for warning in report['warnings']:
            print(f"[{warning['type']}] {warning.get('message', 'N/A')}")

    return report


if __name__ == '__main__':
    run_audit()
