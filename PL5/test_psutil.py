#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import psutil

print("测试psutil功能")
print("=" * 50)

# 测试CPU使用率
try:
    cpu_percent = psutil.cpu_percent(interval=0.1)
    print(f"CPU使用率: {cpu_percent}%")
except Exception as e:
    print(f"获取CPU使用率失败: {e}")

# 测试内存使用
try:
    memory = psutil.virtual_memory()
    print(f"内存使用率: {memory.percent}%")
    print(f"内存使用: {memory.used / 1024 / 1024:.2f} MB")
    print(f"内存总量: {memory.total / 1024 / 1024:.2f} MB")
except Exception as e:
    print(f"获取内存使用失败: {e}")

# 测试磁盘空间
try:
    disk = psutil.disk_usage('C:')
    print(f"磁盘使用率: {disk.percent}%")
    print(f"磁盘使用: {disk.used / 1024 / 1024 / 1024:.2f} GB")
    print(f"磁盘总量: {disk.total / 1024 / 1024 / 1024:.2f} GB")
except Exception as e:
    print(f"获取磁盘空间失败: {e}")

# 测试网络IO
try:
    network = psutil.net_io_counters()
    print(f"网络发送: {network.bytes_sent / 1024 / 1024:.2f} MB")
    print(f"网络接收: {network.bytes_recv / 1024 / 1024:.2f} MB")
except Exception as e:
    print(f"获取网络IO失败: {e}")

# 测试进程信息
try:
    process = psutil.Process()
    print(f"进程ID: {process.pid}")
    print(f"进程CPU使用率: {process.cpu_percent(interval=0.1)}%")
    print(f"进程内存使用: {process.memory_info().rss / 1024 / 1024:.2f} MB")
except Exception as e:
    print(f"获取进程信息失败: {e}")

print("=" * 50)
print("测试完成")