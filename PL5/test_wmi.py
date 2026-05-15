#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import platform

print(f"操作系统: {platform.system()}")
print(f"系统版本: {platform.version()}")
print(f"Python版本: {platform.python_version()}")

# 尝试使用wmi模块
print("\n尝试使用wmi模块...")
try:
    import wmi
    c = wmi.WMI()
    
    # 获取CPU使用率
    print("\nCPU信息:")
    for cpu in c.Win32_Processor():
        print(f"CPU名称: {cpu.Name}")
        print(f"核心数: {cpu.NumberOfCores}")
        print(f"线程数: {cpu.NumberOfLogicalProcessors}")
    
    # 获取内存信息
    print("\n内存信息:")
    for memory in c.Win32_ComputerSystem():
        print(f"总内存: {int(memory.TotalPhysicalMemory) / 1024 / 1024 / 1024:.2f} GB")
    
    # 获取磁盘信息
    print("\n磁盘信息:")
    for disk in c.Win32_LogicalDisk(DriveType=3):
        print(f"驱动器: {disk.DeviceID}")
        print(f"卷标: {disk.VolumeName}")
        print(f"文件系统: {disk.FileSystem}")
        print(f"总空间: {int(disk.Size) / 1024 / 1024 / 1024:.2f} GB")
        print(f"可用空间: {int(disk.FreeSpace) / 1024 / 1024 / 1024:.2f} GB")
        print(f"使用率: {100 - (int(disk.FreeSpace) / int(disk.Size) * 100):.2f}%")
        print()
        
except Exception as e:
    print(f"使用wmi模块失败: {e}")

# 尝试使用ctypes
print("\n尝试使用ctypes...")
try:
    import ctypes
    
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ('dwLength', ctypes.c_ulong),
            ('dwMemoryLoad', ctypes.c_ulong),
            ('ullTotalPhys', ctypes.c_ulonglong),
            ('ullAvailPhys', ctypes.c_ulonglong),
            ('ullTotalPageFile', ctypes.c_ulonglong),
            ('ullAvailPageFile', ctypes.c_ulonglong),
            ('ullTotalVirtual', ctypes.c_ulonglong),
            ('ullAvailVirtual', ctypes.c_ulonglong),
            ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
        ]
    
    memory_status = MEMORYSTATUSEX()
    memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
    
    print(f"内存使用率: {memory_status.dwMemoryLoad}%")
    print(f"总物理内存: {memory_status.ullTotalPhys / 1024 / 1024 / 1024:.2f} GB")
    print(f"可用物理内存: {memory_status.ullAvailPhys / 1024 / 1024 / 1024:.2f} GB")
    
except Exception as e:
    print(f"使用ctypes失败: {e}")

# 尝试使用os模块
print("\n尝试使用os模块...")
try:
    import os
    if platform.system() == 'Windows':
        # Windows系统使用fsutil命令
        import subprocess
        result = subprocess.run(['fsutil', 'volume', 'diskfree', 'C:'], capture_output=True, text=True)
        print(f"fsutil输出: {result.stdout}")
    else:
        # 其他系统使用statvfs
        import statvfs
        stat = os.statvfs('/')
        print(f"磁盘总空间: {stat.f_frsize * stat.f_blocks / 1024 / 1024 / 1024:.2f} GB")
        print(f"磁盘可用空间: {stat.f_frsize * stat.f_bavail / 1024 / 1024 / 1024:.2f} GB")
        print(f"磁盘使用率: {(1 - stat.f_bavail / stat.f_blocks) * 100:.2f}%")
        
except Exception as e:
    print(f"使用os模块失败: {e}")