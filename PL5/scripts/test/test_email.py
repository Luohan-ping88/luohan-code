"""
邮件发送测试脚本
"""
import sys
sys.path.insert(0, '.')

from app.email_sender import EmailSender
from datetime import datetime

print('='*70)
print('邮件发送测试')
print('='*70)
print()

# 测试邮件发送
sender_email = "lhp871096134@qq.com"
auth_code = "evquqvnmvnzyecdi"
recipient_email = "lhp871096134@qq.com"

print(f'发件人: {sender_email}')
print(f'收件人: {recipient_email}')
print()

# 创建简单的测试邮件
html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>邮件测试</title>
</head>
<body style="font-family: Arial, sans-serif; padding: 20px;">
    <h2>排列五系统邮件测试</h2>
    <p>这是一封测试邮件。</p>
    <p>发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>如果收到此邮件，说明邮件配置正确。</p>
</body>
</html>"""

try:
    print('正在连接SMTP服务器...')
    sender = EmailSender(
        sender_email=sender_email,
        auth_code=auth_code
    )
    
    print('正在发送邮件...')
    result = sender.send_report(
        recipient_email=recipient_email,
        subject="排列五系统邮件测试 - " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        html_content=html_content
    )
    
    if result:
        print()
        print('✓ 邮件发送成功!')
        print(f'  收件人: {recipient_email}')
        print(f'  发送时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    else:
        print()
        print('✗ 邮件发送失败')
        
except Exception as e:
    print()
    print(f'✗ 邮件发送异常: {e}')
    import traceback
    traceback.print_exc()

print()
print('='*70)
print('测试完成')
print('='*70)
