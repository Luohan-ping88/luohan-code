#!/usr/bin/env python3
"""
单次完整系统审计脚本
"""

import os
import sys
import time
import json
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/workspace/PL5")
sys.path.insert(0, str(PROJECT_ROOT))

def log_audit(message: str, level: str = "INFO"):
    """输出审计日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def audit_imports():
    """审计所有核心模块导入"""
    log_audit("=" * 60)
    log_audit("审计: 核心模块导入检查")
    log_audit("=" * 60)

    modules = [
        'src.core.models.predictor',
        'src.core.models.model_evaluator',
        'src.core.data.collector',
        'src.ai.tools.pl5_tool',
        'src.ai.agents.agent_orchestrator',
        'src.app.intelligent_scheduler_integration',
        'src.core.utils.unified_error_handler'
    ]

    results = {}
    for module in modules:
        try:
            __import__(module)
            log_audit(f"✓ {module}", "INFO")
            results[module] = "OK"
        except Exception as e:
            log_audit(f"✗ {module}: {str(e)}", "ERROR")
            results[module] = f"ERROR: {str(e)}"

    return results

def audit_training_components():
    """审计训练和推理组件"""
    log_audit("=" * 60)
    log_audit("审计: 训练和推理组件")
    log_audit("=" * 60)

    results = {}

    # 1. 测试预测器
    log_audit("检查预测器 (predictor.py)", "INFO")
    try:
        from src.core.models.predictor import PL5Predictor
        predictor = PL5Predictor()
        log_audit("✓ 预测器实例化成功", "INFO")
        results['predictor'] = "OK"
    except Exception as e:
        log_audit(f"✗ 预测器失败: {str(e)}", "ERROR")
        results['predictor'] = f"ERROR: {str(e)}"

    # 2. 测试模型评估器
    log_audit("检查模型评估器 (model_evaluator.py)", "INFO")
    try:
        from src.core.models.model_evaluator import ModelEvaluator
        evaluator = ModelEvaluator()
        log_audit("✓ 模型评估器实例化成功", "INFO")
        results['evaluator'] = "OK"
    except Exception as e:
        log_audit(f"✗ 模型评估器失败: {str(e)}", "ERROR")
        results['evaluator'] = f"ERROR: {str(e)}"

    # 3. 测试数据收集器
    log_audit("检查数据收集器 (collector.py)", "INFO")
    try:
        from src.core.data.collector import DataCollector
        collector = DataCollector()
        log_audit("✓ 数据收集器实例化成功", "INFO")
        results['collector'] = "OK"
    except Exception as e:
        log_audit(f"✗ 数据收集器失败: {str(e)}", "ERROR")
        results['collector'] = f"ERROR: {str(e)}"

    # 4. 检查训练逻辑
    log_audit("检查训练逻辑目录 (src/core/training/)", "INFO")
    training_dir = PROJECT_ROOT / "src" / "core" / "training"
    if training_dir.exists():
        training_files = list(training_dir.glob("*.py"))
        log_audit(f"找到 {len(training_files)} 个训练模块", "INFO")
        results['training_files'] = [f.name for f in training_files]
    else:
        log_audit("训练目录不存在", "WARNING")
        results['training_files'] = []

    return results

def audit_code_quality():
    """审计代码质量"""
    log_audit("=" * 60)
    log_audit("审计: 代码质量检查")
    log_audit("=" * 60)

    results = {}

    # 1. 语法检查
    log_audit("检查Python语法错误", "INFO")
    src_dir = PROJECT_ROOT / "src"
    syntax_errors = []

    for py_file in src_dir.rglob("*.py"):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                compile(f.read(), str(py_file), 'exec')
        except SyntaxError as e:
            syntax_errors.append(f"{py_file}: {e}")
            log_audit(f"✗ 语法错误: {py_file}", "ERROR")

    if not syntax_errors:
        log_audit("✓ 所有Python文件语法检查通过", "INFO")
        results['syntax'] = "OK"
    else:
        results['syntax'] = syntax_errors

    # 2. pytest测试
    log_audit("运行pytest测试套件", "INFO")
    try:
        import subprocess
        result = subprocess.run(
            ['python', '-m', 'pytest', 'tests/', '-v', '--tb=short', '-x'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120
        )

        log_audit(f"pytest返回码: {result.returncode}", "INFO")
        if result.returncode == 0:
            log_audit("✓ pytest测试全部通过", "INFO")
            results['pytest'] = "OK"
        else:
            log_audit("✗ pytest测试有失败项", "WARNING")
            results['pytest'] = f"FAILED (returncode: {result.returncode})"
            results['pytest_output'] = result.stdout[-1000:]

    except subprocess.TimeoutExpired:
        log_audit("✗ pytest执行超时", "ERROR")
        results['pytest'] = "TIMEOUT"
    except Exception as e:
        log_audit(f"✗ pytest执行失败: {str(e)}", "ERROR")
        results['pytest'] = f"ERROR: {str(e)}"

    return results

def audit_intelligent_features():
    """审计智能功能"""
    log_audit("=" * 60)
    log_audit("审计: 智能功能组件")
    log_audit("=" * 60)

    results = {}

    # 1. PL5工具
    log_audit("检查PL5工具 (pl5_tool.py)", "INFO")
    try:
        from src.ai.tools.pl5_tool import PL5Tool
        tool = PL5Tool()
        log_audit("✓ PL5工具实例化成功", "INFO")
        results['pl5_tool'] = "OK"
    except Exception as e:
        log_audit(f"✗ PL5工具失败: {str(e)}", "ERROR")
        results['pl5_tool'] = f"ERROR: {str(e)}"

    # 2. 智能体编排器
    log_audit("检查智能体编排器 (agent_orchestrator.py)", "INFO")
    try:
        from src.ai.agents.agent_orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        log_audit("✓ 智能体编排器实例化成功", "INFO")
        results['orchestrator'] = "OK"
    except Exception as e:
        log_audit(f"✗ 智能体编排器失败: {str(e)}", "ERROR")
        results['orchestrator'] = f"ERROR: {str(e)}"

    # 3. 智能调度器集成
    log_audit("检查智能调度器集成 (intelligent_scheduler_integration.py)", "INFO")
    try:
        from src.app.intelligent_scheduler_integration import IntelligentSchedulerIntegration
        scheduler = IntelligentSchedulerIntegration()
        log_audit("✓ 智能调度器集成实例化成功", "INFO")
        results['scheduler'] = "OK"
    except Exception as e:
        log_audit(f"✗ 智能调度器集成失败: {str(e)}", "ERROR")
        results['scheduler'] = f"ERROR: {str(e)}"

    return results

def audit_bug_fixes():
    """审计BUG修复"""
    log_audit("=" * 60)
    log_audit("审计: BUG修复和错误处理")
    log_audit("=" * 60)

    results = {}

    # 1. 检查日志文件
    log_audit("检查系统日志文件", "INFO")
    log_files = [
        PROJECT_ROOT / "scheduler.log",
        PROJECT_ROOT / "crash.log",
        PROJECT_ROOT / "performance.log"
    ]

    all_errors = []
    for log_file in log_files:
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    errors = [l for l in lines if 'ERROR' in l or 'CRITICAL' in l or 'Exception' in l]
                    if errors:
                        log_audit(f"  {log_file.name}: 发现 {len(errors)} 条错误", "WARNING")
                        all_errors.extend(errors[-10:])
            except Exception as e:
                log_audit(f"  读取{log_file.name}失败: {str(e)}", "ERROR")

    results['log_errors'] = all_errors

    # 2. 运行验证脚本
    log_audit("运行修复验证脚本", "INFO")
    verify_script = PROJECT_ROOT / "scripts" / "utility" / "verify_all_fixes.py"
    if verify_script.exists():
        try:
            import subprocess
            result = subprocess.run(
                ['python', str(verify_script)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                log_audit("✓ 修复验证脚本通过", "INFO")
                results['verification'] = "OK"
            else:
                log_audit("✗ 修复验证脚本失败", "WARNING")
                results['verification'] = "FAILED"
        except Exception as e:
            log_audit(f"✗ 验证脚本执行失败: {str(e)}", "ERROR")
            results['verification'] = f"ERROR: {str(e)}"
    else:
        log_audit("修复验证脚本不存在，跳过", "WARNING")
        results['verification'] = "SKIPPED"

    # 3. 运行系统检查器
    log_audit("运行系统状态检查器", "INFO")
    system_checker = PROJECT_ROOT / "monitor" / "system_checker.py"
    if system_checker.exists():
        try:
            import subprocess
            result = subprocess.run(
                ['python', str(system_checker)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )
            log_audit(f"系统检查器返回码: {result.returncode}", "INFO")
            results['system_checker'] = "OK" if result.returncode == 0 else "FAILED"
        except Exception as e:
            log_audit(f"✗ 系统检查器执行失败: {str(e)}", "ERROR")
            results['system_checker'] = f"ERROR: {str(e)}"
    else:
        log_audit("系统检查器不存在，跳过", "WARNING")
        results['system_checker'] = "SKIPPED"

    # 4. 检查错误处理器
    log_audit("检查统一错误处理器", "INFO")
    try:
        from src.core.utils.unified_error_handler import UnifiedErrorHandler
        handler = UnifiedErrorHandler()
        log_audit("✓ 统一错误处理器实例化成功", "INFO")
        results['error_handler'] = "OK"
    except Exception as e:
        log_audit(f"✗ 错误处理器失败: {str(e)}", "ERROR")
        results['error_handler'] = f"ERROR: {str(e)}"

    return results

def main():
    """主函数"""
    log_audit("=" * 60)
    log_audit("PL5系统全面审计开始")
    log_audit(f"时间: {datetime.now().isoformat()}")
    log_audit("=" * 60)

    start_time = time.time()
    audit_results = {}

    # 执行各项审计
    audit_results['imports'] = audit_imports()
    audit_results['training'] = audit_training_components()
    audit_results['code_quality'] = audit_code_quality()
    audit_results['intelligent_features'] = audit_intelligent_features()
    audit_results['bug_fixes'] = audit_bug_fixes()

    elapsed = time.time() - start_time

    # 保存审计结果
    log_audit("=" * 60)
    log_audit("保存审计结果", "INFO")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = PROJECT_ROOT / "logs" / "daily_audit" / f"audit_{timestamp}.json"

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed,
            'results': audit_results
        }, f, ensure_ascii=False, indent=2)

    log_audit(f"审计结果已保存到: {results_file}", "INFO")

    # 生成汇总
    log_audit("=" * 60)
    log_audit("审计汇总", "INFO")
    log_audit("=" * 60)

    total_checks = 0
    passed_checks = 0

    for category, results in audit_results.items():
        for item, status in results.items():
            total_checks += 1
            if status == "OK":
                passed_checks += 1

    log_audit(f"总计检查项: {total_checks}", "INFO")
    log_audit(f"通过检查项: {passed_checks}", "INFO")
    log_audit(f"失败检查项: {total_checks - passed_checks}", "WARNING")
    log_audit(f"审计耗时: {elapsed:.2f}秒", "INFO")

    log_audit("=" * 60)
    log_audit("PL5系统全面审计完成")
    log_audit("=" * 60)

    return audit_results

if __name__ == "__main__":
    results = main()
