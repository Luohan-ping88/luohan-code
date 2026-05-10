#!/usr/bin/env python3
"""
PL5 回滚脚本
用于在部署失败时恢复到之前的版本
"""

import os
import sys
import json
import shutil
import zipfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 【修复】仅导入 psutil（进程过滤用），避免对外部 Python 进程误杀
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志文件
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'deploy.log')

# 备份目录
BACKUP_DIR = os.path.join(PROJECT_ROOT, 'backups')


class RollbackManager:
    """回滚管理器"""

    def __init__(self):
        self.rollback_results: Dict[str, Dict] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._ensure_directories()

    def _ensure_directories(self):
        """确保必要目录存在"""
        os.makedirs(BACKUP_DIR, exist_ok=True)
        os.makedirs(os.path.join(PROJECT_ROOT, 'logs'), exist_ok=True)

    def log(self, message: str, level: str = 'INFO'):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

    def list_backups(self) -> List[Dict]:
        """列出所有可用的备份"""
        backups = []

        if not os.path.exists(BACKUP_DIR):
            return backups

        for item in os.listdir(BACKUP_DIR):
            item_path = os.path.join(BACKUP_DIR, item)

            # 检查是否是备份目录或zip文件
            if os.path.isdir(item_path) and item.startswith('backup_'):
                try:
                    # 解析备份时间
                    timestamp_str = item.replace('backup_', '')
                    backup_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')

                    # 检查备份信息文件
                    info_file = os.path.join(item_path, 'backup_info.json')
                    info = {}
                    if os.path.exists(info_file):
                        with open(info_file, 'r', encoding='utf-8') as f:
                            info = json.load(f)

                    backups.append({
                        'name': item,
                        'path': item_path,
                        'time': backup_time.isoformat(),
                        'info': info
                    })
                except Exception as e:
                    self.log(f"解析备份 {item} 失败: {e}", 'WARNING')

            elif os.path.isfile(item_path) and item.startswith('backup_') and item.endswith('.zip'):
                try:
                    # 解析备份时间
                    timestamp_str = item.replace('backup_', '').replace('.zip', '')
                    backup_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')

                    backups.append({
                        'name': item,
                        'path': item_path,
                        'time': backup_time.isoformat(),
                        'is_zip': True
                    })
                except Exception as e:
                    self.log(f"解析备份 {item} 失败: {e}", 'WARNING')

        # 按时间排序（最新的在前）
        backups.sort(key=lambda x: x['time'], reverse=True)
        return backups

    def create_backup(self, backup_name: str = None, include_data: bool = True) -> bool:
        """创建备份"""
        if backup_name is None:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        backup_path = os.path.join(BACKUP_DIR, backup_name)

        self.log(f"创建备份: {backup_name}...")

        try:
            os.makedirs(backup_path, exist_ok=True)

            # 备份配置
            config_backup_dir = os.path.join(backup_path, 'config')
            os.makedirs(config_backup_dir, exist_ok=True)

            config_dir = os.path.join(PROJECT_ROOT, 'config')
            if os.path.exists(config_dir):
                for item in os.listdir(config_dir):
                    src = os.path.join(config_dir, item)
                    dst = os.path.join(config_backup_dir, item)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)

            # 备份数据
            if include_data:
                data_backup_dir = os.path.join(backup_path, 'data')
                os.makedirs(data_backup_dir, exist_ok=True)

                data_dir = os.path.join(PROJECT_ROOT, 'data')
                if os.path.exists(data_dir):
                    # 只备份原始数据，不备份处理后的数据（可以重新生成）
                    raw_data_dir = os.path.join(data_dir, 'raw')
                    if os.path.exists(raw_data_dir):
                        shutil.copytree(raw_data_dir, os.path.join(data_backup_dir, 'raw'), dirs_exist_ok=True)

            # 备份模型
            models_backup_dir = os.path.join(backup_path, 'models')
            os.makedirs(models_backup_dir, exist_ok=True)

            models_dir = os.path.join(PROJECT_ROOT, 'models')
            if os.path.exists(models_dir):
                for item in os.listdir(models_dir):
                    src = os.path.join(models_dir, item)
                    dst = os.path.join(models_backup_dir, item)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)

            # 备份日志（最近的）
            logs_backup_dir = os.path.join(backup_path, 'logs')
            os.makedirs(logs_backup_dir, exist_ok=True)

            logs_dir = os.path.join(PROJECT_ROOT, 'logs')
            if os.path.exists(logs_dir):
                # 只备份最近的日志文件
                log_files = sorted(
                    [f for f in os.listdir(logs_dir) if f.endswith('.log')],
                    key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)),
                    reverse=True
                )[:5]  # 最近5个日志文件

                for log_file in log_files:
                    src = os.path.join(logs_dir, log_file)
                    dst = os.path.join(logs_backup_dir, log_file)
                    shutil.copy2(src, dst)

            # 创建备份信息文件
            backup_info = {
                'created_at': datetime.now().isoformat(),
                'version': self._get_current_version(),
                'include_data': include_data,
                'backup_name': backup_name
            }

            with open(os.path.join(backup_path, 'backup_info.json'), 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, indent=2, ensure_ascii=False)

            self.log(f"✓ 备份创建成功: {backup_path}")
            self.rollback_results['create_backup'] = {
                'status': 'PASS',
                'backup_name': backup_name,
                'backup_path': backup_path
            }
            return True

        except Exception as e:
            error_msg = f"✗ 备份创建失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.rollback_results['create_backup'] = {
                'status': 'FAIL',
                'error': str(e)
            }
            return False

    def _get_current_version(self) -> str:
        """获取当前版本"""
        try:
            config_file = os.path.join(PROJECT_ROOT, 'config', 'config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('system', {}).get('version', 'unknown')
        except Exception:
            pass
        return 'unknown'

    def restore_backup(self, backup_name: str = None) -> bool:
        """恢复备份"""
        if backup_name is None:
            # 获取最新的备份
            backups = self.list_backups()
            if not backups:
                error_msg = "✗ 没有可用的备份"
                self.log(error_msg, 'ERROR')
                self.errors.append(error_msg)
                return False
            backup_name = backups[0]['name']

        backup_path = os.path.join(BACKUP_DIR, backup_name)

        if not os.path.exists(backup_path):
            error_msg = f"✗ 备份不存在: {backup_name}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

        self.log(f"恢复备份: {backup_name}...")

        try:
            # 如果是zip文件，先解压
            if backup_path.endswith('.zip'):
                extract_dir = backup_path.replace('.zip', '')
                with zipfile.ZipFile(backup_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                backup_path = extract_dir

            # 恢复配置
            config_backup_dir = os.path.join(backup_path, 'config')
            if os.path.exists(config_backup_dir):
                config_dir = os.path.join(PROJECT_ROOT, 'config')
                for item in os.listdir(config_backup_dir):
                    src = os.path.join(config_backup_dir, item)
                    dst = os.path.join(config_dir, item)
                    if os.path.isfile(src):
                        # 备份当前配置
                        if os.path.exists(dst):
                            backup_current = f"{dst}.pre_rollback.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            shutil.copy2(dst, backup_current)
                        shutil.copy2(src, dst)

            # 恢复数据
            data_backup_dir = os.path.join(backup_path, 'data')
            if os.path.exists(data_backup_dir):
                data_dir = os.path.join(PROJECT_ROOT, 'data')
                for item in os.listdir(data_backup_dir):
                    src = os.path.join(data_backup_dir, item)
                    dst = os.path.join(data_dir, item)
                    if os.path.isdir(src):
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)

            # 恢复模型
            models_backup_dir = os.path.join(backup_path, 'models')
            if os.path.exists(models_backup_dir):
                models_dir = os.path.join(PROJECT_ROOT, 'models')
                for item in os.listdir(models_backup_dir):
                    src = os.path.join(models_backup_dir, item)
                    dst = os.path.join(models_dir, item)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)

            self.log(f"✓ 备份恢复成功: {backup_name}")
            self.rollback_results['restore_backup'] = {
                'status': 'PASS',
                'backup_name': backup_name
            }
            return True

        except Exception as e:
            error_msg = f"✗ 备份恢复失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            self.rollback_results['restore_backup'] = {
                'status': 'FAIL',
                'error': str(e)
            }
            return False

    def delete_backup(self, backup_name: str) -> bool:
        """删除备份"""
        backup_path = os.path.join(BACKUP_DIR, backup_name)

        if not os.path.exists(backup_path):
            error_msg = f"✗ 备份不存在: {backup_name}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

        try:
            if os.path.isdir(backup_path):
                shutil.rmtree(backup_path)
            else:
                os.remove(backup_path)

            self.log(f"✓ 备份已删除: {backup_name}")
            return True

        except Exception as e:
            error_msg = f"✗ 删除备份失败: {e}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)
            return False

    def cleanup_old_backups(self, keep_count: int = 10) -> bool:
        """清理旧备份"""
        self.log(f"清理旧备份（保留最近 {keep_count} 个）...")

        backups = self.list_backups()

        if len(backups) <= keep_count:
            self.log("备份数量在限制范围内，无需清理")
            return True

        backups_to_delete = backups[keep_count:]

        deleted = []
        failed = []

        for backup in backups_to_delete:
            if self.delete_backup(backup['name']):
                deleted.append(backup['name'])
            else:
                failed.append(backup['name'])

        if failed:
            warning_msg = f"⚠ 部分备份清理失败: {failed}"
            self.log(warning_msg, 'WARNING')
            self.warnings.append(warning_msg)

        self.log(f"✓ 已清理 {len(deleted)} 个旧备份")
        self.rollback_results['cleanup'] = {
            'status': 'PASS',
            'deleted': deleted,
            'failed': failed
        }
        return True

    def _kill_pl5_processes(self) -> List[Dict]:
        """
        【修复】只杀死 PL5 系统相关的 Python/pythonw 进程。
        策略：用 psutil 扫描进程命令行，只杀工作目录或脚本名匹配 PL5 的进程，
        避免误杀其他 Python 应用（如 IDE、Jupyter 等）。
        """
        killed = []
        if not HAS_PSUTIL:
            self.log("⚠ psutil 未安装，使用 wmic 精确匹配（仅杀 PL5 相关进程）", 'WARNING')
            # Fallback: 用 wmic 获取命令行，过滤出 PL5 进程后再杀
            if sys.platform == 'win32':
                try:
                    out = subprocess.run(
                        ['wmic', 'process', 'where',
                         "name='python.exe' or name='pythonw.exe'",
                         'get', 'processid,commandline'],
                        capture_output=True, text=True, encoding='gbk', errors='replace'
                    )
                    for line in out.stdout.splitlines()[1:]:  # 跳过标题行
                        line = line.strip()
                        if not line:
                            continue
                        # wmic 输出格式: commandline  processid
                        parts = line.rsplit(maxsplit=1)
                        if len(parts) != 2:
                            continue
                        cmdline, pid = parts[0].strip(), parts[1].strip()
                        # 精确匹配：命令行包含 PL5 项目路径或脚本名
                        cmdline_upper = cmdline.upper()
                        project_root_upper = str(PROJECT_ROOT).upper()
                        is_pl5 = (
                            project_root_upper in cmdline_upper
                            or 'AUTO_SCHEDULER' in cmdline_upper
                            or 'MAIN.PY' in cmdline_upper
                        )
                        if is_pl5:
                            subprocess.run(['taskkill', '/F', '/PID', pid],
                                          capture_output=True)
                            killed.append({'pid': pid, 'name': 'python/pythonw',
                                           'cmdline': cmdline[:80]})
                            self.log(f"  → 终止 PL5 进程 PID={pid}: {cmdline[:80]}")
                except Exception as e:
                    self.log(f"  wmic 查询失败: {e}", 'WARNING')
            return killed

        # PL5 进程识别关键词（命令行列表中出现任意一个即认为是 PL5 进程）
        pl5_identifiers = [
            'auto_scheduler',
            'main.py',
            'pl5_',
            'prevent_sleep',
            'system_monitor',
            'sentinel_service',
            'data_agent',
            'experiment_agent',
            'evaluation_agent',
            'orchestrator',
        ]
        # 同时要求工作目录在 PROJECT_ROOT 下，防止其他项目的同名脚本被误杀
        project_root_lower = str(PROJECT_ROOT).lower().replace('\\', '/')

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
            try:
                pinfo = proc.info
                name = pinfo['name'] or ''
                cmdline = ' '.join(pinfo['cmdline'] or [])
                cmdline_lower = cmdline.lower()
                cwd = (pinfo['cwd'] or '').replace('\\', '/').lower()

                if name.lower() not in ('python.exe', 'python', 'pythonw.exe'):
                    continue

                # 条件1：工作目录在 PL5 项目根目录下
                in_pl5_dir = cwd.startswith(project_root_lower) or project_root_lower in cwd

                # 条件2：命令行包含 PL5 特征关键词
                has_pl5_keyword = any(kw in cmdline_lower for kw in pl5_identifiers)

                if in_pl5_dir and has_pl5_keyword:
                    pid = pinfo['pid']
                    try:
                        proc.terminate()
                        killed.append({'pid': pid, 'name': name, 'cmdline': cmdline[:80]})
                        self.log(f"  → 终止 PL5 进程 PID={pid}: {cmdline[:80]}")
                    except psutil.NoSuchProcess:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return killed

    def auto_rollback(self) -> bool:
        """自动回滚到最新备份"""
        self.log("=" * 50)
        self.log("开始自动回滚")
        self.log("=" * 50)

        # 1. 【修复】只停止 PL5 相关进程，避免误杀其他 Python 应用
        self.log("停止 PL5 服务（仅本系统相关进程）...")
        try:
            killed = self._kill_pl5_processes()
            if killed:
                self.log(f"✓ 已停止 {len(killed)} 个 PL5 进程")
                for k in killed:
                    self.log(f"    PID={k['pid']} {k['name']}")
            else:
                self.log("  未发现运行中的 PL5 进程")
        except Exception as e:
            self.log(f"⚠ 停止服务时出错: {e}", 'WARNING')

        # 2. 恢复备份
        if not self.restore_backup():
            self.log("✗ 回滚失败")
            return False

        # 3. 验证恢复
        self.log("验证恢复...")
        # 这里可以调用 post_deploy_verify.py 进行验证

        self.log("=" * 50)
        self.log("✓ 自动回滚完成")
        self.log("=" * 50)

        return True

    def run_rollback_operation(self, operation: str, **kwargs) -> Tuple[bool, Dict]:
        """运行回滚操作"""
        self.log("=" * 50)
        self.log(f"执行回滚操作: {operation}")
        self.log("=" * 50)

        success = False

        if operation == 'create':
            success = self.create_backup(
                backup_name=kwargs.get('backup_name'),
                include_data=kwargs.get('include_data', True)
            )
        elif operation == 'restore':
            success = self.restore_backup(kwargs.get('backup_name'))
        elif operation == 'list':
            backups = self.list_backups()
            self.log(f"可用备份 ({len(backups)} 个):")
            for i, backup in enumerate(backups[:10], 1):  # 只显示前10个
                self.log(f"  {i}. {backup['name']} - {backup['time']}")
            self.rollback_results['list'] = {
                'status': 'PASS',
                'backups': backups
            }
            success = True
        elif operation == 'cleanup':
            success = self.cleanup_old_backups(kwargs.get('keep_count', 10))
        elif operation == 'auto':
            success = self.auto_rollback()
        else:
            error_msg = f"✗ 未知操作: {operation}"
            self.log(error_msg, 'ERROR')
            self.errors.append(error_msg)

        return success, {
            'success': success,
            'operation': operation,
            'errors': self.errors,
            'warnings': self.warnings,
            'results': self.rollback_results
        }


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python rollback.py [create|restore|list|cleanup|auto] [options]")
        print("")
        print("操作:")
        print("  create              创建新备份")
        print("  restore [name]      恢复指定备份（默认最新）")
        print("  list                列出所有备份")
        print("  cleanup [count]     清理旧备份（默认保留10个）")
        print("  auto                自动回滚到最新备份")
        return 1

    operation = sys.argv[1]
    manager = RollbackManager()

    kwargs = {}

    if operation == 'create':
        if len(sys.argv) > 2:
            kwargs['backup_name'] = sys.argv[2]
    elif operation == 'restore':
        if len(sys.argv) > 2:
            kwargs['backup_name'] = sys.argv[2]
    elif operation == 'cleanup':
        if len(sys.argv) > 2:
            kwargs['keep_count'] = int(sys.argv[2])

    success, results = manager.run_rollback_operation(operation, **kwargs)

    # 输出JSON格式的结果
    if '--json' in sys.argv:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
