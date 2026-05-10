#!/usr/bin/env python3

"""
PL5 密钥管理脚本
用于安全地管理敏感信息
"""

import os
import sys
import json
import base64
from cryptography.fernet import Fernet
from datetime import datetime

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# 密钥文件
KEY_FILE = os.path.join(PROJECT_ROOT, '.secrets', 'key.key')

# 加密的环境变量文件
ENCRYPTED_ENV_FILE = os.path.join(PROJECT_ROOT, '.secrets', 'env.encrypted')

# 确保密钥目录存在
os.makedirs(os.path.join(PROJECT_ROOT, '.secrets'), exist_ok=True)

def generate_key():
    """生成密钥"""
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
    print(f"密钥已生成并保存到 {KEY_FILE}")
    return key

def load_key():
    """加载密钥"""
    if not os.path.exists(KEY_FILE):
        return generate_key()
    with open(KEY_FILE, 'rb') as f:
        return f.read()

def encrypt_env():
    """加密环境变量文件"""
    key = load_key()
    fernet = Fernet(key)
    
    # 读取.env文件
    env_file = os.path.join(PROJECT_ROOT, '.env')
    if not os.path.exists(env_file):
        print(f"错误: {env_file} 不存在")
        return False
    
    with open(env_file, 'rb') as f:
        env_content = f.read()
    
    # 加密内容
    encrypted_content = fernet.encrypt(env_content)
    
    # 保存加密文件
    with open(ENCRYPTED_ENV_FILE, 'wb') as f:
        f.write(encrypted_content)
    
    print(f"环境变量已加密并保存到 {ENCRYPTED_ENV_FILE}")
    return True

def decrypt_env():
    """解密环境变量文件"""
    key = load_key()
    fernet = Fernet(key)
    
    # 读取加密文件
    if not os.path.exists(ENCRYPTED_ENV_FILE):
        print(f"错误: {ENCRYPTED_ENV_FILE} 不存在")
        return False
    
    with open(ENCRYPTED_ENV_FILE, 'rb') as f:
        encrypted_content = f.read()
    
    # 解密内容
    decrypted_content = fernet.decrypt(encrypted_content)
    
    # 保存到.env文件
    env_file = os.path.join(PROJECT_ROOT, '.env')
    with open(env_file, 'wb') as f:
        f.write(decrypted_content)
    
    print(f"环境变量已解密并保存到 {env_file}")
    return True

def backup_secrets():
    """备份密钥和加密的环境变量"""
    backup_dir = os.path.join(PROJECT_ROOT, '.secrets', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # 备份密钥
    if os.path.exists(KEY_FILE):
        backup_key_file = os.path.join(backup_dir, f'key.key.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        with open(KEY_FILE, 'rb') as src, open(backup_key_file, 'wb') as dst:
            dst.write(src.read())
        print(f"密钥已备份到 {backup_key_file}")
    
    # 备份加密的环境变量
    if os.path.exists(ENCRYPTED_ENV_FILE):
        backup_env_file = os.path.join(backup_dir, f'env.encrypted.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        with open(ENCRYPTED_ENV_FILE, 'rb') as src, open(backup_env_file, 'wb') as dst:
            dst.write(src.read())
        print(f"加密的环境变量已备份到 {backup_env_file}")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python secrets_manager.py [encrypt|decrypt|backup|generate]")
        return 1
    
    command = sys.argv[1]
    
    if command == 'encrypt':
        encrypt_env()
    elif command == 'decrypt':
        decrypt_env()
    elif command == 'backup':
        backup_secrets()
    elif command == 'generate':
        generate_key()
    else:
        print(f"错误: 未知命令 {command}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
