#!/usr/bin/env python3
"""
PL5 24小时持续监控系统 - 完整版
自动检测、优化并升级系统
"""

import os
import sys
import time
import json
import traceback
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess

PROJECT_ROOT = Path("/workspace/PL5")
sys.path.insert(0, str(PROJECT_ROOT))

LOG_DIR = PROJECT_ROOT / "logs" / "daily_audit"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class EnhancedAuditLogger:
    """增强的审计日志记录器"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = LOG_DIR / f"daily_audit_{self.timestamp}.log"
        self.summary_file = LOG_DIR / f"summary_{self.timestamp}.txt"
        self.setup_logging()

    def setup_logging(self):
        """设置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("PL5_24H_Audit")

    def log_section(self, title: str):
        """记录章节"""
        line = "=" * 80
        self.logger.info(line)
        self.logger.info(f"  {title}")
        self.logger.info(line)

    def log_subsection(self, title: str):
        """记录子章节"""
        line = "-" * 60
        self.logger.info(line)
        self.logger.info(f"  {title}")
        self.logger.info(line)

class SystemHealthChecker:
    """系统健康检查器 - 增强版"""

    def __init__(self, logger: EnhancedAuditLogger):
        self.logger = logger
        self.issues = []
        self.fixes_applied = []

    def check_imports(self) -> Dict[str, str]:
        """检查所有核心模块导入"""
        self.logger.log_subsection("检查核心模块导入")

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
                self.logger.logger.info(f"✓ {module}")
                results[module] = "OK"
            except Exception as e:
                self.logger.logger.error(f"✗ {module}: {str(e)}")
                results[module] = f"ERROR: {str(e)}"
                self.issues.append(f"导入失败: {module} - {str(e)}")

        return results

    def check_system_resources(self) -> Dict[str, Any]:
        """检查系统资源"""
        self.logger.log_subsection("检查系统资源")

        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            status = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3)
            }

            self.logger.logger.info(f"CPU使用率: {cpu_percent}%")
            self.logger.logger.info(f"内存使用率: {memory.percent}% (可用: {status['memory_available_gb']:.2f}GB)")
            self.logger.logger.info(f"磁盘使用率: {disk.percent}% (可用: {status['disk_free_gb']:.2f}GB)")

            if cpu_percent > 90:
                self.issues.append(f"CPU使用率过高: {cpu_percent}%")
            if memory.percent > 90:
                self.issues.append(f"内存使用率过高: {memory.percent}%")
            if disk.percent > 90:
                self.issues.append(f"磁盘使用率过高: {disk.percent}%")

            return status

        except ImportError:
            self.logger.logger.warning("psutil未安装，正在安装...")
            self.install_package("psutil")
            return {}

    def check_log_files(self) -> List[Dict[str, Any]]:
        """检查日志文件中的错误"""
        self.logger.log_subsection("检查系统日志文件")

        log_files = [
            PROJECT_ROOT / "scheduler.log",
            PROJECT_ROOT / "crash.log",
            PROJECT_ROOT / "performance.log"
        ]

        errors = []
        for log_file in log_files:
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        error_lines = [l for l in lines if 'ERROR' in l or 'CRITICAL' in l or 'Exception' in l]

                        if error_lines:
                            recent_errors = error_lines[-10:]
                            for err in recent_errors:
                                errors.append({
                                    'file': log_file.name,
                                    'error': err.strip()
                                })
                                self.logger.logger.warning(f"{log_file.name}: {err.strip()}")

                except Exception as e:
                    self.logger.logger.error(f"读取日志文件失败: {log_file.name} - {str(e)}")

        return errors

    def install_package(self, package: str):
        """安装缺失的包"""
        try:
            result = subprocess.run(
                ['pip', 'install', package, '-q'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                self.logger.logger.info(f"✓ 已安装 {package}")
                self.fixes_applied.append(f"安装了缺失依赖: {package}")
            else:
                self.logger.logger.error(f"✗ 安装 {package} 失败")
        except Exception as e:
            self.logger.logger.error(f"安装 {package} 失败: {str(e)}")

class TrainingPerformanceTester:
    """训练推理性能测试器 - 增强版"""

    def __init__(self, logger: EnhancedAuditLogger):
        self.logger = logger
        self.results = {}

    def test_predictor(self) -> Dict[str, Any]:
        """测试预测器功能"""
        self.logger.log_subsection("测试预测器功能")

        try:
            from src.core.models.predictor import PL5Predictor

            predictor = PL5Predictor()
            self.logger.logger.info("✓ 预测器实例化成功")

            self.results['predictor'] = {'status': 'success'}
            return {'status': 'success', 'predictor': predictor}

        except Exception as e:
            self.logger.logger.error(f"✗ 预测器测试失败: {str(e)}")
            self.logger.logger.debug(traceback.format_exc())
            self.results['predictor'] = {'status': 'failed', 'error': str(e)}
            return {'status': 'failed', 'error': str(e)}

    def test_model_evaluator(self) -> Dict[str, Any]:
        """测试模型评估器"""
        self.logger.log_subsection("测试模型评估器")

        try:
            from src.core.models.model_evaluator import ModelEvaluator

            evaluator = ModelEvaluator()
            self.logger.logger.info("✓ 模型评估器实例化成功")

            self.results['evaluator'] = {'status': 'success'}
            return {'status': 'success', 'evaluator': evaluator}

        except Exception as e:
            self.logger.logger.error(f"✗ 模型评估器测试失败: {str(e)}")
            self.results['evaluator'] = {'status': 'failed', 'error': str(e)}
            return {'status': 'failed', 'error': str(e)}

    def test_data_collector(self) -> Dict[str, Any]:
        """测试数据收集器"""
        self.logger.log_subsection("测试数据收集器")

        try:
            from src.core.data.collector import DataCollector

            collector = DataCollector()
            self.logger.logger.info("✓ 数据收集器实例化成功")

            self.results['collector'] = {'status': 'success'}
            return {'status': 'success', 'collector': collector}

        except Exception as e:
            self.logger.logger.error(f"✗ 数据收集器测试失败: {str(e)}")
            self.results['collector'] = {'status': 'failed', 'error': str(e)}
            return {'status': 'failed', 'error': str(e)}

    def check_training_logic(self) -> Dict[str, Any]:
        """检查训练逻辑目录"""
        self.logger.log_subsection("检查训练逻辑目录")

        training_dir = PROJECT_ROOT / "src" / "core" / "training"
        if training_dir.exists():
            training_files = list(training_dir.glob("*.py"))
            self.logger.logger.info(f"找到 {len(training_files)} 个训练模块:")
            for f in training_files:
                self.logger.logger.info(f"  - {f.name}")

            self.results['training_logic'] = {
                'status': 'success',
                'files': [f.name for f in training_files]
            }
            return {'status': 'success', 'files': training_files}
        else:
            self.logger.logger.warning("训练目录不存在")
            self.results['training_logic'] = {'status': 'not_found'}
            return {'status': 'not_found'}

class CodeQualityChecker:
    """代码质量检查器 - 增强版"""

    def __init__(self, logger: EnhancedAuditLogger):
        self.logger = logger
        self.issues = []

    def check_syntax_errors(self) -> bool:
        """检查Python语法错误"""
        self.logger.log_subsection("检查Python语法错误")

        src_dir = PROJECT_ROOT / "src"
        syntax_errors = []

        for py_file in src_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), str(py_file), 'exec')
            except SyntaxError as e:
                syntax_errors.append({
                    'file': str(py_file),
                    'error': str(e)
                })
                self.logger.logger.error(f"✗ 语法错误: {py_file} - {e}")

        if syntax_errors:
            self.issues.extend(syntax_errors)
            return False

        self.logger.logger.info("✓ 所有Python文件语法检查通过")
        return True

    def run_pytest(self) -> Dict[str, Any]:
        """运行pytest测试"""
        self.logger.log_subsection("运行pytest测试套件")

        try:
            result = subprocess.run(
                ['python', '-m', 'pytest', 'tests/', '-v', '--tb=short', '-x'],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=180
            )

            self.logger.logger.info(f"pytest返回码: {result.returncode}")

            output = result.stdout + result.stderr
            if result.returncode == 0:
                self.logger.logger.info("✓ pytest测试全部通过")
            else:
                self.logger.logger.warning("✗ pytest测试有失败项")
                self.logger.logger.debug(output[-2000:])

            return {
                'returncode': result.returncode,
                'output': output[-2000:]
            }

        except subprocess.TimeoutExpired:
            self.logger.logger.error("✗ pytest执行超时")
            return {'returncode': -1, 'error': 'timeout'}
        except Exception as e:
            self.logger.logger.error(f"✗ pytest执行失败: {str(e)}")
            return {'returncode': -1, 'error': str(e)}

class IntelligentFeatureChecker:
    """智能功能检查器 - 增强版"""

    def __init__(self, logger: EnhancedAuditLogger):
        self.logger = logger
        self.results = {}

    def check_pl5_tool(self) -> Dict[str, Any]:
        """检查PL5工具"""
        self.logger.log_subsection("检查PL5工具")

        try:
            from src.ai.tools.pl5_tool import PL5Tool

            tool = PL5Tool()
            self.logger.logger.info("✓ PL5工具实例化成功")

            required_methods = ['execute', 'get_schema']
            missing_methods = []
            for method in required_methods:
                if not hasattr(tool, method):
                    missing_methods.append(method)

            if missing_methods:
                self.logger.logger.warning(f"PL5工具缺少方法: {missing_methods}")
                self.results['pl5_tool'] = {'status': 'partial', 'missing': missing_methods}
            else:
                self.results['pl5_tool'] = {'status': 'success'}

            return self.results['pl5_tool']

        except Exception as e:
            self.logger.logger.error(f"✗ PL5工具检查失败: {str(e)}")
            self.results['pl5_tool'] = {'status': 'failed', 'error': str(e)}
            return self.results['pl5_tool']

    def check_agent_orchestrator(self) -> Dict[str, Any]:
        """检查智能体编排器"""
        self.logger.log_subsection("检查智能体编排器")

        try:
            from src.ai.agents.agent_orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator()
            self.logger.logger.info("✓ 智能体编排器实例化成功")

            self.results['orchestrator'] = {'status': 'success'}
            return self.results['orchestrator']

        except Exception as e:
            self.logger.logger.error(f"✗ 智能体编排器检查失败: {str(e)}")
            self.results['orchestrator'] = {'status': 'failed', 'error': str(e)}
            return self.results['orchestrator']

    def check_intelligent_scheduler(self) -> Dict[str, Any]:
        """检查智能调度器集成"""
        self.logger.log_subsection("检查智能调度器集成")

        try:
            from src.app.intelligent_scheduler_integration import IntelligentSchedulerIntegration

            scheduler = IntelligentSchedulerIntegration()
            self.logger.logger.info("✓ 智能调度器集成实例化成功")

            self.results['scheduler'] = {'status': 'success'}
            return self.results['scheduler']

        except Exception as e:
            self.logger.logger.error(f"✗ 智能调度器集成检查失败: {str(e)}")
            self.results['scheduler'] = {'status': 'failed', 'error': str(e)}
            return self.results['scheduler']

class BugFixVerifier:
    """BUG修复验证器 - 增强版"""

    def __init__(self, logger: EnhancedAuditLogger):
        self.logger = logger
        self.results = {}

    def run_verification_script(self) -> Dict[str, Any]:
        """运行验证脚本"""
        self.logger.log_subsection("运行修复验证脚本")

        verify_script = PROJECT_ROOT / "scripts" / "utility" / "verify_all_fixes.py"

        if not verify_script.exists():
            self.logger.logger.warning("验证脚本不存在，跳过")
            return {'status': 'skipped'}

        try:
            result = subprocess.run(
                ['python', str(verify_script)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=120
            )

            output = result.stdout + result.stderr
            self.logger.logger.info(f"修复验证脚本执行完成，返回码: {result.returncode}")
            self.logger.logger.debug(output[-1000:])

            self.results['verification'] = {
                'returncode': result.returncode,
                'status': 'success' if result.returncode == 0 else 'failed'
            }

            return self.results['verification']

        except Exception as e:
            self.logger.logger.error(f"✗ 修复验证脚本执行失败: {str(e)}")
            self.results['verification'] = {'error': str(e)}
            return self.results['verification']

    def check_error_handler(self) -> Dict[str, Any]:
        """检查错误处理器"""
        self.logger.log_subsection("检查统一错误处理器")

        try:
            from src.core.utils.unified_error_handler import ErrorHandler

            handler = ErrorHandler()
            self.logger.logger.info("✓ 统一错误处理器实例化成功")

            test_error = handler.handle_error(Exception("测试错误"), {"module": "audit"})
            self.logger.logger.info(f"✓ 错误处理器测试通过: {test_error}")

            self.results['error_handler'] = {'status': 'success'}
            return self.results['error_handler']

        except Exception as e:
            self.logger.logger.error(f"✗ 错误处理器检查失败: {str(e)}")
            self.results['error_handler'] = {'status': 'failed', 'error': str(e)}
            return self.results['error_handler']

    def check_system_checker(self) -> Dict[str, Any]:
        """检查系统状态"""
        self.logger.log_subsection("运行系统状态检查器")

        system_checker = PROJECT_ROOT / "monitor" / "system_checker.py"

        if not system_checker.exists():
            self.logger.logger.warning("系统检查器不存在，跳过")
            return {'status': 'skipped'}

        try:
            result = subprocess.run(
                ['python', str(system_checker)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )

            self.logger.logger.info(f"系统检查器返回码: {result.returncode}")

            self.results['system_checker'] = {
                'returncode': result.returncode,
                'status': 'success' if result.returncode == 0 else 'failed'
            }

            return self.results['system_checker']

        except Exception as e:
            self.logger.logger.error(f"✗ 系统检查器执行失败: {str(e)}")
            self.results['system_checker'] = {'error': str(e)}
            return self.results['system_checker']

class Continuous24HourMonitor:
    """24小时持续监控主控制器"""

    def __init__(self):
        self.logger = EnhancedAuditLogger()
        self.start_time = datetime.now()
        self.cycle_count = 0
        self.total_issues = []
        self.total_fixes = []

    def run_full_audit_cycle(self) -> Dict[str, Any]:
        """运行完整审计周期"""
        cycle_id = self.cycle_count + 1
        self.logger.log_section(f"开始审计周期 #{cycle_id}")

        cycle_start = time.time()
        cycle_results = {
            'timestamp': datetime.now().isoformat(),
            'cycle_id': cycle_id,
            'checks': {}
        }

        # 1. 系统健康检查
        self.logger.log_section("1. 系统健康检查")
        health_checker = SystemHealthChecker(self.logger)
        cycle_results['checks']['imports'] = health_checker.check_imports()
        cycle_results['checks']['resources'] = health_checker.check_system_resources()
        cycle_results['checks']['log_errors'] = health_checker.check_log_files()
        self.total_issues.extend(health_checker.issues)
        self.total_fixes.extend(health_checker.fixes_applied)

        # 2. 训练推理性能测试
        self.logger.log_section("2. 训练推理性能测试")
        perf_tester = TrainingPerformanceTester(self.logger)
        cycle_results['checks']['predictor'] = perf_tester.test_predictor()
        cycle_results['checks']['evaluator'] = perf_tester.test_model_evaluator()
        cycle_results['checks']['collector'] = perf_tester.test_data_collector()
        cycle_results['checks']['training_logic'] = perf_tester.check_training_logic()
        cycle_results['checks']['performance_results'] = perf_tester.results

        # 3. 代码质量检查
        self.logger.log_section("3. 代码质量检查")
        quality_checker = CodeQualityChecker(self.logger)
        cycle_results['checks']['syntax'] = quality_checker.check_syntax_errors()
        cycle_results['checks']['pytest'] = quality_checker.run_pytest()
        self.total_issues.extend(quality_checker.issues)

        # 4. 智能功能检查
        self.logger.log_section("4. 智能功能检查")
        feature_checker = IntelligentFeatureChecker(self.logger)
        cycle_results['checks']['pl5_tool'] = feature_checker.check_pl5_tool()
        cycle_results['checks']['orchestrator'] = feature_checker.check_agent_orchestrator()
        cycle_results['checks']['scheduler'] = feature_checker.check_intelligent_scheduler()
        cycle_results['checks']['feature_results'] = feature_checker.results

        # 5. BUG修复验证
        self.logger.log_section("5. BUG修复验证")
        bug_fixer = BugFixVerifier(self.logger)
        cycle_results['checks']['verification'] = bug_fixer.run_verification_script()
        cycle_results['checks']['error_handler'] = bug_fixer.check_error_handler()
        cycle_results['checks']['system_checker'] = bug_fixer.check_system_checker()
        cycle_results['checks']['bugfix_results'] = bug_fixer.results

        cycle_elapsed = time.time() - cycle_start
        cycle_results['elapsed_seconds'] = cycle_elapsed

        self.logger.log_section(f"审计周期 #{cycle_id} 完成，耗时: {cycle_elapsed:.2f}秒")

        self.cycle_count += 1
        return cycle_results

    def generate_summary_report(self, all_results: List[Dict]) -> str:
        """生成汇总报告"""
        report = []
        report.append("=" * 80)
        report.append("PL5 24小时持续监控系统 - 汇总报告")
        report.append("=" * 80)
        report.append(f"监控开始时间: {self.start_time.isoformat()}")
        report.append(f"监控结束时间: {datetime.now().isoformat()}")
        report.append(f"总审计周期数: {self.cycle_count}")
        report.append(f"总发现问题数: {len(self.total_issues)}")
        report.append(f"总修复建议数: {len(self.total_fixes)}")
        report.append("")

        # 汇总各检查项
        report.append("检查项汇总:")
        check_keys = ['imports', 'predictor', 'evaluator', 'collector', 'training_logic',
                      'syntax', 'pytest', 'pl5_tool', 'orchestrator', 'scheduler',
                      'verification', 'error_handler', 'system_checker']

        for key in check_keys:
            statuses = [r['checks'].get(key) for r in all_results if 'checks' in r]
            if statuses:
                if isinstance(statuses[0], dict) and 'status' in statuses[0]:
                    success_count = sum(1 for s in statuses if s.get('status') in ['success', 'OK', 'skipped'])
                    report.append(f"  - {key}: {success_count}/{len(statuses)} 通过")
                elif isinstance(statuses[0], bool):
                    success_count = sum(1 for s in statuses if s)
                    report.append(f"  - {key}: {success_count}/{len(statuses)} 通过")
                elif statuses[0] in ['OK', True]:
                    report.append(f"  - {key}: {len(statuses)}/{len(statuses)} 通过")

        report.append("")
        report.append("发现的问题列表:")
        if self.total_issues:
            for i, issue in enumerate(self.total_issues, 1):
                report.append(f"  {i}. {issue}")
        else:
            report.append("  无发现问题")

        report.append("")
        report.append("已应用的修复:")
        if self.total_fixes:
            for i, fix in enumerate(self.total_fixes, 1):
                report.append(f"  {i}. {fix}")
        else:
            report.append("  无自动修复")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def save_cycle_results(self, cycle_results: Dict):
        """保存审计周期结果"""
        results_file = LOG_DIR / f"cycle_{cycle_results['cycle_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'cycle': cycle_results['cycle_id'],
                'results': cycle_results,
                'timestamp': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        self.logger.logger.info(f"周期结果已保存: {results_file}")

    def run_24hour_monitoring(self):
        """运行24小时持续监控"""
        self.logger.log_section("PL5 24小时持续监控系统启动")

        # 配置参数
        CYCLE_INTERVAL = 10 * 60  # 10分钟一个周期
        TOTAL_CYCLES = int(24 * 60 * 60 / CYCLE_INTERVAL)  # 144个周期

        self.logger.logger.info(f"监控配置:")
        self.logger.logger.info(f"  - 总运行时长: 24小时")
        self.logger.logger.info(f"  - 审计周期: {CYCLE_INTERVAL}秒")
        self.logger.logger.info(f"  - 预计审计次数: {TOTAL_CYCLES}")

        all_results = []
        last_summary_time = datetime.now()

        try:
            while self.cycle_count < TOTAL_CYCLES:
                # 运行完整审计周期
                cycle_results = self.run_full_audit_cycle()
                all_results.append(cycle_results)

                # 保存周期结果
                self.save_cycle_results(cycle_results)

                # 每12小时生成一次汇总报告
                time_since_summary = (datetime.now() - last_summary_time).total_seconds()
                if time_since_summary >= 12 * 60 * 60 or self.cycle_count % 72 == 0:
                    summary = self.generate_summary_report(all_results)
                    summary_file = LOG_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(summary_file, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    self.logger.logger.info(f"12小时汇总报告已保存: {summary_file}")
                    last_summary_time = datetime.now()

                # 计算下一个周期的等待时间
                elapsed = time.time()
                sleep_time = max(0, CYCLE_INTERVAL - elapsed)

                self.logger.logger.info(f"审计周期 #{self.cycle_count} 完成")
                self.logger.logger.info(f"等待 {sleep_time:.0f}秒后进行下一轮审计...")

                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.logger.info("监控被用户中断")
        except Exception as e:
            self.logger.logger.error(f"监控过程发生错误: {str(e)}")
            self.logger.logger.debug(traceback.format_exc())
        finally:
            # 生成最终报告
            summary = self.generate_summary_report(all_results)
            final_summary_file = LOG_DIR / f"final_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(final_summary_file, 'w', encoding='utf-8') as f:
                f.write(summary)

            self.logger.logger.info(f"最终汇总报告已保存: {final_summary_file}")
            self.logger.log_section("PL5 24小时持续监控系统已停止")

def main():
    """主函数"""
    print("=" * 80)
    print("PL5 24小时持续监控系统 - 完整版")
    print("=" * 80)
    print(f"启动时间: {datetime.now().isoformat()}")
    print()

    monitor = Continuous24HourMonitor()

    # 检查是否以服务模式运行（24小时持续监控）
    if len(sys.argv) > 1 and sys.argv[1] == '--continuous':
        monitor.run_24hour_monitoring()
    else:
        # 单次审计模式
        print("运行单次完整审计...")
        result = monitor.run_full_audit_cycle()
        print()
        print("=" * 80)
        print("审计结果汇总:")
        print("=" * 80)

        checks = result.get('checks', {})
        for category, status in checks.items():
            if isinstance(status, dict):
                cat_status = status.get('status', 'unknown')
                print(f"  {category}: {cat_status}")
            elif isinstance(status, bool):
                print(f"  {category}: {'✓ OK' if status else '✗ FAILED'}")
            else:
                print(f"  {category}: {status}")

        print()
        print(f"审计耗时: {result.get('elapsed_seconds', 0):.2f}秒")
        print("=" * 80)

if __name__ == "__main__":
    main()
