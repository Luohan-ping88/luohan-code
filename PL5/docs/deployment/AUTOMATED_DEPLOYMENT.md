# PL5 自动化部署文档

## 概述

本文档描述了PL5排列五预测系统的自动化部署流程，包括环境准备、部署脚本使用、CI/CD配置和回滚机制。

## 部署流程

部署流程包含以下7个步骤：

```
1. 环境检查 (Python版本、磁盘空间、网络连接)
2. 依赖安装 (pip install -r requirements.txt)
3. 配置初始化 (创建配置文件、设置环境变量)
4. 代码部署 (复制代码、设置权限)
5. 数据库/数据准备 (初始化数据目录)
6. 验证测试 (运行冒烟测试)
7. 启动服务
```

## 部署脚本

所有部署脚本位于 `scripts/deploy/` 目录下。

### 主部署脚本

**文件**: `scripts/deploy/deploy.py`

一键部署脚本，自动执行完整的部署流程。

#### 使用方法

```bash
# 完整部署
python scripts/deploy/deploy.py

# 部署到测试环境
python scripts/deploy/deploy.py -e staging

# 跳过某些步骤
python scripts/deploy/deploy.py -s backup,start_service

# 试运行（不实际执行）
python scripts/deploy/deploy.py --dry-run

# 显示帮助
python scripts/deploy/deploy.py -h
```

#### 可用步骤

- `environment_check` - 环境检查
- `install_dependencies` - 安装依赖
- `init_config` - 初始化配置
- `prepare_data` - 准备数据
- `verify_deployment` - 验证部署
- `start_service` - 启动服务
- `backup` - 创建备份

### 子脚本

#### 1. 环境检查脚本

**文件**: `scripts/deploy/check_environment.py`

检查部署环境是否满足要求。

```bash
# 运行环境检查
python scripts/deploy/check_environment.py

# 输出JSON格式结果
python scripts/deploy/check_environment.py --json
```

**检查项**:
- Python版本 (>= 3.10)
- 磁盘空间 (>= 5GB)
- 内存 (>= 4GB)
- 网络连接
- 端口占用情况
- pip可用性
- Git可用性
- 项目结构完整性
- 文件权限

#### 2. 依赖安装脚本

**文件**: `scripts/deploy/install_dependencies.py`

安装项目所需的所有依赖。

```bash
# 安装依赖
python scripts/deploy/install_dependencies.py

# 输出JSON格式结果
python scripts/deploy/install_dependencies.py --json

# 跳过虚拟环境创建
python scripts/deploy/install_dependencies.py --no-venv
```

**功能**:
- 升级pip
- 安装requirements.txt中的依赖
- 安装Windows特定依赖（pywin32, wmi）
- 安装可选依赖（psutil, cryptography等）
- 验证安装

#### 3. 配置初始化脚本

**文件**: `scripts/deploy/init_config.py`

创建和初始化配置文件。

```bash
# 初始化配置
python scripts/deploy/init_config.py

# 输出JSON格式结果
python scripts/deploy/init_config.py --json
```

**功能**:
- 创建必要的目录结构
- 初始化配置文件（config.json, model_config.yaml等）
- 创建.env文件
- 验证配置
- 设置文件权限

#### 4. 部署前检查脚本

**文件**: `scripts/deploy/pre_deploy_check.py`

在实际部署前进行全面检查。

```bash
# 运行部署前检查
python scripts/deploy/pre_deploy_check.py

# 指定环境
python scripts/deploy/pre_deploy_check.py --env=production

# 输出JSON格式结果
python scripts/deploy/pre_deploy_check.py --json
```

**检查项**:
- 代码质量
- 依赖完整性
- 配置有效性
- 数据文件
- 数据库连接
- 外部服务
- 安全性
- 备份状态
- 系统资源

#### 5. 部署后验证脚本

**文件**: `scripts/deploy/post_deploy_verify.py`

验证部署是否成功。

```bash
# 运行部署后验证
python scripts/deploy/post_deploy_verify.py

# 指定环境
python scripts/deploy/post_deploy_verify.py --env=production

# 输出JSON格式结果
python scripts/deploy/post_deploy_verify.py --json
```

**验证项**:
- 服务运行状态
- 健康检查端点
- API端点
- 响应时间
- 核心功能
- 数据访问
- 配置加载
- 日志记录
- 进程状态

#### 6. 回滚脚本

**文件**: `scripts/deploy/rollback.py`

在部署失败时恢复到之前的版本。

```bash
# 创建备份
python scripts/deploy/rollback.py create

# 创建指定名称的备份
python scripts/deploy/rollback.py create my_backup

# 列出所有备份
python scripts/deploy/rollback.py list

# 恢复最新备份
python scripts/deploy/rollback.py restore

# 恢复指定备份
python scripts/deploy/rollback.py restore backup_20240101_120000

# 清理旧备份（保留最近10个）
python scripts/deploy/rollback.py cleanup

# 清理旧备份（保留最近5个）
python scripts/deploy/rollback.py cleanup 5

# 自动回滚
python scripts/deploy/rollback.py auto
```

## CI/CD 配置

### GitHub Actions 工作流

**文件**: `.github/workflows/ci-cd.yml`

包含以下任务：

1. **代码质量检查** - 运行flake8、black、isort、bandit
2. **单元测试** - 在多个Python版本和操作系统上运行
3. **集成测试** - 运行集成测试套件
4. **端到端测试** - 运行E2E测试
5. **构建** - 构建Python包和Docker镜像
6. **部署到测试环境** - 自动部署到staging
7. **部署到生产环境** - 手动触发部署到production
8. **性能测试** - 运行性能测试
9. **生成测试报告** - 生成Allure报告

### 触发条件

- **Push到main/develop分支** - 运行完整CI/CD流程
- **Pull Request** - 运行测试和代码检查
- **定时任务** - 每天UTC 00:00运行
- **手动触发** - 支持workflow_dispatch手动触发

### 环境变量

需要在GitHub Secrets中配置：

- `SLACK_WEBHOOK_URL` - Slack通知Webhook
- `GITHUB_TOKEN` - GitHub自动提供

## Windows 部署

### PowerShell 部署

```powershell
# 进入项目目录
cd e:\PL5

# 运行部署脚本
python scripts\deploy\deploy.py

# 或者使用批处理文件
scripts\deploy\deploy.bat
```

### CMD 部署

```cmd
# 进入项目目录
cd e:\PL5

# 运行部署脚本
python scripts\deploy\deploy.py

# 或者使用批处理文件
scripts\deploy\deploy.bat
```

## 部署后验证

部署完成后，可以通过以下方式验证：

1. **健康检查**
   ```bash
   curl http://localhost:8000/api/health
   ```

2. **系统状态**
   ```bash
   curl http://localhost:8000/api/status
   ```

3. **查看日志**
   ```bash
   # 查看部署日志
   type logs\deploy.log

   # 查看系统日志
   type logs\system.log
   ```

4. **查看部署报告**
   ```bash
   # 查看最新的部署报告
   dir logs\deploy_report_*.json /b /o-d
   ```

## 故障排除

### 常见问题

#### 1. Python版本过低

**错误**: `Python版本过低: 3.9，需要 >= 3.10`

**解决**: 升级Python到3.10或更高版本

#### 2. 端口被占用

**错误**: `端口8000已被占用`

**解决**:
```bash
# 查找占用端口的进程
netstat -ano | findstr :8000

# 停止进程
taskkill /PID <PID> /F
```

#### 3. 依赖安装失败

**错误**: `依赖安装失败`

**解决**:
```bash
# 升级pip
python -m pip install --upgrade pip

# 单独安装失败的包
pip install <package_name>
```

#### 4. 配置文件缺失

**错误**: `config.json 不存在`

**解决**:
```bash
# 运行配置初始化
python scripts\deploy\init_config.py
```

### 日志文件

部署过程中会生成以下日志文件：

- `logs/deploy.log` - 部署日志
- `logs/system.log` - 系统日志
- `logs/deploy_report_*.json` - 部署报告
- `logs/deploy_verify_*.json` - 部署验证报告

### 回滚

如果部署失败，可以执行回滚：

```bash
# 自动回滚到最新备份
python scripts\deploy\rollback.py auto

# 或者手动回滚
python scripts\deploy\rollback.py restore
```

## 安全注意事项

1. **敏感信息** - 不要将.env文件提交到版本控制
2. **备份** - 部署前自动创建备份
3. **权限** - 确保配置文件权限正确
4. **网络** - 生产环境限制外部访问

## 维护

### 定期任务

- **清理旧备份** - 每月运行一次 `rollback.py cleanup`
- **更新依赖** - 每季度检查并更新依赖
- **性能测试** - 每月运行一次性能测试

### 监控

- 检查日志文件大小
- 监控磁盘空间
- 监控系统资源使用

## 联系支持

如有问题，请查看：

1. 部署日志: `logs/deploy.log`
2. 系统日志: `logs/system.log`
3. 部署报告: `logs/deploy_report_*.json`

---

**文档版本**: 1.0  
**最后更新**: 2026-04-06
