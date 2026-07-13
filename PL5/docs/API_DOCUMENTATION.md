# PL5 系统 API 文档

## 1. 概述

本文档描述了 PL5 排列五高阶数理分析预测系统的 API 接口，包括接口设计、参数说明、返回值格式等。

## 2. API 接口列表

### 2.1 数据采集接口

#### 2.1.1 获取历史数据
- **接口**: `/api/data/history`
- **方法**: `GET`
- **参数**:
  - `start_date`: 开始日期 (YYYY-MM-DD)
  - `end_date`: 结束日期 (YYYY-MM-DD)
  - `limit`: 限制数量
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": [
      {
        "date": "2026-04-01",
        "number": "12345",
        "id": "2026082"
      }
    ]
  }
  ```

#### 2.1.2 采集最新数据
- **接口**: `/api/data/collect`
- **方法**: `POST`
- **参数**:
  - `force`: 是否强制采集
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "collected": true,
      "count": 1
    }
  }
  ```

### 2.2 特征工程接口

#### 2.2.1 生成特征
- **接口**: `/api/features/generate`
- **方法**: `POST`
- **参数**:
  - `data_id`: 数据ID
  - `feature_set`: 特征集名称
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "features_generated": true,
      "feature_count": 700
    }
  }
  ```

#### 2.2.2 获取特征重要性
- **接口**: `/api/features/importance`
- **方法**: `GET`
- **参数**:
  - `feature_set`: 特征集名称
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": [
      {
        "feature": "feature_1",
        "importance": 0.95
      }
    ]
  }
  ```

### 2.3 模型预测接口

#### 2.3.1 运行预测
- **接口**: `/api/predict/run`
- **方法**: `POST`
- **参数**:
  - `model_name`: 模型名称
  - `feature_set`: 特征集名称
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "prediction": ["12345", "67890", "24680"],
      "confidence": [0.85, 0.75, 0.70]
    }
  }
  ```

#### 2.3.2 获取预测历史
- **接口**: `/api/predict/history`
- **方法**: `GET`
- **参数**:
  - `start_date`: 开始日期 (YYYY-MM-DD)
  - `end_date`: 结束日期 (YYYY-MM-DD)
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": [
      {
        "date": "2026-04-01",
        "prediction": ["12345", "67890"],
        "actual": "13579",
        "accuracy": 0.2
      }
    ]
  }
  ```

### 2.4 工作流接口

#### 2.4.1 创建工作流
- **接口**: `/api/workflow/create`
- **方法**: `POST`
- **参数**:
  - `name`: 工作流名称
  - `tasks`: 任务列表
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "workflow_id": "wf_12345",
      "status": "created"
    }
  }
  ```

#### 2.4.2 运行工作流
- **接口**: `/api/workflow/run`
- **方法**: `POST`
- **参数**:
  - `workflow_id`: 工作流ID
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "workflow_id": "wf_12345",
      "status": "running"
    }
  }
  ```

### 2.5 系统监控接口

#### 2.5.1 获取系统状态
- **接口**: `/api/monitor/status`
- **方法**: `GET`
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "cpu": 45.5,
      "memory": 60.2,
      "disk": 30.1,
      "status": "healthy"
    }
  }
  ```

#### 2.5.2 获取性能指标
- **接口**: `/api/monitor/metrics`
- **方法**: `GET`
- **参数**:
  - `time_range`: 时间范围 (hour/day/week)
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "response_time": 0.25,
      "throughput": 100,
      "error_rate": 0.01
    }
  }
  ```

### 2.6 安全接口

#### 2.6.1 登录
- **接口**: `/api/auth/login`
- **方法**: `POST`
- **参数**:
  - `username`: 用户名
  - `password`: 密码
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "expires_in": 1800
    }
  }
  ```

#### 2.6.2 验证权限
- **接口**: `/api/auth/check`
- **方法**: `GET`
- **参数**:
  - `token`: 认证令牌
- **返回值**:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "valid": true,
      "user": "admin",
      "roles": ["admin"]
    }
  }
  ```

## 3. 错误处理

所有 API 接口的错误返回格式统一为：

```json
{
  "code": 400,
  "message": "错误信息",
  "data": null
}
```

常见错误码：
- `400`: 请求参数错误
- `401`: 未授权
- `403`: 权限不足
- `404`: 资源不存在
- `500`: 服务器内部错误

## 4. 认证机制

系统使用 JWT (JSON Web Token) 进行认证：

1. 客户端通过 `/api/auth/login` 接口获取 token
2. 后续请求在 HTTP 头中携带 token：`Authorization: Bearer <token>`
3. 服务器验证 token 的有效性

## 5. 速率限制

为防止滥用，系统对 API 请求进行速率限制：

- 每个 IP 地址：60 请求/分钟
- 每个用户：100 请求/分钟
- 敏感操作：10 请求/分钟

## 6. 版本控制

API 版本通过 URL 路径进行控制，例如：`/api/v1/data/history`

当前版本：v1

## 7. 最佳实践

1. **使用 HTTPS**: 所有 API 请求应使用 HTTPS 协议
2. **合理缓存**: 对频繁请求的资源进行缓存
3. **错误处理**: 正确处理 API 返回的错误信息
4. **速率控制**: 遵守系统的速率限制
5. **安全传输**: 敏感信息应通过安全方式传输

## 8. 示例代码

### Python 示例

```python
import requests

# 登录获取 token
auth_response = requests.post('http://localhost:8000/api/auth/login', json={
    'username': 'admin',
    'password': 'password'
})
token = auth_response.json()['data']['token']

# 使用 token 调用 API
headers = {'Authorization': f'Bearer {token}'}
response = requests.get('http://localhost:8000/api/data/history', headers=headers, params={
    'start_date': '2026-01-01',
    'end_date': '2026-01-31'
})
print(response.json())
```

### JavaScript 示例

```javascript
// 登录获取 token
fetch('http://localhost:8000/api/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    username: 'admin',
    password: 'password'
  })
})
.then(response => response.json())
.then(data => {
  const token = data.data.token;
  
  // 使用 token 调用 API
  return fetch('http://localhost:8000/api/data/history?start_date=2026-01-01&end_date=2026-01-31', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
})
.then(response => response.json())
.then(data => console.log(data));
```