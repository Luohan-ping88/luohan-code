#!/usr/bin/env python3
"""
PL5项目系统全面审计脚本
Comprehensive System Audit Script for PL5 Project
"""

import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
import subprocess
import json

# 配置
PROJECT_ROOT = Path("/workspace/PL5")
LOGS_DIR = PROJECT_ROOT / "logs"
SRC_DIR = PROJECT_ROOT / "src"

# 创建日志目录
LOGS_DIR.mkdir(exist_ok=True)

# 生成日志文件名
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"daily_audit_{TIMESTAMP}.log"
REPORT_FILE = LOGS_DIR / f"audit_report_{TIMESTAMP}.json"

class AuditLogger:
    """审计日志记录器"""
    def __init__(self, log_file):
        self.log_file = log_file
        self.start_time = time.time()
        self.findings = []
        
    def log(self, level, section, message, details=None):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "section": section,
            "message": message,
            "details": details,
            "elapsed": time.time() - self.start_time
        }
        self.findings.append(log_entry)
        
        # 写入日志文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{level}] [{section}] {message}\n")
            if details:
                f.write(f"  Details: {details}\n")
        
        # 打印到控制台
        print(f"[{timestamp}] [{level}] [{section}] {message}")
        if details:
            print(f"  Details: {details}")
    
    def info(self, section, message, details=None):
        self.log("INFO", section, message, details)
    
    def warning(self, section, message, details=None):
        self.log("WARNING", section, message, details)
    
    def error(self, section, message, details=None):
        self.log("ERROR", section, message, details)
    
    def save_report(self):
        """保存JSON报告"""
        report = {
            "audit_start": datetime.fromtimestamp(self.start_time).isoformat(),
            "audit_end": datetime.now().isoformat(),
            "total_duration": time.time() - self.start_time,
            "findings_count": len(self.findings),
            "findings": self.findings
        }
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n报告已保存到: {REPORT_FILE}")

def check_file_exists(logger, file_path, section):
    """检查文件是否存在"""
    if os.path.exists(file_path):
        logger.info(section, f"文件存在: {file_path}")
        return True
    else:
        logger.error(section, f"文件不存在: {file_path}")
        return False

def run_python_test(logger, script_path, section, description=""):
    """运行Python测试脚本"""
    logger.info(section, f"执行测试: {description}")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            logger.info(section, f"测试成功: {description}")
            if result.stdout:
                logger.info(section, f"输出: {result.stdout[:500]}")
            return True, result.stdout, result.stderr
        else:
            logger.error(section, f"测试失败: {description}")
            logger.error(section, f"错误: {result.stderr[:500]}")
            return False, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(section, f"测试超时: {description}")
        return False, "", "Timeout"
    except Exception as e:
        logger.error(section, f"测试异常: {description} - {str(e)}")
        return False, "", str(e)

def check_imports(logger, file_path, section):
    """检查Python文件的导入"""
    logger.info(section, f"检查导入: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        imports = []
        for line in content.split('\n'):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                imports.append(line.strip())
        
        logger.info(section, f"发现 {len(imports)} 个导入语句")
        return True, imports
    except Exception as e:
        logger.error(section, f"读取文件失败: {file_path} - {str(e)}")
        return False, []

def run_audit():
    """运行审计"""
    logger = AuditLogger(LOG_FILE)
    logger.info("SYSTEM", "="*60)
    logger.info("SYSTEM", "PL5项目系统全面审计开始")
    logger.info("SYSTEM", "="*60)
    
    # 1. 训练推理性能及逻辑检测
    logger.info("TRAINING", "\n" + "="*60)
    logger.info("TRAINING", "1. 训练推理性能及逻辑检测")
    logger.info("TRAINING", "="*60)
    
    # 1.1 预测功能测试
    predictor_path = SRC_DIR / "core" / "models" / "predictor.py"
    if check_file_exists(logger, predictor_path, "PREDICTOR"):
        check_imports(logger, predictor_path, "PREDICTOR")
        run_python_test(logger, predictor_path, "PREDICTOR", "预测功能测试")
    
    # 1.2 模型评估
    evaluator_path = SRC_DIR / "core" / "models" / "model_evaluator.py"
    if check_file_exists(logger, evaluator_path, "EVALUATOR"):
        check_imports(logger, evaluator_path, "EVALUATOR")
        run_python_test(logger, evaluator_path, "EVALUATOR", "模型评估")
    
    # 1.3 训练逻辑检查
    training_dir = SRC_DIR / "core" / "training"
    logger.info("TRAINING", f"\n检查训练目录: {training_dir}")
    if training_dir.exists():
        for py_file in training_dir.glob("*.py"):
            check_imports(logger, py_file, "TRAINING")
            run_python_test(logger, py_file, "TRAINING", f"训练逻辑: {py_file.name}")
    else:
        logger.warning("TRAINING", f"训练目录不存在: {training_dir}")
    
    # 1.4 数据处理验证
    collector_path = SRC_DIR / "core" / "data" / "collector.py"
    if check_file_exists(logger, collector_path, "DATA"):
        check_imports(logger, collector_path, "DATA")
        run_python_test(logger, collector_path, "DATA", "数据处理流程验证")
    
    # 2. 代码质量优化
    logger.info("CODE_QUALITY", "\n" + "="*60)
    logger.info("CODE_QUALITY", "2. 代码质量优化检查")
    logger.info("CODE_QUALITY", "="*60)
    
    # 2.1 Python代码检查
    logger.info("CODE_QUALITY", f"\n检查 src/ 目录下的Python代码")
    src_files = list(SRC_DIR.rglob("*.py"))
    logger.info("CODE_QUALITY", f"发现 {len(src_files)} 个Python文件")
    
    import_issues = []
    for py_file in src_files[:20]:  # 限制检查前20个文件
        ok, imports = check_imports(logger, py_file, "CODE_QUALITY")
        if not ok:
            import_issues.append(str(py_file))
    
    # 2.2 pytest测试套件
    logger.info("CODE_QUALITY", "\n运行pytest测试套件")
    pytest_ini = PROJECT_ROOT / "pytest.ini"
    tests_dir = PROJECT_ROOT / "tests"
    
    if pytest_ini.exists() and tests_dir.exists():
        run_python_test(logger, pytest_ini, "PYTEST", "pytest测试套件")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tests_dir), "-v", "--tb=short"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300
            )
            logger.info("PYTEST", f"pytest执行完成, 返回码: {result.returncode}")
            if result.stdout:
                logger.info("PYTEST", f"输出:\n{result.stdout[:1000]}")
            if result.stderr:
                logger.warning("PYTEST", f"错误:\n{result.stderr[:500]}")
        except Exception as e:
            logger.error("PYTEST", f"pytest执行失败: {str(e)}")
    else:
        logger.warning("PYTEST", "pytest.ini 或 tests/ 目录不存在")
    
    # 3. 智能功能执行逻辑检测
    logger.info("AI_LOGIC", "\n" + "="*60)
    logger.info("AI_LOGIC", "3. 智能功能执行逻辑检测")
    logger.info("AI_LOGIC", "="*60)
    
    # 3.1 工具执行逻辑
    tool_path = SRC_DIR / "ai" / "tools" / "pl5_tool.py"
    if check_file_exists(logger, tool_path, "TOOL"):
        check_imports(logger, tool_path, "TOOL")
        run_python_test(logger, tool_path, "TOOL", "工具执行逻辑检查")
    
    # 3.2 智能体编排
    orchestrator_path = SRC_DIR / "ai" / "agents" / "agent_orchestrator.py"
    if check_file_exists(logger, orchestrator_path, "ORCHESTRATOR"):
        check_imports(logger, orchestrator_path, "ORCHESTRATOR")
        run_python_test(logger, orchestrator_path, "ORCHESTRATOR", "智能体编排检查")
    
    # 3.3 集成功能验证
    integration_path = PROJECT_ROOT / "intelligent_scheduler_integration.py"
    if check_file_exists(logger, integration_path, "INTEGRATION"):
        check_imports(logger, integration_path, "INTEGRATION")
        run_python_test(logger, integration_path, "INTEGRATION", "集成功能验证")
    
    # 4. BUG修复
    logger.info("BUG_FIX", "\n" + "="*60)
    logger.info("BUG_FIX", "4. BUG修复检查")
    logger.info("BUG_FIX", "="*60)
    
    # 4.1 日志文件检查
    logger.info("BUG_FIX", "\n检查日志文件")
    log_files = ["scheduler.log", "crash.log", "performance.log"]
    for log_name in log_files:
        log_path = PROJECT_ROOT / log_name
        if log_path.exists():
            logger.info("BUG_FIX", f"日志文件存在: {log_name}")
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    logger.info("BUG_FIX", f"{log_name} 包含 {len(lines)} 行")
                    if len(lines) > 0:
                        logger.info("BUG_FIX", f"最后10行:\n{''.join(lines[-10:])}")
            except Exception as e:
                logger.error("BUG_FIX", f"读取日志失败 {log_name}: {str(e)}")
        else:
            logger.warning("BUG_FIX", f"日志文件不存在: {log_name}")
    
    # 4.2 修复验证脚本
    verify_fixes_path = PROJECT_ROOT / "scripts" / "utility" / "verify_all_fixes.py"
    if check_file_exists(logger, verify_fixes_path, "VERIFY_FIXES"):
        run_python_test(logger, verify_fixes_path, "VERIFY_FIXES", "修复验证")
    
    # 4.3 系统状态检查
    system_checker_path = PROJECT_ROOT / "monitor" / "system_checker.py"
    if check_file_exists(logger, system_checker_path, "SYSTEM_CHECK"):
        run_python_test(logger, system_checker_path, "SYSTEM_CHECK", "系统状态检查")
    
    # 4.4 错误处理检查
    error_handler_path = SRC_DIR / "core" / "utils" / "unified_error_handler.py"
    if check_file_exists(logger, error_handler_path, "ERROR_HANDLER"):
        check_imports(logger, error_handler_path, "ERROR_HANDLER")
        run_python_test(logger, error_handler_path, "ERROR_HANDLER", "错误处理检查")
    
    # 完成
    logger.info("SYSTEM", "\n" + "="*60)
    logger.info("SYSTEM", "PL5项目系统全面审计完成")
    logger.info("SYSTEM", "="*60)
    logger.save_report()
    
    return logger.findings

if __name__ == "__main__":
    try:
        findings = run_audit()
        print(f"\n审计完成，发现 {len(findings)} 条记录")
        print(f"日志文件: {LOG_FILE}")
        print(f"报告文件: {REPORT_FILE}")
    except Exception as e:
        print(f"审计过程出错: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
