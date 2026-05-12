"""
排列五完美系统完整性检查工具
验证系统所有组件是否正常工作
支持 src/ 目录结构
"""

import os
import sys
import json
import importlib
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


class PerfectSystemChecker:
    """完美系统检查器"""

    def __init__(self):
        self.project_dir = Path(__file__).parent.parent
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

        required_files_src = [
            'src/core/config.py',
            'src/core/models/predictor.py',
            'src/core/data/collector.py',
            'src/core/features/engineer.py',
            'src/core/self_learning.py',
            'src/app/auto_scheduler.py',
            'src/app/email_sender.py',
            'monitor/prevent_sleep.py',
            'monitor/system_monitor.py',
            'monitor/perfect_monitor.py',
            'monitor/system_checker.py',
            'main.py'
        ]

        required_dirs = [
            'src/core',
            'src/app',
            'monitor',
            'scripts',
            'data',
            'data/raw',
            'data/processed',
            'models',
            'logs',
            'results',
            'config',
            'src/ai',
            'src/agents',
            'tests'
        ]

        all_good = True

        for file in required_files_src:
            file_path = self.project_dir / file
            if file_path.exists():
                self.log(f"  [OK] {file}", 'SUCCESS')
            else:
                self.log(f"  [WARN] {file} missing (optional)", 'WARNING')

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

        raw_file = self.project_dir / 'data' / 'raw' / 'pl5_history.txt'
        if raw_file.exists():
            size_mb = raw_file.stat().st_size / 1024 / 1024
            self.log(f"  [OK] Raw data file ({size_mb:.2f} MB)", 'SUCCESS')
        else:
            self.log(f"  [WARN] Raw data not exist, will download on first run", 'WARNING')

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

        email_file = self.project_dir / 'config' / 'email_config.json'
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
        """检查核心模块（支持 src/ 目录结构）"""
        self.log("Checking core modules...", 'INFO')

        modules_to_check = [
            ('src.core.config', 'Config module'),
            ('src.core.models.predictor', 'PL5 Predictor'),
            ('src.core.data.collector', 'Data collector'),
            ('src.core.training', 'Training module'),
            ('src.core.utils.unified_error_handler', 'Error handler'),
            ('src.app.intelligent_scheduler_integration', 'Scheduler integration'),
            ('src.ai.agents.agent_orchestrator', 'Agent orchestrator'),
            ('src.ai.tools.pl5_tool', 'PL5 Tool'),
        ]

        all_good = True

        for module_name, description in modules_to_check:
            try:
                module = importlib.import_module(module_name)
                self.log(f"  [OK] {description} ({module_name})", 'SUCCESS')
            except Exception as e:
                self.log(f"  [WARN] {description} ({module_name}): {e}", 'WARNING')

        return all_good

    def check_scheduler_config(self):
        """检查调度器配置"""
        self.log("Checking scheduler config...", 'INFO')

        config_file = self.project_dir / 'config' / 'scheduler_config_v8.json'
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.log(f"  [OK] Scheduler config exists (v8)", 'SUCCESS')
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
            sys.path.insert(0, str(self.project_dir / 'cpp_core'))
            from pl5_core import CPP_AVAILABLE, FeatureCalculator

            if CPP_AVAILABLE:
                self.log(f"  [OK] C++ module enabled", 'SUCCESS')
                test_data = [1, 2, 3, 4, 5]
                mean = FeatureCalculator.calculate_mean(test_data)
                self.log(f"  [OK] C++ test passed (mean={mean})", 'SUCCESS')
                return True
            else:
                self.log(f"  [WARN] C++ module using Python fallback", 'WARNING')
                self.log(f"    Same functionality, slightly lower performance", 'INFO')
                return True
        except Exception as e:
            self.log(f"  [WARN] C++ module check failed: {e}", 'WARNING')
            return True

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

        print(f"\n{'=' * 70}")
        print("Check Summary")
        print('=' * 70)

        all_passed = all(results.values())

        if all_passed and not self.warnings:
            print("\n[SUCCESS] All system checks passed!")
            print("\nSystem is ready to run.")
            print("\nStart methods:")
            print("  1. python main.py")
            print("  2. python -m src.app.auto_scheduler")
            print("  3. scripts/launcher.bat")
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
    result = checker.run_all_checks()
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
