#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5系统自动化审计与优化脚本
执行时间：每天22:00
功能：
1. 检测系统的训练推理性能及逻辑
2. 优化代码质量
3. 检测系统"智能功能执行逻辑"的实现及应用
4. 修复所有在运行过程中的BUG
"""

import sys
import os
import logging
import json
import subprocess
from datetime import datetime
from pathlib import Path
import traceback

# 强制禁用 pyc 缓存
sys.dont_write_bytecode = True

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# 配置日志
LOG_DIR = ROOT_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f'automated_audit_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 审计报告
audit_report = {
    'timestamp': datetime.now().isoformat(),
    'checks': [],
    'issues_found': [],
    'fixes_applied': [],
    'summary': {},
    'performance_metrics': {}
}


def run_command(cmd, cwd=None, timeout=300):
    """执行系统命令"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or str(ROOT_DIR),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, '', '命令执行超时'
    except Exception as e:
        return -1, '', str(e)


def check_system_status():
    """检查系统状态"""
    logger.info("=" * 80)
    logger.info("步骤1: 检查系统状态")
    logger.info("=" * 80)
    
    checks = [
        ('数据目录存在', lambda: (ROOT_DIR / 'data').exists()),
        ('模型目录存在', lambda: (ROOT_DIR / 'models').exists()),
        ('配置目录存在', lambda: (ROOT_DIR / 'config').exists()),
        ('日志目录存在', lambda: (ROOT_DIR / 'logs').exists()),
        ('主程序文件存在', lambda: (ROOT_DIR / 'main.py').exists()),
        ('requirements.txt存在', lambda: (ROOT_DIR / 'requirements.txt').exists()),
    ]
    
    for name, check_fn in checks:
        try:
            result = check_fn()
            audit_report['checks'].append({
                'name': name,
                'status': 'PASS' if result else 'FAIL',
                'timestamp': datetime.now().isoformat()
            })
            logger.info(f"  {'[OK]' if result else '[!!]'} {name}")
        except Exception as e:
            audit_report['checks'].append({
                'name': name,
                'status': 'ERROR',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            logger.error(f"  [ERR] {name}: {e}")


def check_core_modules():
    """检查核心模块"""
    logger.info("\n" + "=" * 80)
    logger.info("步骤2: 检查核心模块导入")
    logger.info("=" * 80)
    
    modules_to_check = [
        'core.config',
        'core.utils.logger',
        'src.core.data.collector',
        'src.core.features.engineer',
        'src.core.models.enhanced_predictor',
        'src.core.self_learning',
        'src.core.orchestrator',
        'monitor.system_monitor',
        'src.agents.orchestrator',
        'src.ai.tools',
    ]
    
    for module_name in modules_to_check:
        try:
            __import__(module_name)
            audit_report['checks'].append({
                'name': f'模块导入: {module_name}',
                'status': 'PASS',
                'timestamp': datetime.now().isoformat()
            })
            logger.info(f"  [OK] {module_name}")
        except Exception as e:
            audit_report['checks'].append({
                'name': f'模块导入: {module_name}',
                'status': 'FAIL',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            audit_report['issues_found'].append({
                'type': 'module_import_error',
                'module': module_name,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            logger.error(f"  [!!] {module_name}: {e}")


def run_smoke_tests():
    """运行冒烟测试"""
    logger.info("\n" + "=" * 80)
    logger.info("步骤3: 运行冒烟测试")
    logger.info("=" * 80)
    
    smoke_scripts = [
        'scripts/smoke_test_v80.py',
        'test_automation.py',
        'test_basic_functionality.py',
    ]
    
    for script in smoke_scripts:
        script_path = ROOT_DIR / script
        if not script_path.exists():
            logger.warning(f"  [SKIP] 脚本不存在: {script}")
            continue
            
        logger.info(f"  运行: {script}")
        code, stdout, stderr = run_command(
            f'python "{script_path}"',
            timeout=300
        )
        
        if code == 0:
            logger.info(f"  [OK] {script} 测试通过")
            audit_report['checks'].append({
                'name': f'冒烟测试: {script}',
                'status': 'PASS',
                'output': stdout[-200:] if len(stdout) > 200 else stdout,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"  [!!] {script} 测试失败")
            logger.error(f"  STDERR: {stderr[:500]}")
            audit_report['checks'].append({
                'name': f'冒烟测试: {script}',
                'status': 'FAIL',
                'output': stderr[:1000],
                'timestamp': datetime.now().isoformat()
            })
            audit_report['issues_found'].append({
                'type': 'smoke_test_failure',
                'script': script,
                'error': stderr
            })


def check_training_performance():
    """检查训练性能"""
    logger.info("\n" + "=" * 80)
    logger.info("步骤4: 检查训练推理性能")
    logger.info("=" * 80)
    
    try:
        # 测试数据加载
        start_time = datetime.now()
        from src.core.data.collector import PL5DataCollector
        collector = PL5DataCollector()
        df = collector.update_data()
        load_time = (datetime.now() - start_time).total_seconds()
        
        if df is not None and len(df) > 0:
            logger.info(f"  [OK] 数据加载: {len(df)} 条, 耗时 {load_time:.2f}s")
            audit_report['performance_metrics']['data_load'] = {
                'record_count': len(df),
                'load_time': load_time,
                'latest_period': str(df['period'].iloc[-1]) if 'period' in df.columns else 'N/A'
            }
            
            # 测试特征工程
            start_time = datetime.now()
            from src.core.features.engineer import FeatureEngineer
            engineer = FeatureEngineer()
            df_features = engineer.extract_all_features(df, select_top=None)
            feature_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"  [OK] 特征工程: {len([c for c in df_features.columns if c not in ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']])} 个特征, 耗时 {feature_time:.2f}s")
            
            # 检查模型状态
            from src.core.models.enhanced_predictor import EnhancedPL5Predictor
            predictor = EnhancedPL5Predictor()
            model_loaded = predictor.load_models()
            logger.info(f"  [OK] 模型状态: {'已加载' if model_loaded else '未找到模型'}")
            
    except Exception as e:
        logger.error(f"  [ERR] 性能检查失败: {e}")
        audit_report['issues_found'].append({
            'type': 'performance_check_error',
            'error': str(e),
            'traceback': traceback.format_exc()
        })


def check_intelligent_features():
    """检查智能功能执行逻辑"""
    logger.info("\n" + "=" * 80)
    logger.info("步骤5: 检查智能功能执行逻辑")
    logger.info("=" * 80)
    
    features_to_check = [
        ('自学习系统', 'src.core.self_learning', 'SelfLearningSystem'),
        ('Agent协调系统', 'src.agents.orchestrator', 'AgentOrchestrator'),
        ('工作流编排', 'src.core.workflow.orchestrator', 'WorkflowOrchestrator'),
        ('性能监控', 'monitor.performance_monitor', 'PerformanceMonitor'),
        ('系统监控', 'monitor.system_monitor', 'SystemMonitor'),
    ]
    
    for feature_name, module_name, class_name in features_to_check:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            # 尝试初始化
            instance = cls()
            logger.info(f"  [OK] {feature_name}: {class_name} 初始化成功")
            audit_report['checks'].append({
                'name': f'智能功能: {feature_name}',
                'status': 'PASS',
                'class': class_name,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.warning(f"  [WARN] {feature_name}: {e}")
            audit_report['checks'].append({
                'name': f'智能功能: {feature_name}',
                'status': 'WARN',
                'warning': str(e),
                'timestamp': datetime.now().isoformat()
            })


def run_pytest():
    """运行pytest测试"""
    logger.info("\n" + "=" * 80)
    logger.info("步骤6: 运行单元测试")
    logger.info("=" * 80)
    
    code, stdout, stderr = run_command(
        'python -m pytest tests/ -v --tb=short -x',
        timeout=600
    )
    
    if code == 0:
        logger.info("  [OK] 所有测试通过")
    else:
        logger.warning("  [WARN] 部分测试失败")
        logger.warning(f"  输出: {stderr[-1000:] if len(stderr) > 1000 else stderr}")
    
    audit_report['test_results'] = {
        'exit_code': code,
        'stdout': stdout[-2000:] if len(stdout) > 2000 else stdout,
        'stderr': stderr[-2000:] if len(stderr) > 2000 else stderr
    }


def check_log_files():
    """检查日志文件中的错误"""
    logger.info("\n" + "=" * 80)
    logger.info("步骤7: 检查日志文件中的错误")
    logger.info("=" * 80)
    
    log_files_to_check = [
        ROOT_DIR / 'logs' / 'main.log',
        ROOT_DIR / 'logs' / 'system.log',
        ROOT_DIR / 'crash.log',
        ROOT_DIR / 'scheduler.log',
        ROOT_DIR / 'performance.log',
    ]
    
    for log_file in log_files_to_check:
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    error_count = content.lower().count('error')
                    warning_count = content.lower().count('warning')
                    exception_count = content.lower().count('exception')
                    logger.info(f"  {log_file.name}: {error_count} 错误, {warning_count} 警告, {exception_count} 异常")
                    
                    if error_count > 0 or exception_count > 0:
                        audit_report['log_issues'].append({
                            'log_file': str(log_file),
                            'error_count': error_count,
                            'warning_count': warning_count,
                            'exception_count': exception_count
                        })
            except Exception as e:
                logger.warning(f"  [WARN] 无法读取 {log_file.name}: {e}")


def attempt_auto_fixes():
    """尝试自动修复常见问题"""
    logger.info("\n" + "=" * 80)
    logger.info("步骤8: 尝试自动修复常见问题")
    logger.info("=" * 80)
    
    fixes_attempted = []
    
    # 修复1: 检查并创建缺失的目录
    dirs_to_ensure = [
        ROOT_DIR / 'data' / 'raw',
        ROOT_DIR / 'data' / 'processed',
        ROOT_DIR / 'models' / 'cache',
        ROOT_DIR / 'logs' / 'archive',
        ROOT_DIR / 'health',
    ]
    
    for dir_path in dirs_to_ensure:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            fixes_attempted.append({
                'type': 'directory_created',
                'path': str(dir_path)
            })
            logger.info(f"  [FIX] 创建目录: {dir_path}")
    
    # 修复2: 清除pyc缓存
    import shutil
    pyc_cleaned = 0
    for pyc_file in ROOT_DIR.rglob('*.pyc'):
        try:
            pyc_file.unlink()
            pyc_cleaned += 1
        except:
            pass
    for pycache_dir in ROOT_DIR.rglob('__pycache__'):
        try:
            shutil.rmtree(pycache_dir)
            pyc_cleaned += 1
        except:
            pass
    if pyc_cleaned > 0:
        fixes_attempted.append({
            'type': 'pyc_cache_cleared',
            'count': pyc_cleaned
        })
        logger.info(f"  [FIX] 清除了 {pyc_cleaned} 个pyc缓存")
    
    audit_report['fixes'] = fixes_attempted


def generate_report():
    """生成审计报告"""
    logger.info("\n" + "=" * 80)
    logger.info("步骤9: 生成审计报告")
    logger.info("=" * 80)
    
    # 统计
    pass_count = sum(1 for check in audit_report['checks'] if check.get('status') == 'PASS')
    fail_count = sum(1 for check in audit_report['checks'] if check.get('status') == 'FAIL')
    warn_count = sum(1 for check in audit_report['checks'] if check.get('status') == 'WARN')
    total_checks = len(audit_report['checks'])
    
    audit_report['summary'] = {
        'total_checks': total_checks,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'warn_count': warn_count,
        'pass_rate': pass_count / total_checks * 100 if total_checks > 0 else 0,
        'issues_found_count': len(audit_report['issues_found']),
        'fixes_applied_count': len(audit_report['fixes_applied'])
    }
    
    # 保存报告
    report_file = LOG_DIR / f'audit_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(audit_report, f, indent=2, ensure_ascii=False, default=str)
    
    logger.info(f"\n审计报告已保存至: {report_file}")
    logger.info(f"\n=== 审计摘要 ===")
    logger.info(f"总检查项: {total_checks}")
    logger.info(f"通过: {pass_count}")
    logger.info(f"失败: {fail_count}")
    logger.info(f"警告: {warn_count}")
    logger.info(f"通过率: {pass_count / total_checks * 100:.1f}%" if total_checks > 0 else "通过率: N/A")
    logger.info(f"发现问题: {len(audit_report['issues_found'])}")
    logger.info(f"已修复: {len(audit_report['fixes_applied'])}")
    logger.info(f"日志文件: {LOG_FILE}")


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("PL5系统自动化审计与优化")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    try:
        check_system_status()
        check_core_modules()
        run_smoke_tests()
        check_training_performance()
        check_intelligent_features()
        run_pytest()
        check_log_files()
        attempt_auto_fixes()
        generate_report()
        
        logger.info("\n" + "=" * 80)
        logger.info("审计完成")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"审计过程发生严重错误: {e}")
        logger.error(traceback.format_exc())
        audit_report['fatal_error'] = str(e)
        audit_report['traceback'] = traceback.format_exc()
        
        # 保存错误报告
        error_report = LOG_DIR / f'audit_error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(error_report, 'w', encoding='utf-8') as f:
            json.dump(audit_report, f, indent=2, ensure_ascii=False, default=str)
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
