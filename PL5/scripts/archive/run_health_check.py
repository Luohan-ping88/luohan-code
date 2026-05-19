#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行系统健康检查并输出详细结果
"""

from src.core.monitoring.health_check import check_health

if __name__ == "__main__":
    print("正在执行系统健康检查...")
    result = check_health()
    print("\n健康检查结果:")
    print(f"整体状态: {result['overall_status']}")
    print(f"检查时间: {result['timestamp']}")
    
    print("\n详细检查结果:")
    for check_name, check_result in result['checks'].items():
        print(f"{check_name}: {check_result['status']} - {check_result['message']}")
        if 'details' in check_result:
            for detail_key, detail_value in check_result['details'].items():
                print(f"  {detail_key}: {detail_value}")
    
    print("\n系统信息:")
    if 'system_info' in result['details']:
        for key, value in result['details']['system_info'].items():
            print(f"{key}: {value}")
    
    print("\n资源使用情况:")
    if 'resource_usage' in result['details']:
        for key, value in result['details']['resource_usage'].items():
            print(f"{key}: {value}")
