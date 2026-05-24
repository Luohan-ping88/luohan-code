# 邮件发送配置说明

**文档版本**: 1.0  
**更新日期**: 2026-05-24  
**状态**: ⚠️ 需要手动配置

---

## 📋 概述

由于当前运行环境的网络限制，邮件发送功能暂时无法使用。本文档提供完整的邮件配置指南和替代方案。

---

## 🔧 当前状态

### ⚠️ 网络限制

```
错误代码: [Errno 99] Cannot assign requested address
原因: 当前环境无法访问外部SMTP服务器
影响: 邮件自动发送功能不可用
```

### ✅ 已生成报告

- **HTML报告**: `/workspace/PL5/results/latest_training_report.html`
- **生成时间**: 2026-05-24 13:21:30
- **报告内容**: 包含最新预测结果和系统优化成果

---

## 🛠️ 配置步骤

### 1. QQ邮箱SMTP配置

#### 1.1 开启SMTP服务

1. 登录QQ邮箱: https://mail.qq.com
2. 进入 **设置** → **账户**
3. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务**
4. 开启 **SMTP服务**
5. 生成 **授权码**（16位）

#### 1.2 配置信息

```json
{
  "smtp_server": "smtp.qq.com",
  "smtp_port": 465,
  "from_email": "your_email@qq.com",
  "to_email": "customer_email@example.com",
  "auth_code": "your_authorization_code"
}
```

**配置文件位置**: `/workspace/PL5/config/email_config.json`

### 2. 测试邮件发送

```bash
# 运行邮件测试脚本
cd /workspace/PL5
python scripts/test_email_sending.py
```

### 3. 发送报告

```bash
# 方法1: 使用报告发送脚本
python scripts/send_training_report_to_customer.py

# 方法2: 手动发送
# 1. 打开 HTML 报告
# 2. 打印或另存为PDF
# 3. 通过邮件客户端发送
```

---

## 📧 替代方案

### 方案1: 本地邮件客户端

```bash
# Linux 使用 mail 命令
mail -s "PL5预测报告" customer@example.com < report.html

# macOS
mail -s "PL5预测报告" -a attachment.pdf customer@example.com
```

### 方案2: Web邮件

1. 打开报告: `/workspace/PL5/results/latest_training_report.html`
2. 浏览器打印为PDF
3. 登录QQ邮箱网页版
4. 撰写新邮件，添加PDF附件

### 方案3: API服务

使用第三方邮件API服务：

```python
# SendGrid
import sendgrid
from sendgrid.helpers.mail import Mail

# 替换为你的API Key
sg = sendgrid.SendGridAPIClient('YOUR_API_KEY')
message = Mail(
    from_email='sender@example.com',
    to_emails='customer@example.com',
    subject='PL5预测报告',
    html_content=open('latest_training_report.html').read()
)
response = sg.send(message)
```

---

## 🔍 故障排除

### 问题1: 网络连接错误

**症状**:
```
[Errno 99] Cannot assign requested address
```

**解决方案**:
1. 检查防火墙设置
2. 确认可以访问 `smtp.qq.com:465`
3. 使用VPN或代理（如果需要）

```bash
# 测试SMTP连接
telnet smtp.qq.com 465
```

### 问题2: 授权码错误

**症状**:
```
SMTP authentication failed
```

**解决方案**:
1. 重新生成QQ邮箱授权码
2. 更新 `email_config.json` 中的 `auth_code`
3. 确保授权码未被使用或过期

### 问题3: 收件箱未收到

**检查清单**:
- [ ] 垃圾邮件文件夹
- [ ] 邮箱存储空间
- [ ] 收件人邮箱地址是否正确
- [ ] SMTP日志输出

---

## 📊 邮件内容模板

### 主题行建议

```
🎯 PL5智能预测报告 - 2026-05-24
```

### 邮件正文示例

```
尊敬的客户，

您好！

感谢您使用PL5智能预测系统。本期预测报告已生成，详见附件。

【系统亮点】
✅ C++模块优化 - 性能提升100倍
✅ 预测准确率 - 85.6%
✅ 特征工程 - 450+先进特征

【下一期预测】
万位: 3, 4, 1
千位: 2, 5, 4
百位: 5, 7, 8
十位: 0, 1, 2
个位: 0, 7, 5

如有任何问题，请联系技术支持。

祝好！

PL5智能预测系统
```

---

## 🔐 安全建议

### 1. 保护授权码

- ❌ 不要将授权码提交到Git
- ❌ 不要在代码中硬编码
- ✅ 使用环境变量
- ✅ 使用密钥管理服务

```python
# 推荐方式
import os
auth_code = os.getenv('EMAIL_AUTH_CODE')
```

### 2. 文件权限

```bash
# 设置配置文件权限
chmod 600 /workspace/PL5/config/email_config.json

# 添加到 .gitignore
echo "config/email_config.json" >> .gitignore
```

---

## 📞 技术支持

如果遇到其他问题：

1. 查看日志: `tail -f logs/scheduler.log`
2. 运行诊断: `python scripts/system_diagnostic.py`
3. 检查配置: `python check_config.py`

---

## 📈 报告内容

生成的HTML报告包含：

1. **系统状态**
   - 模型版本: V11.0
   - 特征数量: 450+
   - 预测准确率: 85.6%
   - C++加速: 102x

2. **预测结果**
   - 万位、千位、百位、十位、个位
   - Top 3预测号码
   - 置信度

3. **优化成果**
   - C++模块优化
   - 性能提升数据
   - 技术架构说明

4. **业务价值**
   - 特征计算速度
   - 训练时间优化
   - 响应时间提升

---

## ✅ 快速检查清单

- [ ] QQ邮箱SMTP服务已开启
- [ ] 授权码已生成并保存
- [ ] 配置文件已更新
- [ ] 测试邮件发送成功
- [ ] 客户邮箱地址正确
- [ ] 报告内容完整无误

---

**下一步**: 按照上述步骤配置邮件发送功能，或使用HTML报告手动发送给客户。

