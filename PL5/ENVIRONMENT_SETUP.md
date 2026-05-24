# 环境变量配置指南

## 概述

PL5 预测系统现已支持使用环境变量配置，替代传统的 JSON 配置文件方式。环境变量配置具有以下优势：

- 更安全：敏感信息不会被提交到版本控制
- 更灵活：支持多环境配置（开发、测试、生产）
- 更便捷：无需修改代码即可切换配置
- 兼容性好：同时支持环境变量和原有 JSON 配置

## 快速开始

### 1. 安装依赖

确保已安装 `python-dotenv`：

```bash
pip install python-dotenv==1.0.0
```

### 2. 创建配置文件

复制项目根目录下的 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

### 3. 编辑配置

打开 `.env` 文件，填入你的实际配置信息：

```env
# 邮件配置
EMAIL_SMTP_SERVER=smtp.qq.com
EMAIL_SMTP_PORT=465
EMAIL_FROM_ADDRESS=your_email@qq.com
EMAIL_TO_ADDRESS=customer_email@example.com
EMAIL_AUTH_CODE=your_authorization_code

# 特征工程配置
ENABLE_CPP_ACCELERATION=true
FEATURE_MODE=v11_advanced
```

### 4. 使用配置

在代码中使用配置管理器：

```python
from src.core.config.env_config import get_config

# 获取全局配置实例
config = get_config()

# 访问邮件配置
email_config = config.email_config
print(f"发件人: {email_config['from_email']}")

# 访问特征工程配置
feature_config = config.feature_config
print(f"C++加速: {feature_config['enable_cpp_acceleration']}")

# 验证配置
valid, errors = config.validate_email_config()
if not valid:
    print("配置错误:", errors)
```

## 配置优先级

配置按以下优先级加载（高优先级覆盖低优先级）：

1. **系统环境变量** - 最高优先级
2. **.env 文件** - 次高优先级
3. **JSON 配置文件** - 向后兼容支持
4. **默认值** - 最低优先级

## 环境变量列表

### 邮件配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `EMAIL_SMTP_SERVER` | SMTP 服务器地址 | `smtp.qq.com` |
| `EMAIL_SMTP_PORT` | SMTP 服务器端口 | `465` |
| `EMAIL_FROM_ADDRESS` | 发件人邮箱 | - |
| `EMAIL_TO_ADDRESS` | 收件人邮箱 | - |
| `EMAIL_AUTH_CODE` | SMTP 授权码 | - |

### 系统配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `LOG_LEVEL` | 日志级别（DEBUG/INFO/WARNING/ERROR） | `INFO` |
| `DATA_DIR` | 数据目录 | `./data` |
| `MODEL_DIR` | 模型目录 | `./models` |
| `LOG_DIR` | 日志目录 | `./logs` |
| `TZ` | 时区 | `Asia/Shanghai` |

### 特征工程配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ENABLE_CPP_ACCELERATION` | 是否启用 C++ 加速 | `true` |
| `FEATURE_MODE` | 特征工程模式（v10/v11_advanced/v11_full） | `v11_advanced` |

### 模型配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `PREDICTOR_TYPE` | 预测器类型 | `ensemble` |

### 调度器配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ENABLE_SCHEDULER` | 是否启用调度器 | `true` |

## 使用示例

### 发送邮件

```python
from src.app.email_sender import EmailSender

# 自动从环境变量读取配置
sender = EmailSender()

# 发送邮件
sender.send_report(
    recipient_email="recipient@example.com",
    subject="测试邮件",
    html_content="<h1>Hello World!</h1>"
)
```

### 运行发送报告脚本

```bash
python scripts/send_training_report_to_customer.py
```

### 使用系统环境变量（不使用 .env 文件）

```bash
# Linux/Mac
export EMAIL_FROM_ADDRESS="your_email@qq.com"
export EMAIL_AUTH_CODE="your_auth_code"
python your_script.py

# Windows (PowerShell)
$env:EMAIL_FROM_ADDRESS="your_email@qq.com"
$env:EMAIL_AUTH_CODE="your_auth_code"
python your_script.py
```

## 安全注意事项

1. **永远不要**将 `.env` 文件提交到版本控制
2. 使用强密码和授权码
3. 定期更换授权码
4. 限制 `.env` 文件的访问权限：`chmod 600 .env`

## 故障排除

### 配置未生效？

- 确认 `.env` 文件在项目根目录
- 确认环境变量名称拼写正确
- 检查 `python-dotenv` 是否已安装
- 重启 Python 进程以加载新配置

### 邮件发送失败？

- 验证邮件配置完整性：`config.validate_email_config()`
- 确认授权码正确（不是邮箱密码）
- 检查网络连接和防火墙设置

## 向后兼容

系统仍支持原有的 JSON 配置文件方式：
- `config/email_config.json` - 邮件配置
- `config/config.json` - 系统配置

当环境变量未设置时，系统会自动回退到 JSON 配置文件。

## 迁移指南

从 JSON 配置迁移到环境变量：

1. 将 `config/email_config.json` 中的配置值复制到 `.env` 文件
2. 验证配置能正确加载
3. （可选）删除或备份旧的 JSON 配置文件

## 更多信息

- 查看 `.env.example` 获取完整的配置模板
- 查看 `EMAIL_CONFIG_GUIDE.md` 获取邮件配置详细说明
