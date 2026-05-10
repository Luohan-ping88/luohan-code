#!/usr/bin/env python3
"""
停止PL5相关进程 - 精确匹配版
【修复V3.1】支持模块方式启动的进程（-m src.app.auto_scheduler_v8）
"""

import psutil
import time

# PL5项目根目录路径（用于精确匹配）
PL5_PROJECT_PATHS = [
    '\\PL5\\',
    '/PL5/',
    'E:\\PL5',
    'D:\\PL5',
]

# PL5特定标识符
PL5_SPECIFIC_IDENTIFIERS = [
    'auto_scheduler_v8',
    'process_watchdog',
    'prevent_sleep',
    'pl5_intelligent_system',
    'start_system',
    'start_sentinel',
    'launch_simple',
    'src.app.auto_scheduler_v8',
]


def _is_in_pl5_project(cmdline_str: str) -> bool:
    """检查命令行是否在PL5项目目录下"""
    if not cmdline_str:
        return False
    cmdline_lower = cmdline_str.lower()
    return any(path.lower() in cmdline_lower for path in PL5_PROJECT_PATHS)


def _check_module_mode(cmdline_str: str) -> bool:
    """检查是否是模块方式启动的PL5进程"""
    if not cmdline_str:
        return False
    cmdline_lower = cmdline_str.lower()
    # 模块方式启动：pythonw.exe -m src.app.auto_scheduler_v8
    # 这种情况下命令行中没有项目路径，但使用了PL5的模块名
    if 'src.app.auto_scheduler_v8' in cmdline_lower and 'python' in cmdline_lower:
        return True
    return False


def _is_pl5_process_strict(cmdline_str: str, process_name: str) -> bool:
    """
    严格检查进程是否属于PL5系统【V3.1修复】

    匹配规则：
    1. 是Python进程（包含python或pythonw）
    2. 包含至少一个PL5特定标识符
    3. 在PL5项目目录下运行 OR 使用PL5模块方式启动

    Args:
        cmdline_str: 命令行字符串
        process_name: 进程名

    Returns:
        bool: 是否属于PL5系统进程
    """
    if not cmdline_str:
        return False

    cmdline_str_lower = cmdline_str.lower()

    # 规则1：必须是Python进程
    is_python = 'python' in process_name.lower() if process_name else False
    if not is_python:
        return False

    # 规则2：必须包含至少一个PL5特定标识符
    has_pl5_identifier = any(pid in cmdline_str_lower for pid in PL5_SPECIFIC_IDENTIFIERS)
    if not has_pl5_identifier:
        return False

    # 规则3：在PL5项目目录下 OR 使用模块方式启动
    has_pl5_path = _is_in_pl5_project(cmdline_str_lower)
    has_module_mode = _check_module_mode(cmdline_str_lower)
    return has_pl5_path or has_module_mode


def stop_pl5_processes():
    """停止所有PL5相关进程"""
    stopped = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline'] or []
            cmdline_str = ' '.join(cmdline)
            process_name = proc.info['name'] or ''

            if _is_pl5_process_strict(cmdline_str, process_name):
                pid = proc.info['pid']
                proc_obj = psutil.Process(pid)
                print(f'  [停止] PL5进程 PID={pid}: {cmdline_str[:80]}...')
                proc_obj.terminate()
                try:
                    proc_obj.wait(timeout=5)
                    stopped.append(pid)
                except psutil.TimeoutExpired:
                    print(f'  [强制] 进程 {pid} 未响应，强制终止')
                    proc_obj.kill()
                    stopped.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            print(f'  [错误] {e}')

    if stopped:
        print(f'  [完成] 已安全停止 {len(stopped)} 个PL5进程')
    else:
        print('  [完成] 未发现PL5相关进程')
    return stopped


def verify_no_remaining():
    """验证是否有PL5进程残留"""
    remaining = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline'] or []
            cmdline_str = ' '.join(cmdline)
            process_name = proc.info['name'] or ''

            if _is_pl5_process_strict(cmdline_str, process_name):
                remaining.append(proc.info['pid'])
        except:
            pass

    if remaining:
        print(f'  [警告] 仍有 {len(remaining)} 个PL5进程残留')
    else:
        print('  [确认] 无PL5相关进程残留')
    return remaining


if __name__ == '__main__':
    print('[1/3] 精确终止PL5相关进程（V3.1安全版）...')
    stop_pl5_processes()
    time.sleep(2)
    print('[2/3] 验证状态...')
    verify_no_remaining()
    print('[3/3] 完成')
