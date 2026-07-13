# PL5 部署和CI/CD流程文档

## 1. 部署流程概述

PL5 项目采用自动化部署流程，确保部署过程的可靠性和一致性。部署流程包括以下步骤：

1. **环境检查**：检查Python环境、依赖文件等
2. **依赖安装**：安装项目所需的Python依赖
3. **Docker构建**：构建Docker镜像（如果Docker可用）
4. **测试运行**：运行项目测试，确保功能正常
5. **系统状态检查**：检查系统组件状态
6. **服务启动**：启动API服务
7. **健康检查**：检查服务是否正常运行

## 2. 环境要求

### 2.1 系统要求

- **操作系统**：Linux、macOS、Windows
- **Python版本**：Python 3.12+
- **Docker**：可选，用于容器化部署

### 2.2 依赖要求

项目依赖项在 `requirements.txt` 文件中定义，包括：

- **核心依赖**：fastapi、uvicorn
- **模型依赖**：openai、llama-cpp-python
- **工具依赖**：python-dotenv
- **测试依赖**：pytest、pytest-asyncio
- **开发依赖**：black、flake8

## 3. 自动化部署脚本

### 3.1 部署脚本

项目提供了两个部署脚本：

- **`scripts/deploy/deploy.sh`**：用于Linux/Unix系统
- **`scripts/deploy/deploy.bat`**：用于Windows系统

### 3.2 运行部署脚本

#### Linux/Unix系统

```bash
# 给脚本添加执行权限
chmod +x scripts/deploy/deploy.sh

# 运行部署脚本
./scripts/deploy/deploy.sh
```

#### Windows系统

```batch
# 运行部署脚本
scripts\deploy\deploy.bat
```

### 3.3 部署脚本功能

部署脚本执行以下操作：

1. **环境检查**：检查Python环境、pip是否安装
2. **依赖安装**：安装项目依赖
3. **Docker构建**：构建Docker镜像（如果Docker可用）
4. **测试运行**：运行项目测试
5. **系统状态检查**：检查系统组件状态
6. **服务启动**：启动API服务
7. **健康检查**：检查服务是否正常运行

## 4. CI/CD流程

### 4.1 GitHub Actions配置

项目使用GitHub Actions实现CI/CD流程，配置文件为 `.github/workflows/ci-cd.yml`。

### 4.2 CI/CD流程步骤

1. **代码检查**：运行flake8进行代码风格检查
2. **测试运行**：运行pytest进行测试
3. **构建**：构建Docker镜像
4. **部署**：根据分支部署到不同环境
   - `main` 分支：部署到生产环境
   - `develop` 分支：部署到测试环境
5. **部署检查**：检查部署状态
6. **性能测试**：运行性能测试

### 4.3 触发条件

CI/CD流程在以下情况下触发：

- **推送代码**：推送到 `main` 或 `develop` 分支
- **拉取请求**：针对 `main` 或 `develop` 分支的拉取请求
- **定时执行**：每天执行一次

## 5. 环境变量和密钥管理

### 5.1 环境变量配置

项目使用 `.env` 文件管理环境变量，模板文件为 `.env.example`。

#### 主要环境变量

- **`OPENAI_API_KEY`**：OpenAI API密钥
- **`OPENAI_BASE_URL`**：OpenAI API基础URL
- **`API_HOST`**：API服务主机
- **`API_PORT`**：API服务端口
- **`LOG_LEVEL`**：日志级别

### 5.2 密钥管理

项目提供了密钥管理脚本 `scripts/deploy/secrets_manager.py`，用于安全地管理敏感信息。

#### 密钥管理脚本功能

- **生成密钥**：生成加密密钥
- **加密环境变量**：加密 `.env` 文件
- **解密环境变量**：解密加密的环境变量文件
- **备份密钥**：备份密钥和加密的环境变量

#### 使用方法

```bash
# 生成密钥
python scripts/deploy/secrets_manager.py generate

# 加密环境变量
python scripts/deploy/secrets_manager.py encrypt

# 解密环境变量
python scripts/deploy/secrets_manager.py decrypt

# 备份密钥
python scripts/deploy/secrets_manager.py backup
```

## 6. 部署测试

### 6.1 部署测试脚本

项目提供了部署测试脚本 `scripts/deploy/test_deployment.py`，用于测试部署流程的完整性。

### 6.2 运行部署测试

```bash
# 运行部署测试
python scripts/deploy/test_deployment.py
```

### 6.3 测试内容

部署测试脚本测试以下内容：

1. **环境测试**：检查Python环境、依赖安装状态、配置文件存在性
2. **服务启动测试**：检查API服务是否成功启动
3. **API接口测试**：检查API接口是否正常响应
4. **核心功能测试**：检查系统核心功能是否正常
5. **性能测试**：测试API响应时间

## 7. 手动部署步骤

### 7.1 本地部署

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python start_api.py
```

### 7.2 Docker部署

```bash
# 构建镜像
docker build -t pl5-system .

# 运行容器
docker run -d -p 8000:8000 --name pl5-system pl5-system
```

### 7.3 Docker Compose部署

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 8. 生产环境部署

### 8.1 配置反向代理

使用Nginx或Apache作为反向代理，配置示例：

```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 8.2 设置HTTPS

配置SSL证书，使用Let's Encrypt等服务获取免费证书。

### 8.3 配置监控

添加Prometheus和Grafana监控，监控系统运行状态。

### 8.4 设置自动重启

使用systemd或supervisor管理服务，确保服务在崩溃后自动重启。

## 9. 部署故障排查

### 9.1 常见问题

1. **依赖安装失败**：检查网络连接，确保pip版本最新
2. **服务启动失败**：检查端口是否被占用，查看日志文件
3. **API接口响应异常**：检查服务状态，查看日志文件
4. **Docker构建失败**：检查Docker环境，确保Dockerfile正确

### 9.2 日志文件

项目日志文件位于 `logs` 目录，包括：

- **`deploy.log`**：部署日志
- **`deployment_test.log`**：部署测试日志
- **`pl5.log`**：系统运行日志

### 9.3 健康检查

API服务提供了健康检查端点：

```
GET /api/health
```

响应示例：

```json
{
  "status": "healthy",
  "service": "AI工具系统API"
}
```

## 10. 版本管理和发布流程

### 10.1 版本管理

使用语义化版本号：

- **主版本**：不兼容的API变更
- **次版本**：向后兼容的功能添加
- **补丁版本**：向后兼容的bug修复

### 10.2 发布流程

1. **更新版本号**：更新项目版本号
2. **运行测试**：运行项目测试
3. **构建Docker镜像**：构建Docker镜像
4. **推送镜像**：推送镜像到仓库
5. **部署到生产环境**：部署到生产环境

## 11. 总结

PL5 项目采用自动化部署流程和CI/CD流程，确保部署过程的可靠性和一致性。通过自动化部署脚本和GitHub Actions，实现了从代码提交到部署的全流程自动化，提高了部署效率和可靠性。

同时，项目提供了完善的环境变量和密钥管理机制，确保敏感信息的安全。部署测试脚本和健康检查端点，保证了部署的完整性和服务的可用性。

通过本文档的指导，您可以轻松地部署和管理PL5项目，确保系统的稳定运行。
