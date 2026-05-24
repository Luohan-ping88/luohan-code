#!/usr/bin/env python3
"""环境变量配置测试脚本"""

from src.core.config.env_config import get_config
from src.app.email_sender import EmailSender

print('='*70)
print('🔧 环境变量配置验证')
print('='*70)

# 1. 加载配置
config = get_config()
print('\n✅ 配置加载成功')
print(config.summary())

# 2. 验证邮件配置
print('\n📧 邮件配置验证:')
valid, errors = config.validate_email_config()
if valid:
    print('✅ 邮件配置完整')
else:
    print('⚠️ 邮件配置有问题:')
    for error in errors:
        print(f'   - {error}')

# 3. 验证 EmailSender
print('\n📤 邮件发送器测试:')
try:
    sender = EmailSender()
    print('✅ EmailSender 初始化成功')
except Exception as e:
    print(f'❌ EmailSender 初始化失败: {e}')

print('\n'+'='*70)
print('🎉 环境变量配置验证完成！')
print('='*70)
