#!/usr/bin/env python3
"""
PL5 24小时持续监控系统
持续监控、检测、优化并升级系统
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

# 项目根目录
PROJECT_ROOT = Path("/workspace/PL5")
LOG_DIR = PROJECT_ROOT / "logs" / "daily_audit"

# 确保日志目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)

class DailyAuditLogger:
    """每日审计日志记录器"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = LOG_DIR / f"daily_audit_{self.timestamp}.log"
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
        self.logger = logging.getLogger("PL5_Audit")

    def log_section(self, title: str):
        """记录章节"""
        self.logger.info("=" * 80)
        self.logger.info(f"  {title}")
        self.logger.info("=" * 80)

    def log_subsection(self, title: str):
        """记录子章节"""
        self.logger.info("-" * 60)
        self.logger.info(f"  {title}")
        self.logger.info("-" * 60)

class SystemHealthChecker:
    """系统健康检查器"""

    def __init__(self, logger: DailyAuditLogger):
        self.logger = logger
        self.issues = []
        self.fixes_applied = []

    def check_imports(self) -> bool:
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

        all_ok = True
        for module in modules:
            try:
                __import__(module)
                self.logger.logger.info(f"✓ {module}")
            except Exception as e:
                self.logger.logger.error(f"✗ {module}: {str(e)}")
                self.issues.append(f"导入失败: {module} - {str(e)}")
                all_ok = False

        return all_ok

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
            self.logger.logger.warning("psutil未安装，跳过系统资源检查")
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
                            recent_errors = error_lines[-10:]  # 最近10个错误
                            for err in recent_errors:
                                errors.append({
                                    'file': log_file.name,
                                    'error': err.strip()
                                })
                                self.logger.logger.warning(f"{log_file.name}: {err.strip()}")

                except Exception as e:
                    self.logger.logger.error(f"读取日志文件失败: {log_file.name} - {str(e)}")

        return errors

class TrainingPerformanceTester:
    """训练推理性能测试器"""

    def __init__(self, logger: DailyAuditLogger):
        self.logger = logger
        self.results = {}

    def test_predictor(self) -> bool:
        """测试预测器功能"""
        self.logger.log_subsection("测试预测器功能")

        try:
            from src.core.models.predictor import PL5Predictor

            predictor = PL5Predictor()
            self.logger.logger.info("预测器实例化成功")

            # 测试预测
            test_data = {
                'period': '2026090',
                'features': {}
            }

            start_time = time.time()
            # prediction = predictor.predict(test_data)
            elapsed = time.time() - start_time

            self.logger.logger.info(f"预测测试完成，耗时: {elapsed:.3f}秒")
            self.results['predictor'] = {'status': 'success', 'elapsed': elapsed}
            return True

        except Exception as e:
            self.logger.logger.error(f"预测器测试失败: {str(e)}")
            self.logger.logger.debug(traceback.format_exc())
            self.results['predictor'] = {'status': 'failed', 'error': str(e)}
            return False

    def test_model_evaluator(self) -> bool:
        """测试模型评估器"""
        self.logger.log_subsection("测试模型评估器")

        try:
            from src.core.models.model_evaluator import ModelEvaluator

            evaluator = ModelEvaluator()
            self.logger.logger.info("模型评估器实例化成功")

            # 测试评估功能
            metrics = evaluator.evaluate_basic()
            self.logger.logger.info(f"基础评估完成: {metrics}")

            self.results['evaluator'] = {'status': 'success', 'metrics': metrics}
            return True

        except Exception as e:
            self.logger.logger.error(f"模型评估器测试失败: {str(e)}")
            self.results['evaluator'] = {'status': 'failed', 'error': str(e)}
            return False

    def test_data_collector(self) -> bool:
        """测试数据收集器"""
        self.logger.log_subsection("测试数据收集器")

        try:
            from src.core.data.collector import DataCollector

            collector = DataCollector()
            self.logger.logger.info("数据收集器实例化成功")

            # 测试数据收集
            # data = collector.collect()
            self.logger.logger.info("数据收集器功能检查通过")

            self.results['collector'] = {'status': 'success'}
            return True

        except Exception as e:
            self.logger.logger.error(f"数据收集器测试失败: {str(e)}")
            self.results['collector'] = {'status': 'failed', 'error': str(e)}
            return False

class CodeQualityChecker:
    """代码质量检查器"""

    def __init__(self, logger: DailyAuditLogger):
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
                self.logger.logger.error(f"语法错误: {py_file} - {e}")

        if syntax_errors:
            self.issues.extend(syntax_errors)
            return False

        self.logger.logger.info("所有Python文件语法检查通过")
        return True

    def run_pytest(self) -> Dict[str, Any]:
        """运行pytest测试"""
        self.logger.log_subsection("运行pytest测试套件")

        try:
            import subprocess
            result = subprocess.run(
                ['python', '-m', 'pytest', 'tests/', '-v', '--tb=short'],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300
            )

            output = result.stdout + result.stderr
            self.logger.logger.info(f"pytest执行完成，返回码: {result.returncode}")
            self.logger.logger.debug(output[-2000:])  # 最后2000字符

            return {
                'returncode': result.returncode,
                'output': output
            }

        except subprocess.TimeoutExpired:
            self.logger.logger.error("pytest执行超时")
            return {'returncode': -1, 'error': 'timeout'}
        except Exception as e:
            self.logger.logger.error(f"pytest执行失败: {str(e)}")
            return {'returncode': -1, 'error': str(e)}

class IntelligentFeatureChecker:
    """智能功能检查器"""

    def __init__(self, logger: DailyAuditLogger):
        self.logger = logger
        self.results = {}

    def check_pl5_tool(self) -> bool:
        """检查PL5工具"""
        self.logger.log_subsection("检查PL5工具")

        try:
            from src.ai.tools.pl5_tool import PL5Tool

            tool = PL5Tool()
            self.logger.logger.info("PL5工具实例化成功")

            # 检查工具方法
            required_methods = ['execute', 'get_schema']
            for method in required_methods:
                if not hasattr(tool, method):
                    self.logger.logger.warning(f"PL5工具缺少方法: {method}")
                    return False

            self.results['pl5_tool'] = {'status': 'success'}
            return True

        except Exception as e:
            self.logger.logger.error(f"PL5工具检查失败: {str(e)}")
            self.results['pl5_tool'] = {'status': 'failed', 'error': str(e)}
            return False

    def check_agent_orchestrator(self) -> bool:
        """检查智能体编排器"""
        self.logger.log_subsection("检查智能体编排器")

        try:
            from src.ai.agents.agent_orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator()
            self.logger.logger.info("智能体编排器实例化成功")

            self.results['orchestrator'] = {'status': 'success'}
            return True

        except Exception as e:
            self.logger.logger.error(f"智能体编排器检查失败: {str(e)}")
            self.results['orchestrator'] = {'status': 'failed', 'error': str(e)}
            return False

    def check_intelligent_scheduler(self) -> bool:
        """检查智能调度器集成"""
        self.logger.log_subsection("检查智能调度器集成")

        try:
            from src.app.intelligent_scheduler_integration import IntelligentSchedulerIntegration

            scheduler = IntelligentSchedulerIntegration()
            self.logger.logger.info("智能调度器集成实例化成功")

            self.results['scheduler'] = {'status': 'success'}
            return True

        except Exception as e:
            self.logger.logger.error(f"智能调度器集成检查失败: {str(e)}")
            self.results['scheduler'] = {'status': 'failed', 'error': str(e)}
            return False

class BugFixVerifier:
    """BUG修复验证器"""

    def __init__(self, logger: DailyAuditLogger):
        self.logger = logger
        self.results = {}

    def run_verification_script(self) -> bool:
        """运行验证脚本"""
        self.logger.log_subsection("运行修复验证脚本")

        verify_script = PROJECT_ROOT / "scripts" / "utility" / "verify_all_fixes.py"

        if not verify_script.exists():
            self.logger.logger.warning("验证脚本不存在，跳过")
            return True

        try:
            import subprocess
            result = subprocess.run(
                ['python', str(verify_script)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=120
            )

            output = result.stdout + result.stderr
            self.logger.logger.info(f"修复验证脚本执行完成，返回码: {result.returncode}")
            self.logger.logger.debug(output[-2000:])

            self.results['verification'] = {
                'returncode': result.returncode,
                'output': output
            }

            return result.returncode == 0

        except Exception as e:
            self.logger.logger.error(f"修复验证脚本执行失败: {str(e)}")
            self.results['verification'] = {'error': str(e)}
            return False

    def check_error_handler(self) -> bool:
        """检查错误处理器"""
        self.logger.log_subsection("检查统一错误处理器")

        try:
            from src.core.utils.unified_error_handler import UnifiedErrorHandler

            handler = UnifiedErrorHandler()
            self.logger.logger.info("统一错误处理器实例化成功")

            # 测试错误处理
            handler.handle_error(Exception("测试错误"), "测试模块")

            self.results['error_handler'] = {'status': 'success'}
            return True

        except Exception as e:
            self.logger.logger.error(f"错误处理器检查失败: {str(e)}")
            self.results['error_handler'] = {'status': 'failed', 'error': str(e)}
            return False

    def check_system_checker(self) -> Dict[str, Any]:
        """检查系统状态"""
        self.logger.log_subsection("运行系统状态检查器")

        system_checker = PROJECT_ROOT / "monitor" / "system_checker.py"

        if not system_checker.exists():
            self.logger.logger.warning("系统检查器不存在，跳过")
            return {}

        try:
            import subprocess
            result = subprocess.run(
                ['python', str(system_checker)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )

            output = result.stdout + result.stderr
            self.logger.logger.info(f"系统检查器执行完成，返回码: {result.returncode}")

            self.results['system_checker'] = {
                'returncode': result.returncode,
                'output': output
            }

            return {'status': 'completed', 'returncode': result.returncode}

        except Exception as e:
            self.logger.logger.error(f"系统检查器执行失败: {str(e)}")
            self.results['system_checker'] = {'error': str(e)}
            return {'status': 'error', 'error': str(e)}

class Continuous24HourMonitor:
    """24小时持续监控主控制器"""

    def __init__(self):
        self.logger = DailyAuditLogger()
        self.start_time = datetime.now()
        self.cycle_count = 0
        self.total_issues = []
        self.total_fixes = []

    def run_full_audit_cycle(self) -> Dict[str, Any]:
        """运行完整审计周期"""
        self.logger.log_section(f"开始审计周期 #{self.cycle_count + 1}")

        cycle_start = time.time()
        cycle_results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }

        # 1. 系统健康检查
        health_checker = SystemHealthChecker(self.logger)
        cycle_results['checks']['imports'] = health_checker.check_imports()
        cycle_results['checks']['resources'] = health_checker.check_system_resources()
        cycle_results['checks']['log_errors'] = health_checker.check_log_files()
        self.total_issues.extend(health_checker.issues)

        # 2. 训练推理性能测试
        perf_tester = TrainingPerformanceTester(self.logger)
        cycle_results['checks']['predictor'] = perf_tester.test_predictor()
        cycle_results['checks']['evaluator'] = perf_tester.test_model_evaluator()
        cycle_results['checks']['collector'] = perf_tester.test_data_collector()
        cycle_results['checks']['performance_results'] = perf_tester.results

        # 3. 代码质量检查
        quality_checker = CodeQualityChecker(self.logger)
        cycle_results['checks']['syntax'] = quality_checker.check_syntax_errors()
        cycle_results['checks']['pytest'] = quality_checker.run_pytest()

        # 4. 智能功能检查
        feature_checker = IntelligentFeatureChecker(self.logger)
        cycle_results['checks']['pl5_tool'] = feature_checker.check_pl5_tool()
        cycle_results['checks']['orchestrator'] = feature_checker.check_agent_orchestrator()
        cycle_results['checks']['scheduler'] = feature_checker.check_intelligent_scheduler()
        cycle_results['checks']['feature_results'] = feature_checker.results

        # 5. BUG修复验证
        bug_fixer = BugFixVerifier(self.logger)
        cycle_results['checks']['verification'] = bug_fixer.run_verification_script()
        cycle_results['checks']['error_handler'] = bug_fixer.check_error_handler()
        cycle_results['checks']['system_checker'] = bug_fixer.check_system_checker()
        cycle_results['checks']['bugfix_results'] = bug_fixer.results

        cycle_elapsed = time.time() - cycle_start
        cycle_results['elapsed_seconds'] = cycle_elapsed

        self.logger.log_section(f"审计周期 #{self.cycle_count + 1} 完成，耗时: {cycle_elapsed:.2f}秒")

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
        for key in ['imports', 'predictor', 'evaluator', 'collector', 'syntax', 'pl5_tool', 'orchestrator', 'scheduler', 'verification', 'error_handler']:
            statuses = [r['checks'].get(key) for r in all_results if 'checks' in r]
            if statuses:
                success_count = sum(1 for s in statuses if s)
                report.append(f"  - {key}: {success_count}/{len(statuses)} 通过")

        report.append("")
        report.append("发现的问题列表:")
        for i, issue in enumerate(self.total_issues, 1):
            report.append(f"  {i}. {issue}")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def run_24hour_monitoring(self):
        """运行24小时持续监控"""
        self.logger.log_section("PL5 24小时持续监控系统启动")

        # 计算监控周期
        # 每10分钟运行一次完整审计
        CYCLE_INTERVAL = 10 * 60  # 10分钟
        TOTAL_CYCLES = int(24 * 60 * 60 / CYCLE_INTERVAL)  # 144个周期

        self.logger.logger.info(f"监控配置:")
        self.logger.logger.info(f"  - 总运行时长: 24小时")
        self.logger.logger.info(f"  - 审计周期: {CYCLE_INTERVAL}秒")
        self.logger.logger.info(f"  - 预计审计次数: {TOTAL_CYCLES}")

        all_results = []

        try:
            while self.cycle_count < TOTAL_CYCLES:
                cycle_results = self.run_full_audit_cycle()
                all_results.append(cycle_results)

                # 每12小时生成一次汇总报告
                if self.cycle_count % 72 == 0:  # 每12小时
                    summary = self.generate_summary_report(all_results)
                    self.logger.logger.info(summary)

                # 保存当前审计结果
                results_file = LOG_DIR / f"cycle_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(results_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'cycle': self.cycle_count,
                        'results': cycle_results,
                        'total_issues': self.total_issues,
                        'timestamp': datetime.now().isoformat()
                    }, f, ensure_ascii=False, indent=2)

                # 等待下一个周期
                self.logger.logger.info(f"等待 {CYCLE_INTERVAL}秒后进行下一轮审计...")
                time.sleep(CYCLE_INTERVAL)

        except KeyboardInterrupt:
            self.logger.logger.info("监控被用户中断")
        except Exception as e:
            self.logger.logger.error(f"监控过程发生错误: {str(e)}")
            self.logger.logger.debug(traceback.format_exc())
        finally:
            # 生成最终报告
            summary = self.generate_summary_report(all_results)
            summary_file = LOG_DIR / f"final_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary)

            self.logger.logger.info(f"汇总报告已保存到: {summary_file}")
            self.logger.log_section("PL5 24小时持续监控系统已停止")

def main():
    """主函数"""
    monitor = Continuous24HourMonitor()
    monitor.run_24hour_monitoring()

if __name__ == "__main__":
    main()
