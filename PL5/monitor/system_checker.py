"""
排列五完美系统完整性检查工具
验证系统所有组件是否正常工作
"""

import os
import sys
import json
import importlib
from pathlib import Path
from datetime import datetime


class PerfectSystemChecker:
    """完美系统检查器"""
    
    def __init__(self):
        self.project_dir = Path(__file__).parent.parent  # 项目根目录
        self.check_results = []
        self.errors = []
        self.warnings = []
        
    def log(self, message, level='INFO'):
        """记录日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        prefix = {'INFO': '[INFO]', 'SUCCESS': '[OK]', 'WARNING': '[WARN]', 'ERROR': '[ERR]'}.get(level, '[INFO]')
        print(f"{prefix} [{timestamp}] {message}")
        
        if level == 'ERROR':
            self.errors.append(message)
        elif level == 'WARNING':
            self.warnings.append(message)
    
    def check_file_structure(self):
        """检查文件结构"""
        self.log("检查文件结构...", 'INFO')
        
        required_files = [
            'core/config.py',
            'core/data_collector.py',
            'core/feature_engineering.py',
            'core/models.py',
            'core/self_learning.py',
            'app/auto_scheduler.py',
            'app/analyze_and_send.py',
            'app/email_sender.py',
            'monitor/prevent_sleep.py',
            'monitor/system_monitor.py',
            'monitor/perfect_monitor.py',
            'monitor/system_checker.py',
            'main.py'
        ]
        
        required_dirs = [
            'core',
            'app',
            'monitor',
            'scripts',
            'data',
            'data/raw',
            'data/processed',
            'models',
            'logs',
            'results',
            'config'
        ]
        
        all_good = True
        
        # 检查文件
        for file in required_files:
            file_path = self.project_dir / file
            if file_path.exists():
                self.log(f"  [OK] {file}", 'SUCCESS')
            else:
                self.log(f"  [ERR] {file} missing", 'ERROR')
                all_good = False
        
        # 检查目录
        for dir_path in required_dirs:
            full_path = self.project_dir / dir_path
            if full_path.exists():
                self.log(f"  [OK] {dir_path}/", 'SUCCESS')
            else:
                self.log(f"  [WARN] {dir_path}/ not exist, creating...", 'WARNING')
                full_path.mkdir(parents=True, exist_ok=True)
        
        return all_good
    
    def check_dependencies(self):
        """检查依赖"""
        self.log("检查Python依赖...", 'INFO')
        
        required_packages = [
            ('numpy', 'numpy'),
            ('pandas', 'pandas'),
            ('scipy', 'scipy'),
            ('sklearn', 'scikit-learn'),
            ('hmmlearn', 'hmmlearn'),
            ('schedule', 'schedule'),
            ('requests', 'requests'),
            ('psutil', 'psutil'),
        ]
        
        all_good = True
        
        for import_name, package_name in required_packages:
            try:
                module = importlib.import_module(import_name)
                version = getattr(module, '__version__', 'unknown')
                self.log(f"  [OK] {package_name} ({version})", 'SUCCESS')
            except ImportError:
                self.log(f"  [ERR] {package_name} not installed", 'ERROR')
                all_good = False
        
        return all_good
    
    def check_data_files(self):
        """检查数据文件"""
        self.log("检查数据文件...", 'INFO')
        
        # 检查原始数据
        raw_file = self.project_dir / 'data' / 'raw' / 'pl5_history.txt'
        if raw_file.exists():
            size_mb = raw_file.stat().st_size / 1024 / 1024
            self.log(f"  [OK] Raw data file ({size_mb:.2f} MB)", 'SUCCESS')
        else:
            self.log(f"  [WARN] Raw data not exist, will download on first run", 'WARNING')
        
        # 检查处理后的数据
        processed_file = self.project_dir / 'data' / 'processed' / 'pl5_processed.csv'
        if processed_file.exists():
            try:
                import pandas as pd
                df = pd.read_csv(processed_file)
                self.log(f"  [OK] Processed data ({len(df)} records, {len(df.columns)} features)", 'SUCCESS')
            except Exception as e:
                self.log(f"  [ERR] Failed to read processed data: {e}", 'ERROR')
        else:
            self.log(f"  [WARN] Processed data not exist, will generate on first run", 'WARNING')
        
        return True
    
    def check_email_config(self):
        """检查邮件配置"""
        self.log("Checking email config...", 'INFO')
        
        email_file = self.project_dir / 'email_config.json'
        if email_file.exists():
            try:
                with open(email_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.log(f"  [OK] Email config set", 'SUCCESS')
                    self.log(f"    Recipient: {config.get('to_email', 'N/A')}", 'INFO')
                    return True
            except Exception as e:
                self.log(f"  [ERR] Failed to read email config: {e}", 'ERROR')
                return False
        else:
            self.log(f"  [WARN] Email config not exist, copy from email_config.example.json", 'WARNING')
            return False
    
    def check_modules(self):
        """检查核心模块"""
        self.log("Checking core modules...", 'INFO')
        
        modules_to_check = [
            ('core.config', 'Config module'),
            ('core.data_collector', 'Data collector'),
            ('core.feature_engineering', 'Feature engineering'),
            ('core.models', 'Models'),
            ('app.email_sender', 'Email sender'),
        ]
        
        all_good = True
        
        for module_name, description in modules_to_check:
            try:
                module = importlib.import_module(module_name)
                self.log(f"  [OK] {description} ({module_name})", 'SUCCESS')
            except Exception as e:
                self.log(f"  [ERR] {description} load failed: {e}", 'ERROR')
                all_good = False
        
        return all_good
    
    def check_scheduler_config(self):
        """检查调度器配置"""
        self.log("Checking scheduler config...", 'INFO')
        
        config_file = self.project_dir / 'config' / 'scheduler_config.json'
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.log(f"  [OK] Scheduler config exists", 'SUCCESS')
                    self.log(f"    Data fetch time: {config.get('data_fetch_time', 'N/A')}", 'INFO')
                    self.log(f"    Email send time: {config.get('email_send_time', 'N/A')}", 'INFO')
                    return True
            except Exception as e:
                self.log(f"  [ERR] Failed to read scheduler config: {e}", 'ERROR')
                return False
        else:
            self.log(f"  [INFO] Scheduler config will be created on first run", 'INFO')
            return True
    
    def check_cpp_module(self):
        """检查C++模块"""
        self.log("Checking C++ acceleration module...", 'INFO')
        
        try:
            from cpp_core import CPP_AVAILABLE, FeatureCalculator
            
            if CPP_AVAILABLE:
                self.log(f"  [OK] C++ module enabled", 'SUCCESS')
                # 测试功能
                test_data = [1, 2, 3, 4, 5]
                mean = FeatureCalculator.calculate_mean(test_data)
                self.log(f"  [OK] C++ test passed (mean={mean})", 'SUCCESS')
                return True
            else:
                self.log(f"  [WARN] C++ module using Python fallback", 'WARNING')
                self.log(f"    Same functionality, slightly lower performance", 'INFO')
                return True
        except Exception as e:
            self.log(f"  [ERR] C++ module check failed: {e}", 'ERROR')
            return False
    
    def run_all_checks(self):
        """运行所有检查"""
        print("=" * 70)
        print("PL5 Perfect Intelligent Analysis System - Integrity Check")
        print("=" * 70)
        print()
        
        checks = [
            ("File Structure", self.check_file_structure),
            ("Dependencies", self.check_dependencies),
            ("Data Files", self.check_data_files),
            ("Email Config", self.check_email_config),
            ("Core Modules", self.check_modules),
            ("Scheduler Config", self.check_scheduler_config),
            ("C++ Module", self.check_cpp_module),
        ]
        
        results = {}
        for name, check_func in checks:
            print(f"\n{'─' * 70}")
            print(f"[{name}]")
            print('─' * 70)
            try:
                results[name] = check_func()
            except Exception as e:
                self.log(f"Check error: {e}", 'ERROR')
                results[name] = False
        
        # 输出总结
        print(f"\n{'=' * 70}")
        print("Check Summary")
        print('=' * 70)
        
        all_passed = all(results.values())
        
        if all_passed and not self.warnings:
            print("\n[SUCCESS] All system checks passed!")
            print("\nSystem is ready to run.")
            print("\nStart methods:")
            print("  1. Double click: scripts\\launcher.bat")
            print("  2. Command line: python -m app.auto_scheduler")
            print("  3. Background: Double click scripts\\start_hidden.vbs")
        elif all_passed:
            print("\n[WARNING] System check passed with warnings")
            print(f"\nWarnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"  [WARN] {warning}")
        else:
            print("\n[ERROR] System check failed!")
            print(f"\nErrors: {len(self.errors)}")
            for error in self.errors:
                print(f"  [ERR] {error}")
            print(f"\nWarnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"  [WARN] {warning}")
        
        print(f"\n{'=' * 70}")
        
        return all_passed


def main():
    """主函数"""
    checker = PerfectSystemChecker()
    checker.run_all_checks()


if __name__ == "__main__":
    main()
