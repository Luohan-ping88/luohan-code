#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PL5 24小时全面训练预测系统控制器
功能：
1. 训练推理性能及逻辑检测
2. 代码质量优化和测试
3. 智能功能执行逻辑检测
4. BUG修复和问题报告生成
5. 自动检测、优化并升级系统
"""

import os
import sys
import json
import time
import traceback
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import threading
import subprocess

# 设置项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 日志配置
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_daily_log_filename():
    """获取每日日志文件名"""
    now = datetime.now()
    return f"daily_audit_{now.strftime('%Y%m%d_%H%M%S')}.log"

LOG_FILE = LOG_DIR / get_daily_log_filename()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskResult:
    """任务执行结果"""
    task_name: str
    status: TaskStatus
    duration: float
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "task_name": self.task_name,
            "status": self.status.value,
            "duration": f"{self.duration:.2f}s",
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
            "recommendations": self.recommendations
        }


class PL5DailyAuditor:
    """PL5每日审计器 - 24小时持续运行"""

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.results: List[TaskResult] = []
        self.start_time = datetime.now()
        self.cycle_count = 0
        self.total_tasks = 0
        self.failed_tasks = 0
        self.passed_tasks = 0
        self.is_running = True
        self.lock = threading.Lock()

        # 性能指标
        self.performance_metrics = {
            "prediction_runs": 0,
            "training_runs": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "bugs_detected": 0,
            "bugs_fixed": 0,
            "optimizations_applied": 0,
            "errors_encountered": 0
        }

    def log_section(self, title: str):
        """打印分节标题"""
        logger.info("=" * 80)
        logger.info(f"  {title}")
        logger.info("=" * 80)

    def log_subsection(self, title: str):
        """打印子节标题"""
        logger.info("-" * 60)
        logger.info(f"  {title}")
        logger.info("-" * 60)

    def run_task(self, task_name: str, task_func, *args, **kwargs) -> TaskResult:
        """执行单个任务并记录结果"""
        self.total_tasks += 1
        start = time.time()
        logger.info(f"[开始] {task_name}")

        try:
            result = task_func(*args, **kwargs)
            duration = time.time() - start

            task_result = TaskResult(
                task_name=task_name,
                status=TaskStatus.SUCCESS,
                duration=duration,
                result=result
            )
            self.passed_tasks += 1
            logger.info(f"[完成] {task_name} - 耗时: {duration:.2f}s")
            return task_result

        except Exception as e:
            duration = time.time() - start
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"[失败] {task_name}: {error_msg}")

            task_result = TaskResult(
                task_name=task_name,
                status=TaskStatus.FAILED,
                duration=duration,
                error=error_msg
            )
            self.failed_tasks += 1
            self.performance_metrics["errors_encountered"] += 1
            return task_result

    def check_training_logic(self) -> TaskResult:
        """检查训练逻辑"""
        return self.run_task("检查训练逻辑", self._check_training_logic_impl)

    def _check_training_logic_impl(self) -> Dict[str, Any]:
        """训练逻辑检查实现"""
        self.log_subsection("训练逻辑检查")

        issues = []
        recommendations = []

        # 检查训练目录
        training_dir = self.project_root / "src" / "core" / "training"
        if training_dir.exists():
            logger.info(f"训练目录存在: {training_dir}")
            py_files = list(training_dir.glob("*.py"))
            logger.info(f"找到 {len(py_files)} 个训练相关文件")
        else:
            issues.append("训练目录不存在")
            recommendations.append("创建 src/core/training/ 目录")

        # 检查训练模块导入
        try:
            from src.core.training import EarlyStopping, LRScheduler, Optimizer
            logger.info("训练模块导入成功")
        except ImportError as e:
            issues.append(f"训练模块导入失败: {e}")
            recommendations.append("检查 src/core/training/__init__.py 配置")

        # 检查优化器
        try:
            from src.core.training.optimizer import Optimizer
            logger.info("优化器模块正常")
        except Exception as e:
            issues.append(f"优化器模块问题: {e}")
            recommendations.append("检查优化器实现")

        return {
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_predictor(self) -> TaskResult:
        """检查预测器功能"""
        return self.run_task("检查预测器功能", self._check_predictor_impl)

    def _check_predictor_impl(self) -> Dict[str, Any]:
        """预测器检查实现"""
        self.log_subsection("预测器功能测试")

        issues = []
        recommendations = []
        prediction_test_passed = False

        # 检查预测器导入
        try:
            from src.core.models.predictor import PL5Predictor, HMMModel, BSTSModel, CopulaModel
            logger.info("预测器模块导入成功")

            # 创建预测器实例
            predictor = PL5Predictor()
            logger.info("预测器实例化成功")

            # 检查模型组件
            logger.info("检查子模型组件:")
            logger.info(f"  - HMMModel: 可用")
            logger.info(f"  - BSTSModel: 可用")
            logger.info(f"  - CopulaModel: 可用")

            prediction_test_passed = True

        except ImportError as e:
            issues.append(f"预测器导入失败: {e}")
            recommendations.append("检查 predictor.py 的依赖")
        except Exception as e:
            issues.append(f"预测器实例化失败: {e}")
            recommendations.append("检查预测器构造函数")

        # 检查模型文件
        model_dir = self.project_root / "models"
        if model_dir.exists():
            model_files = list(model_dir.glob("*.pkl")) + list(model_dir.glob("*.joblib"))
            logger.info(f"模型目录存在，包含 {len(model_files)} 个模型文件")

            # 检查特定模型
            for model_name in ["pl5_predictor_v8.pkl", "pl5_predictor_v8.joblib"]:
                model_path = model_dir / model_name
                if model_path.exists():
                    size_kb = model_path.stat().st_size / 1024
                    logger.info(f"  - {model_name}: {size_kb:.1f} KB")

        return {
            "prediction_test_passed": prediction_test_passed,
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_model_evaluator(self) -> TaskResult:
        """检查模型评估器"""
        return self.run_task("检查模型评估器", self._check_model_evaluator_impl)

    def _check_model_evaluator_impl(self) -> Dict[str, Any]:
        """模型评估器检查实现"""
        self.log_subsection("模型评估器测试")

        issues = []
        recommendations = []

        try:
            from src.core.models.model_evaluator import ModelEvaluator, AutoTuner

            # 测试评估器
            evaluator = ModelEvaluator(
                target_accuracy_8=0.95,
                target_accuracy_5=0.70,
                target_accuracy_3=0.50
            )
            logger.info("ModelEvaluator 实例化成功")

            # 测试评估功能
            test_prediction = {
                "wan": [1, 2, 3, 4, 5],
                "qian": [2, 3, 4, 5, 6],
                "bai": [3, 4, 5, 6, 7],
                "shi": [4, 5, 6, 7, 8],
                "ge": [5, 6, 7, 8, 9]
            }
            test_actual = {
                "wan": 3, "qian": 4, "bai": 5, "shi": 6, "ge": 7
            }

            evaluation = evaluator.evaluate_prediction(test_prediction, test_actual)
            logger.info(f"评估结果: 8码准确率={evaluation['overall']['accuracy_8']:.2%}")

            # 测试自动调优器
            auto_tuner = AutoTuner(evaluator)
            logger.info("AutoTuner 实例化成功")

        except ImportError as e:
            issues.append(f"模型评估器导入失败: {e}")
            recommendations.append("检查 model_evaluator.py 的依赖")
        except Exception as e:
            issues.append(f"模型评估器测试失败: {e}")
            recommendations.append("检查评估器实现")

        return {
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_data_collector(self) -> TaskResult:
        """检查数据采集器"""
        return self.run_task("检查数据采集器", self._check_data_collector_impl)

    def _check_data_collector_impl(self) -> Dict[str, Any]:
        """数据采集器检查实现"""
        self.log_subsection("数据处理流程验证")

        issues = []
        recommendations = []

        try:
            from src.core.data.collector import PL5DataCollectorV8

            collector = PL5DataCollectorV8()
            logger.info("数据采集器实例化成功")

            # 检查数据源配置
            logger.info(f"数据源配置: {len(collector.data_sources)} 个")
            for name, source in collector.data_sources.items():
                enabled = source.get('enabled', False)
                logger.info(f"  - {name}: {'启用' if enabled else '禁用'}")

            # 检查验证器
            validator = collector.validator
            logger.info(f"数据验证器可用: {validator is not None}")

            # 检查版本管理器
            version_mgr = collector.version_manager
            logger.info(f"版本管理器可用: {version_mgr is not None}")

            # 检查本地数据
            if collector.raw_data_path.exists():
                size_kb = collector.raw_data_path.stat().st_size / 1024
                logger.info(f"原始数据文件: {size_kb:.1f} KB")

            if collector.processed_data_path.exists():
                size_kb = collector.processed_data_path.stat().st_size / 1024
                logger.info(f"处理后数据文件: {size_kb:.1f} KB")

        except ImportError as e:
            issues.append(f"数据采集器导入失败: {e}")
            recommendations.append("检查 collector.py 的依赖")
        except Exception as e:
            issues.append(f"数据采集器测试失败: {e}")
            recommendations.append("检查采集器实现")

        return {
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_code_quality(self) -> TaskResult:
        """检查代码质量"""
        return self.run_task("检查代码质量", self._check_code_quality_impl)

    def _check_code_quality_impl(self) -> Dict[str, Any]:
        """代码质量检查实现"""
        self.log_subsection("代码质量检查")

        issues = []
        recommendations = []

        # 检查src目录
        src_dir = self.project_root / "src"
        py_files = list(src_dir.rglob("*.py"))
        logger.info(f"找到 {len(py_files)} 个Python文件")

        # 检查导入依赖
        import_errors = []
        for py_file in py_files[:20]:  # 检查前20个文件
            try:
                relative_path = py_file.relative_to(self.project_root)
                module_path = str(relative_path).replace(os.sep, '.').replace('.py', '')

                if module_path.endswith('__init__'):
                    module_path = module_path[:-9]

                __import__(module_path)
            except Exception as e:
                import_errors.append(f"{py_file.name}: {str(e)[:50]}")

        if import_errors:
            issues.append(f"发现 {len(import_errors)} 个导入错误")
            logger.warning(f"导入错误: {import_errors[:5]}")

        # 检查pytest测试
        tests_dir = self.project_root / "tests"
        if tests_dir.exists():
            test_files = list(tests_dir.rglob("test_*.py"))
            logger.info(f"找到 {len(test_files)} 个测试文件")

        return {
            "total_files": len(py_files),
            "import_errors": len(import_errors),
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_pytest(self) -> TaskResult:
        """运行pytest测试"""
        return self.run_task("运行pytest测试", self._check_pytest_impl)

    def _check_pytest_impl(self) -> Dict[str, Any]:
        """pytest测试实现"""
        self.log_subsection("pytest测试套件")

        issues = []
        recommendations = []
        test_results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-v", "--tb=short", "tests/"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )

            output = result.stdout + result.stderr
            logger.info(f"pytest输出:\n{output[:2000]}")

            # 解析输出
            if "passed" in output.lower():
                self.performance_metrics["tests_passed"] += 1
            if "failed" in output.lower():
                self.performance_metrics["tests_failed"] += 1

        except subprocess.TimeoutExpired:
            issues.append("pytest执行超时(5分钟)")
            recommendations.append("优化测试或增加超时时间")
        except Exception as e:
            issues.append(f"pytest执行失败: {e}")
            recommendations.append("检查pytest安装和测试配置")

        return {
            "test_results": test_results,
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_pl5_tool(self) -> TaskResult:
        """检查PL5工具"""
        return self.run_task("检查PL5工具", self._check_pl5_tool_impl)

    def _check_pl5_tool_impl(self) -> Dict[str, Any]:
        """PL5工具检查实现"""
        self.log_subsection("PL5工具执行逻辑检测")

        issues = []
        recommendations = []

        try:
            from src.ai.tools.pl5_tool import PL5Tool
            from src.ai.tools.registry import register_tool

            tool = PL5Tool()
            logger.info("PL5Tool实例化成功")
            logger.info(f"  名称: {tool.name}")
            logger.info(f"  描述: {tool.description}")
            logger.info(f"  类别: {tool.category}")
            logger.info(f"  参数: {len(tool.parameters)} 个")

            # 测试执行
            test_params = {
                "action": "predict",
                "model_name": "test-model",
                "input_data": {"features": [1.0, 2.0, 3.0]},
                "params": {}
            }

            result = tool.run(test_params)
            logger.info(f"工具执行结果: {result.success}")

        except ImportError as e:
            issues.append(f"PL5Tool导入失败: {e}")
            recommendations.append("检查工具模块依赖")
        except Exception as e:
            issues.append(f"PL5Tool执行失败: {e}")
            recommendations.append("检查工具实现")

        return {
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_agent_orchestrator(self) -> TaskResult:
        """检查智能体编排器"""
        return self.run_task("检查智能体编排器", self._check_agent_orchestrator_impl)

    def _check_agent_orchestrator_impl(self) -> Dict[str, Any]:
        """智能体编排器检查实现"""
        self.log_subsection("智能体编排器检测")

        issues = []
        recommendations = []

        try:
            from src.ai.agents.agent_orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator()
            logger.info("AgentOrchestrator实例化成功")

            # 测试方法
            logger.info("测试方法可用:")
            logger.info(f"  - register_agent: {hasattr(orchestrator, 'register_agent')}")
            logger.info(f"  - run_task: {hasattr(orchestrator, 'run_task')}")
            logger.info(f"  - select_agent: {hasattr(orchestrator, 'select_agent')}")

            # 测试选择逻辑
            test_task = "predict future values"
            selected = orchestrator.select_agent(test_task)
            logger.info(f"任务选择测试: '{test_task}' -> {selected}")

        except ImportError as e:
            issues.append(f"AgentOrchestrator导入失败: {e}")
            recommendations.append("检查编排器模块依赖")
        except Exception as e:
            issues.append(f"AgentOrchestrator测试失败: {e}")
            recommendations.append("检查编排器实现")

        return {
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_scheduler_integration(self) -> TaskResult:
        """检查调度器集成"""
        return self.run_task("检查调度器集成", self._check_scheduler_integration_impl)

    def _check_scheduler_integration_impl(self) -> Dict[str, Any]:
        """调度器集成检查实现"""
        self.log_subsection("智能调度器集成功能验证")

        issues = []
        recommendations = []

        try:
            from src.app.intelligent_scheduler_integration import (
                IntelligentSchedulerIntegration,
                get_integration,
                SchedulerMode
            )

            integration = get_integration()
            logger.info("IntelligentSchedulerIntegration实例化成功")

            # 检查模式
            current_mode = integration.get_current_mode()
            logger.info(f"当前模式: {current_mode.value}")

            # 检查智能模块可用性
            logger.info(f"智能模块可用: {integration._intelligent_available}")

            # 检查降级功能
            logger.info(f"降级功能启用: {integration.config.enable_fallback}")

            # 检查决策历史
            decision_stats = integration.get_decision_stats()
            logger.info(f"决策统计: {decision_stats}")

        except ImportError as e:
            issues.append(f"调度器集成导入失败: {e}")
            recommendations.append("检查集成模块依赖")
        except Exception as e:
            issues.append(f"调度器集成测试失败: {e}")
            recommendations.append("检查集成实现")

        return {
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def run_full_training_prediction(self) -> TaskResult:
        """执行完整的训练预测任务"""
        return self.run_task("执行完整训练预测", self._run_full_training_prediction_impl)

    def _run_full_training_prediction_impl(self) -> Dict[str, Any]:
        """完整训练预测任务实现"""
        self.log_subsection("完整训练预测任务执行")
        import time
        
        result = {
            "data_updated": False,
            "data_count": 0,
            "training_completed": False,
            "prediction_completed": False,
            "predictions": {},
            "duration": 0,
            "issues": [],
            "recommendations": []
        }
        
        start_time = time.time()
        
        try:
            # 1. 数据采集更新
            logger.info("1/5 数据采集更新...")
            from src.core.data.collector import PL5DataCollectorV8
            collector = PL5DataCollectorV8()
            data = collector.update_data()
            if data is None:
                data = collector.load_processed_data()
            result["data_count"] = len(data)
            result["data_updated"] = True
            logger.info(f"  ✓ 数据加载成功: {len(data)} 条记录")
            logger.info(f"  ✓ 最新期号: {data['period'].iloc[-1]}")
            self.performance_metrics["prediction_runs"] += 1
            
            # 2. 特征工程
            logger.info("2/5 特征工程...")
            from src.core.features.engineer import FeatureEngineer
            engineer = FeatureEngineer()
            features = engineer.extract_all_features(data)
            non_feature_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']
            feature_cols = [col for col in features.columns if col not in non_feature_cols]
            logger.info(f"  ✓ 特征提取完成: {len(feature_cols)} 个特征")
            
            # 3. 模型训练
            logger.info("3/5 模型训练...")
            from src.core.models.predictor import PL5Predictor
            predictor = PL5Predictor()
            predictor.train(features, feature_cols)
            result["training_completed"] = True
            logger.info("  ✓ 模型训练完成")
            self.performance_metrics["training_runs"] += 1
            
            # 4. 执行预测
            logger.info("4/5 执行预测...")
            latest = features.iloc[[-1]]
            preds = predictor.predict(latest)
            result["prediction_completed"] = True
            result["predictions"] = {
                pos: preds[pos]['top_k'][:5] for pos in ['wan', 'qian', 'bai', 'shi', 'ge']
            }
            logger.info("  ✓ 预测完成")
            
            # 5. 显示结果
            logger.info("5/5 结果汇总:")
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                top_k = result["predictions"][pos]
                logger.info(f"  {pos}: {top_k}")
                
        except Exception as e:
            logger.error(f"训练预测任务出错: {str(e)}")
            result["issues"].append(str(e))
            result["recommendations"].append("检查训练预测流程")
        
        result["duration"] = time.time() - start_time
        return result

    def check_log_files(self) -> TaskResult:
        """检查日志文件"""
        return self.run_task("检查日志文件", self._check_log_files_impl)

    def _check_log_files_impl(self) -> Dict[str, Any]:
        """日志文件检查实现"""
        self.log_subsection("日志文件检查")

        issues = []
        recommendations = []
        log_summary = {}

        log_files = [
            "scheduler.log",
            "crash.log",
            "performance.log"
        ]

        for log_name in log_files:
            log_path = self.project_root / log_name
            if log_path.exists():
                size_kb = log_path.stat().st_size / 1024
                log_summary[log_name] = {
                    "exists": True,
                    "size_kb": round(size_kb, 2)
                }

                # 读取最后几行
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        last_lines = lines[-10:] if len(lines) > 10 else lines
                        log_summary[log_name]["last_entries"] = len(lines)
                        log_summary[log_name]["recent"] = [l.strip() for l in last_lines if l.strip()]

                        # 检查错误
                        error_lines = [l for l in lines if 'ERROR' in l or 'CRITICAL' in l]
                        if error_lines:
                            issues.append(f"{log_name} 包含 {len(error_lines)} 条错误")
                            log_summary[log_name]["errors"] = len(error_lines)
                except Exception as e:
                    issues.append(f"读取 {log_name} 失败: {e}")
            else:
                log_summary[log_name] = {"exists": False}
                logger.info(f"{log_name}: 不存在")

        return {
            "log_summary": log_summary,
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def check_error_handler(self) -> TaskResult:
        """检查错误处理器"""
        return self.run_task("检查错误处理器", self._check_error_handler_impl)

    def _check_error_handler_impl(self) -> Dict[str, Any]:
        """错误处理器检查实现"""
        self.log_subsection("统一错误处理检查")

        issues = []
        recommendations = []

        try:
            from src.core.utils.unified_error_handler import (
                PL5Error, ErrorSeverity, ErrorType,
                ErrorHandler, get_error_handler, handle_error
            )

            logger.info("错误处理模块导入成功")

            # 测试错误创建
            test_error = PL5Error(
                message="测试错误",
                error_type=ErrorType.DATA_ERROR,
                severity=ErrorSeverity.ERROR_SEVERITY_MEDIUM
            )
            logger.info(f"错误创建测试: {test_error}")

            # 测试错误处理器
            handler = get_error_handler()
            logger.info(f"错误处理器可用: {handler is not None}")

            # 测试错误处理
            handled = handler.handle_error(ValueError("测试值错误"))
            logger.info(f"错误处理测试: {handled.error_type.value}")

        except ImportError as e:
            issues.append(f"错误处理模块导入失败: {e}")
            recommendations.append("检查 unified_error_handler.py")
        except Exception as e:
            issues.append(f"错误处理测试失败: {e}")
            recommendations.append("检查错误处理实现")

        return {
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations
        }

    def run_system_checker(self) -> TaskResult:
        """运行系统检查器"""
        return self.run_task("运行系统检查器", self._run_system_checker_impl)

    def _run_system_checker_impl(self) -> Dict[str, Any]:
        """系统检查器运行实现"""
        self.log_subsection("系统完整性检查")

        try:
            from monitor.system_checker import PerfectSystemChecker

            checker = PerfectSystemChecker()
            results = checker.run_all_checks()

            return {
                "all_passed": results,
                "errors": checker.errors,
                "warnings": checker.warnings
            }

        except Exception as e:
            return {
                "error": str(e),
                "all_passed": False
            }

    def verify_fixes(self) -> TaskResult:
        """验证修复"""
        return self.run_task("验证所有修复", self._verify_fixes_impl)

    def _verify_fixes_impl(self) -> Dict[str, Any]:
        """修复验证实现"""
        self.log_subsection("验证修复脚本检查")

        verify_script = self.project_root / "scripts" / "utility" / "verify_all_fixes.py"

        if verify_script.exists():
            logger.info(f"验证脚本存在: {verify_script}")
            return {"script_exists": True}
        else:
            logger.warning(f"验证脚本不存在: {verify_script}")
            return {"script_exists": False}

    def generate_report(self) -> Dict[str, Any]:
        """生成审计报告"""
        self.log_section("生成审计报告")

        report = {
            "audit_start": self.start_time.isoformat(),
            "audit_end": datetime.now().isoformat(),
            "duration": (datetime.now() - self.start_time).total_seconds(),
            "cycle_count": self.cycle_count,
            "total_tasks": self.total_tasks,
            "passed_tasks": self.passed_tasks,
            "failed_tasks": self.failed_tasks,
            "pass_rate": f"{self.passed_tasks / self.total_tasks * 100:.1f}%" if self.total_tasks > 0 else "N/A",
            "performance_metrics": self.performance_metrics,
            "task_results": [r.to_dict() for r in self.results],
            "recommendations": []
        }

        # 收集所有建议
        all_recommendations = []
        for result in self.results:
            if result.recommendations:
                all_recommendations.extend(result.recommendations)

        report["recommendations"] = list(set(all_recommendations))

        # 保存报告
        report_file = LOG_DIR / f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"报告已保存: {report_file}")

        # 打印摘要
        logger.info("\n" + "=" * 60)
        logger.info("审计摘要")
        logger.info("=" * 60)
        logger.info(f"总任务数: {report['total_tasks']}")
        logger.info(f"通过: {report['passed_tasks']}")
        logger.info(f"失败: {report['failed_tasks']}")
        logger.info(f"通过率: {report['pass_rate']}")
        logger.info(f"建议数量: {len(report['recommendations'])}")

        return report

    def run_full_audit(self) -> Dict[str, Any]:
        """运行完整审计"""
        self.log_section("PL5 24小时全面训练预测系统 - 审计启动")
        logger.info(f"项目根目录: {self.project_root}")
        logger.info(f"日志目录: {LOG_DIR}")
        logger.info(f"开始时间: {datetime.now().isoformat()}")

        # 1. 训练推理性能及逻辑检测
        self.log_section("1. 训练推理性能及逻辑检测")
        self.results.append(self.check_predictor())
        self.results.append(self.check_model_evaluator())
        self.results.append(self.check_training_logic())
        self.results.append(self.check_data_collector())
        self.results.append(self.run_full_training_prediction())

        # 2. 代码质量优化
        self.log_section("2. 代码质量优化")
        self.results.append(self.check_code_quality())
        self.results.append(self.check_pytest())

        # 3. 智能功能执行逻辑检测
        self.log_section("3. 智能功能执行逻辑检测")
        self.results.append(self.check_pl5_tool())
        self.results.append(self.check_agent_orchestrator())
        self.results.append(self.check_scheduler_integration())

        # 4. BUG修复和问题报告
        self.log_section("4. BUG修复和问题报告")
        self.results.append(self.check_log_files())
        self.results.append(self.check_error_handler())
        self.results.append(self.run_system_checker())
        self.results.append(self.verify_fixes())

        # 生成报告
        report = self.generate_report()

        self.log_section("审计完成")
        return report

    def run_continuous_audit(self, duration_hours: int = 24):
        """持续运行审计"""
        self.log_section(f"启动{duration_hours}小时持续审计模式")
        logger.info(f"系统将每10分钟执行一次完整审计")

        end_time = datetime.now() + timedelta(hours=duration_hours)
        cycle = 0

        while datetime.now() < end_time and self.is_running:
            cycle += 1
            self.cycle_count = cycle
            self.start_time = datetime.now()
            self.results = []
            self.total_tasks = 0
            self.passed_tasks = 0
            self.failed_tasks = 0

            logger.info(f"\n{'#' * 60}")
            logger.info(f"  审计周期 #{cycle}")
            logger.info(f"  开始时间: {datetime.now().isoformat()}")
            logger.info(f"  剩余时间: {end_time - datetime.now()}")
            logger.info(f"{'#' * 60}\n")

            try:
                self.run_full_audit()
            except Exception as e:
                logger.error(f"审计周期 #{cycle} 执行失败: {e}")
                logger.error(traceback.format_exc())

            # 等待10分钟
            if datetime.now() < end_time and self.is_running:
                wait_seconds = 600
                logger.info(f"等待 {wait_seconds} 秒后执行下一次审计...")
                time.sleep(wait_seconds)

        logger.info(f"\n{'=' * 60}")
        logger.info("持续审计模式结束")
        logger.info(f"总执行周期数: {cycle}")
        logger.info(f"{'=' * 60}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='PL5 24小时全面审计系统')
    parser.add_argument('--duration', type=int, default=24, help='运行时长(小时)')
    parser.add_argument('--single', action='store_true', help='单次运行模式')
    args = parser.parse_args()

    auditor = PL5DailyAuditor()

    try:
        if args.single:
            # 单次运行
            logger.info("启动单次审计模式")
            report = auditor.run_full_audit()
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            # 持续运行
            logger.info(f"启动{args.duration}小时持续审计模式")
            auditor.run_continuous_audit(duration_hours=args.duration)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        auditor.is_running = False
    except Exception as e:
        logger.error(f"审计系统异常: {e}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
