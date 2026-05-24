#!/usr/bin/env python3
"""快速系统健康检查脚本"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

print('='*70)
print('🏥 系统健康检查')
print('='*70)

# 检查项目结构
print('\n📁 项目结构检查:')
critical_dirs = ['data', 'models', 'config', 'logs', 'src']
for dir_name in critical_dirs:
    if Path(dir_name).exists():
        print(f'   ✅ {dir_name}/')
    else:
        print(f'   ❌ {dir_name}/ (不存在)')

# 检查配置文件
print('\n⚙️ 配置文件检查:')
config_files = ['.env', 'config/email_config.json', 'config/config.json']
for config_file in config_files:
    if Path(config_file).exists():
        print(f'   ✅ {config_file}')
    else:
        print(f'   ⚠️  {config_file} (不存在)')

# 检查Python模块导入
print('\n📦 核心模块导入检查:')
modules_to_check = [
    ('numpy', 'NumPy'),
    ('pandas', 'Pandas'),
    ('sklearn', 'Scikit-learn'),
    ('psutil', 'Psutil'),
    ('dotenv', 'Python-dotenv'),
]

for module_name, display_name in modules_to_check:
    try:
        __import__(module_name)
        print(f'   ✅ {display_name}')
    except ImportError:
        print(f'   ❌ {display_name} (未安装)')

# 检查项目模块
print('\n🔧 项目模块导入检查:')
project_modules = [
    'src.core.config.env_config',
    'src.app.email_sender',
]

for module_path in project_modules:
    try:
        __import__(module_path)
        print(f'   ✅ {module_path}')
    except Exception as e:
        print(f'   ❌ {module_path} ({str(e)[:50]})')

# 环境变量配置验证
print('\n🔐 环境变量配置:')
try:
    from src.core.config.env_config import get_config
    config = get_config()
    email_config = config.email_config
    
    if email_config['from_email']:
        print(f'   ✅ 发件人: {email_config["from_email"]}')
    if email_config['to_email']:
        print(f'   ✅ 收件人: {email_config["to_email"]}')
    if email_config['auth_code']:
        print(f'   ✅ 授权码: {"*"*20}')
except Exception as e:
    print(f'   ❌ 配置加载失败: {e}')

# 检查模型文件
print('\n🤖 模型文件检查:')
model_dir = Path('models')
if model_dir.exists():
    model_files = list(model_dir.glob('*.pkl'))
    print(f'   📁 模型目录存在')
    print(f'   📊 找到 {len(model_files)} 个模型文件')
else:
    print(f'   ⚠️  模型目录不存在')

# 检查数据文件
print('\n📊 数据文件检查:')
data_dir = Path('data')
if data_dir.exists():
    data_files = list(data_dir.rglob('*.csv')) + list(data_dir.rglob('*.txt'))
    print(f'   📁 数据目录存在')
    print(f'   📊 找到 {len(data_files)} 个数据文件')
else:
    print(f'   ⚠️  数据目录不存在')

# 检查日志目录
print('\n📝 日志目录检查:')
log_dir = Path('logs')
if log_dir.exists():
    print(f'   ✅ 日志目录存在')
else:
    print(f'   ℹ️  日志目录不存在 (首次运行时会自动创建)')

print('\n'+'='*70)
print('✅ 健康检查完成')
print('='*70)
