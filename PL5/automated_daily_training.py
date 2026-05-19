#!/usr/bin/env python3
"""
PL5 日循环训练自动化脚本
功能：
1. 执行完整日循环训练流程
2. 监控系统性能
3. 检测异常和问题
4. 自动修复问题
5. 生成报告
"""

import sys
import os
import subprocess
import time
import psutil
import json
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PL5Automation:
    def __init__(self):
        self.project_dir = Path("/workspace/PL5")
        self.logs_dir = self.project_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        self.start_time = datetime.now()
        self.report_data = {
            "training_success": False,
            "performance_issues": [],
            "code_quality_issues": [],
            "fixes": [],
            "warnings": [],
            "errors": [],
            "system_suggestions": []
        }
        self.timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.report_path = self.logs_dir / f"automation_report_{self.timestamp}.txt"

    def log_info(self, message):
        logger.info(message)
        self._write_to_report(f"[INFO] {message}")

    def log_warning(self, message):
        logger.warning(message)
        self.report_data["warnings"].append(message)
        self._write_to_report(f"[WARNING] {message}")

    def log_error(self, message):
        logger.error(message)
        self.report_data["errors"].append(message)
        self._write_to_report(f"[ERROR] {message}")

    def _write_to_report(self, message):
        """写入报告"""
        with open(self.report_path, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")

    def monitor_system(self):
        """监控系统性能"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            self.log_info(f"系统监控 - CPU: {cpu_percent}%, 内存: {memory.percent}%, 磁盘: {disk.percent}%")

            if cpu_percent > 90:
                self.report_data["performance_issues"].append(f"CPU使用率过高: {cpu_percent}%")
            if memory.percent > 90:
                self.report_data["performance_issues"].append(f"内存使用率过高: {memory.percent}%")
            if disk.percent > 90:
                self.report_data["performance_issues"].append(f"磁盘使用率过高: {disk.percent}%")

            return True
        except Exception as e:
            self.log_error(f"系统监控失败: {str(e)}")
            return False

    def run_command(self, cmd, description, max_retries=2):
        """运行命令并监控"""
        os.chdir(self.project_dir)
        
        for attempt in range(max_retries + 1):
            try:
                self.log_info(f"开始执行: {description}")
                self.log_info(f"命令: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
                
                self.monitor_system()
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                output_lines = []
                for line in process.stdout:
                    print(line, end='')
                    output_lines.append(line)
                    line_lower = line.lower()
                    if 'warning' in line_lower or 'warn' in line_lower:
                        self.log_warning(f"检测到警告: {line.strip()}")
                    if 'error' in line_lower or 'exception' in line_lower or 'traceback' in line_lower:
                        self.log_error(f"检测到错误: {line.strip()}")
                
                process.wait()
                
                if process.returncode == 0:
                    self.log_info(f"{description} 执行成功")
                    return True, output_lines
                else:
                    if attempt < max_retries:
                        self.log_warning(f"{description} 失败，第 {attempt + 1} 次重试...")
                        time.sleep(5)
                    else:
                        self.log_error(f"{description} 执行失败，返回码: {process.returncode}")
                        return False, output_lines
                        
            except Exception as e:
                if attempt < max_retries:
                    self.log_warning(f"{description} 异常，第 {attempt + 1} 次重试: {str(e)}")
                    time.sleep(5)
                else:
                    self.log_error(f"{description} 执行异常: {str(e)}")
                    return False, []

    def check_and_fix_issues(self):
        """检查并修复常见问题"""
        try:
            # 检查数据文件
            data_raw = self.project_dir / "data" / "raw" / "pl5_history.txt"
            if not data_raw.exists():
                self.log_warning("原始数据文件不存在，检查是否有其他数据源...")
            
            # 检查配置文件
            config_files = [
                self.project_dir / "config" / "config.json",
                self.project_dir / "config" / "email_config.json"
            ]
            for config_file in config_files:
                if not config_file.exists():
                    self.log_warning(f"配置文件不存在: {config_file}")
            
            # 检查Python环境
            self.log_info("检查Python依赖...")
            requirements_path = self.project_dir / "requirements.txt"
            if requirements_path.exists():
                with open(requirements_path, 'r') as f:
                    requirements = f.read()
                self.log_info("依赖检查完成")
            
            return True
        except Exception as e:
            self.log_error(f"检查和修复问题时出错: {str(e)}")
            return False

    def run(self):
        """执行完整的日循环训练流程"""
        self.log_info("="*80)
        self.log_info("PL5 日循环训练自动化执行开始")
        self.log_info(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log_info("="*80)

        # 检查问题
        self.check_and_fix_issues()
        self.monitor_system()

        # 步骤1: 执行完整日循环训练流程
        self.log_info("\n" + "="*60)
        self.log_info("步骤 1/3: 执行完整日循环训练流程")
        self.log_info("="*60)
        
        success1, _ = self.run_command(
            ["python", "main.py", "schedule", "--once"],
            "完整日循环训练"
        )

        if not success1:
            self.log_warning("完整日循环训练失败，尝试分步执行...")
            # 尝试分步执行
            self.log_info("尝试执行单独训练流程...")
            success_train, _ = self.run_command(
                ["python", "main.py", "train"],
                "单独训练流程"
            )
            if success_train:
                self.log_info("单独训练成功")
                success1 = True
            else:
                self.log_error("单独训练也失败了")

        # 步骤2: 执行预测
        self.log_info("\n" + "="*60)
        self.log_info("步骤 2/3: 执行预测")
        self.log_info("="*60)
        
        success2, _ = self.run_command(
            ["python", "main.py", "predict"],
            "预测流程"
        )

        # 步骤3: 发送训练报告邮件
        self.log_info("\n" + "="*60)
        self.log_info("步骤 3/3: 发送训练报告邮件")
        self.log_info("="*60)
        
        success3, _ = self.run_command(
            ["python", "main.py", "analyze"],
            "分析与邮件发送"
        )

        # 更新报告状态
        self.report_data["training_success"] = success1 and success2
        self.log_info("\n" + "="*60)
        self.log_info("任务执行结果")
        self.log_info("="*60)
        self.log_info(f"完整日循环训练: {'成功' if success1 else '失败'}")
        self.log_info(f"预测: {'成功' if success2 else '失败'}")
        self.log_info(f"分析邮件: {'成功' if success3 else '失败'}")

        # 生成最终报告
        self.generate_final_report(success1, success2, success3)

        return success1

    def generate_final_report(self, success1, success2, success3):
        """生成最终报告"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        self.log_info("\n" + "="*80)
        self.log_info("最终训练状态报告")
        self.log_info("="*80)
        self._write_to_report("\n" + "="*80)
        self._write_to_report("PL5 日循环训练自动化报告")
        self._write_to_report("="*80)
        self._write_to_report(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self._write_to_report(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self._write_to_report(f"总耗时: {duration:.1f}秒")
        self._write_to_report("")
        self._write_to_report("执行结果:")
        self._write_to_report(f"  完整日循环训练: {'✅ 成功' if success1 else '❌ 失败'}")
        self._write_to_report(f"  预测流程: {'✅ 成功' if success2 else '❌ 失败'}")
        self._write_to_report(f"  分析邮件: {'✅ 成功' if success3 else '❌ 失败'}")
        self._write_to_report(f"  整体状态: {'✅ 成功' if (success1 and success2) else '❌ 失败'}")

        if self.report_data["performance_issues"]:
            self._write_to_report("\n性能问题:")
            for issue in self.report_data["performance_issues"]:
                self._write_to_report(f"  - {issue}")

        if self.report_data["warnings"]:
            self._write_to_report("\n警告信息:")
            for warning in self.report_data["warnings"][-20:]:  # 只显示最后20个警告
                self._write_to_report(f"  - {warning}")

        if self.report_data["errors"]:
            self._write_to_report("\n错误信息:")
            for error in self.report_data["errors"]:
                self._write_to_report(f"  - {error}")

        if self.report_data["fixes"]:
            self._write_to_report("\n已执行的修复:")
            for fix in self.report_data["fixes"]:
                self._write_to_report(f"  - {fix}")

        # 系统建议
        self._write_to_report("\n系统建议:")
        if success1 and success2:
            self._write_to_report("  ✅ 训练和预测成功完成，可以继续使用系统")
        else:
            self._write_to_report("  ⚠️  部分任务失败，建议检查错误日志并修复问题")
        
        if self.report_data["performance_issues"]:
            self._write_to_report("  ⚠️  存在性能问题，建议检查系统资源")

        self._write_to_report("\n" + "="*80)
        self.log_info(f"报告已保存到: {self.report_path}")

def main():
    """主函数"""
    automation = PL5Automation()
    
    try:
        success = automation.run()
        return 0 if success else 1
    except KeyboardInterrupt:
        automation.log_info("用户中断执行")
        return 130
    except Exception as e:
        automation.log_error(f"自动化执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

