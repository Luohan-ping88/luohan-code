#!/usr/bin/env python3

"""
PL5 部署测试脚本
用于测试部署流程的完整性
"""

import os
import sys
import time
import requests
import json
from datetime import datetime

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 日志文件
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'deployment_test.log')

# 确保日志目录存在
os.makedirs(os.path.join(PROJECT_ROOT, 'logs'), exist_ok=True)

def log(message):
    """记录日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_message + '\n')

def test_environment():
    """测试环境"""
    log("=== 测试环境 ===")
    
    # 检查Python版本
    import sys
    log(f"Python版本: {sys.version}")
    
    # 检查依赖
    try:
        import fastapi
        import uvicorn
        import openai
        log("✓ 核心依赖已安装")
    except ImportError as e:
        log(f"✗ 依赖缺失: {e}")
        return False
    
    # 检查配置文件
    config_files = [
        'requirements.txt',
        'Dockerfile',
        'docker-compose.yml'
    ]
    
    for config_file in config_files:
        if os.path.exists(os.path.join(PROJECT_ROOT, config_file)):
            log(f"✓ {config_file} 存在")
        else:
            log(f"✗ {config_file} 不存在")
            return False
    
    return True

def test_service_startup():
    """测试服务启动"""
    log("=== 测试服务启动 ===")
    
    # 检查服务是否在运行
    try:
        response = requests.get('http://localhost:8000/api/health', timeout=5)
        if response.status_code == 200:
            log("✓ 服务已启动")
            return True
        else:
            log(f"✗ 服务状态异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        log("✗ 服务未启动")
        return False
    except Exception as e:
        log(f"✗ 测试服务启动失败: {e}")
        return False

def test_api_endpoints():
    """测试API接口"""
    log("=== 测试API接口 ===")
    
    endpoints = [
        '/api/health'
    ]
    
    all_passed = True
    for endpoint in endpoints:
        try:
            url = f'http://localhost:8000{endpoint}'
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                log(f"✓ {endpoint} 正常响应")
            else:
                log(f"✗ {endpoint} 响应异常: {response.status_code}")
                all_passed = False
        except Exception as e:
            log(f"✗ {endpoint} 测试失败: {e}")
            all_passed = False
    
    return all_passed

def test_core_functionality():
    """测试核心功能"""
    log("=== 测试核心功能 ===")
    
    # 测试训练功能
    try:
        import sys
        sys.path.insert(0, PROJECT_ROOT)
        from src.core.orchestrator import PL5Orchestrator
        
        orchestrator = PL5Orchestrator()
        status = orchestrator.get_status()
        log(f"✓ 系统状态检查成功: {status}")
        orchestrator.shutdown()
        return True
    except Exception as e:
        log(f"✗ 核心功能测试失败: {e}")
        return False

def test_performance():
    """测试性能"""
    log("=== 测试性能 ===")
    
    # 测试API响应时间
    start_time = time.time()
    try:
        response = requests.get('http://localhost:8000/api/health', timeout=5)
        end_time = time.time()
        response_time = end_time - start_time
        log(f"✓ API响应时间: {response_time:.2f}秒")
        if response_time < 1.0:
            log("✓ 性能良好")
        else:
            log("⚠ 性能一般")
        return True
    except Exception as e:
        log(f"✗ 性能测试失败: {e}")
        return False

def main():
    """主函数"""
    log("=== PL5 部署测试开始 ===")
    
    # 测试环境
    if not test_environment():
        log("环境测试失败")
        return 1
    
    # 测试服务启动
    if not test_service_startup():
        log("服务启动测试失败")
        return 1
    
    # 测试API接口
    if not test_api_endpoints():
        log("API接口测试失败")
        return 1
    
    # 测试核心功能
    if not test_core_functionality():
        log("核心功能测试失败")
        return 1
    
    # 测试性能
    if not test_performance():
        log("性能测试失败")
        return 1
    
    log("=== 部署测试完成，所有测试通过 ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
