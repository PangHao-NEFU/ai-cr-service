# AI Code Review Monorepo

基于 OpenAI API 的 AI 代码评审系统。当 GitLab Merge Request 创建或更新时，自动触发 AI 对代码进行评审，并将结果以评论形式发布到 GitLab MR。

## 核心技术栈

- **后端框架**: Python 3.11+ / FastAPI
- **包管理**: uv
- **AI 服务**: OpenAI API (支持兼容 OpenAI 接口的自定义服务)
- **GitLab 交互**: python-gitlab
- **缓存**: Redis
- **部署**: Docker / Docker Compose

## 项目结构

```
ai-cr-monorepo/
├── README.md
├── ai-cr-service/                          # 后端服务
│   ├── pyproject.toml                      # uv 项目配置
│   ├── Dockerfile                          # Docker 构建文件
│   ├── docker-compose.yml                  # Docker Compose 配置
│   ├── .env.example                        # 环境变量示例
│   ├── .gitignore
│   ├── src/
│   │   └── ai_cr_service/
│   │       ├── __init__.py
│   │       ├── main.py                     # FastAPI 应用入口
│   │       ├── config.py                   # 配置管理 (pydantic-settings)
│   │       ├── models/
│   │       │   ├── __init__.py
│   │       │   └── schemas.py              # Pydantic 数据模型
│   │       ├── services/
│   │       │   ├── __init__.py
│   │       │   ├── gitlab_service.py       # GitLab API 交互服务
│   │       │   ├── ai_service.py           # AI 评审服务 (OpenAI API)
│   │       │   └── cr_service.py           # 核心评审编排服务
│   │       └── routers/
│   │           ├── __init__.py
│   │           └── cr.py                   # API 路由定义
│   └── tests/
│       ├── __init__.py
│       └── test_main.py                    # 单元测试
│
└── test-prj/                               # 测试项目 (用于触发 MR)
    ├── .gitlab-ci.yml                      # GitLab CI 配置示例
    ├── main.js                             # 示例代码
    └── README.md
```

## 核心模块说明

### 1. config.py - 配置管理
使用 `pydantic-settings` 从环境变量加载配置，支持：
- GitLab 连接配置
- OpenAI API 配置（支持自定义 base_url）
- Redis 缓存配置
- 评审规则配置（忽略文件、扩展名等）

### 2. schemas.py - 数据模型
- `MRTriggerRequest`: MR 触发请求模型
- `CRIssue`: 代码问题模型（分为 `bug` 和 `suggestion` 两类）
- `AICRResult`: AI 评审结果模型
- `GitLabDiffFile`: GitLab diff 文件模型

### 3. gitlab_service.py - GitLab 服务
- 获取 MR 变更文件列表
- 创建 MR 整体评论
- 创建 MR 行级讨论（Discussion）
- 支持忽略指定文件模式

### 4. ai_service.py - AI 评审服务
- 构建结构化评审 Prompt
- 调用 OpenAI API 进行代码分析
- 解析 JSON 格式的评审结果
- 支持自定义代码规范

### 5. cr_service.py - 核心编排服务
- 编排整个评审流程
- Redis 缓存评审结果（避免重复调用 API）
- 发布评论到 GitLab MR

---

## 快速开始

### 前置要求

- Python 3.11+
- uv (Python 包管理器)
- Redis (可选，用于缓存)
- GitLab 实例 + Access Token
- OpenAI API Key

### 1. 配置环境变量

```bash
cd ai-cr-service
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 服务配置
APP_NAME=AI Code Review Service
DEBUG=false
HOST=0.0.0.0
PORT=8000

# GitLab 配置
GITLAB_URL=https://gitlab.example.com
GITLAB_PRIVATE_TOKEN=your_gitlab_private_token
GITLAB_VERIFY_SSL=true

# OpenAI API 配置
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxxxx
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# Redis 配置
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# 安全配置
WEBHOOK_SECRET=your_webhook_secret
```

### 2. 启动服务

#### 方式一：Docker Compose（推荐）

```bash
docker-compose up -d
```

服务将在 `http://localhost:8000` 启动。

#### 方式二：本地运行

```bash
# 安装 uv (如果未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖
uv sync

# 运行服务
uv run python -m ai_cr_service.main
```

#### 方式三：直接运行

```bash
# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate
uv pip install -e .

# 运行服务
python -m ai_cr_service.main
```

### 3. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 查看 API 文档
open http://localhost:8000/docs
```

---

## API 接口文档

### 基础信息

- **Base URL**: `http://localhost:8000`
- **Content-Type**: `application/json`

---

### 1. 触发 AI 代码评审

触发完整的代码评审流程，包括获取变更、AI 分析、发布评论到 GitLab。

**请求**

```http
POST /api/cr/trigger
Content-Type: application/json
X-GitLab-Token: your_token (可选)
```

**请求体**

```json
{
  "project_id": 123,
  "mr_iid": 456,
  "commit_sha": "abc123...",
  "source_branch": "feature/new-feature",
  "target_branch": "main"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | int | 是 | GitLab 项目 ID |
| mr_iid | int | 是 | Merge Request IID |
| commit_sha | string | 否 | 提交 SHA |
| source_branch | string | 否 | 源分支名 |
| target_branch | string | 否 | 目标分支名 |

**响应**

```json
{
  "code": 0,
  "msg": "AI Code Review completed",
  "data": {
    "total_issues": 3,
    "issues": [
      {
        "file_path": "src/main.py",
        "line_number": 42,
        "level": "bug",
        "title": "SQL 注入风险",
        "content": "使用参数化查询替代字符串拼接",
        "code_snippet": "sql = f\"SELECT * FROM users WHERE id = {user_input}\""
      }
    ]
  }
}
```

---

### 2. 执行评审（不发布评论）

仅执行 AI 评审，不发布评论到 GitLab。适用于测试或预览。

**请求**

```http
POST /api/cr/review
Content-Type: application/json
```

**请求体**

```json
{
  "project_id": 123,
  "mr_iid": 456
}
```

**响应**

```json
{
  "total_issues": 2,
  "issues": [
    {
      "file_path": "src/auth.py",
      "line_number": 15,
      "level": "bug",
      "title": "硬编码密码",
      "content": "请使用环境变量存储敏感信息",
      "code_snippet": "password = \"hardcoded_secret\""
    },
    {
      "file_path": "src/utils.py",
      "line_number": 30,
      "level": "suggestion",
      "title": "使用列表推导式",
      "content": "可以用列表推导式简化代码",
      "code_snippet": null
    }
  ]
}
```

---

### 3. 预览评审格式

直接提交 diff 内容进行评审，无需连接 GitLab。

**请求**

```http
POST /api/cr/preview
Content-Type: application/json
```

**请求体**

```json
[
  {
    "new_path": "src/main.py",
    "diff": "+def hello():\n+    password = \"secret123\"\n+    return password",
    "new_file": true,
    "renamed_file": false,
    "deleted_file": false
  }
]
```

**响应**

```json
{
  "total_issues": 1,
  "issues": [
    {
      "file_path": "src/main.py",
      "line_number": 2,
      "level": "bug",
      "title": "硬编码敏感信息",
      "content": "密码不应硬编码在代码中，请使用环境变量或密钥管理服务",
      "code_snippet": "password = \"secret123\""
    }
  ]
}
```

---

### 4. 健康检查

检查服务运行状态和依赖连接状态。

**请求**

```http
GET /health
```

**响应**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "llm_connected": true,
  "redis_connected": true
}
```

---

### 5. 服务信息

**请求**

```http
GET /
```

**响应**

```json
{
  "name": "AI Code Review Service",
  "version": "0.1.0",
  "docs": "/docs",
  "health": "/health"
}
```

---

## GitLab CI 集成

在测试项目的 `.gitlab-ci.yml` 中添加以下配置：

```yaml
stages:
  - test

ai_code_review:
  stage: test
  only:
    - merge_requests
    - main
  script:
    - |
      curl -X POST http://ai-cr-service:8000/api/cr/trigger \
        -H "Content-Type: application/json" \
        -H "X-GitLab-Token: $CI_GITLAB_TOKEN" \
        -d '{
          "project_id": "'$CI_PROJECT_ID'",
          "mr_iid": "'$CI_MERGE_REQUEST_IID'",
          "commit_sha": "'$CI_COMMIT_SHA'"
        }'
  timeout: 10m
  allow_failure: true
```

---

## 工作流程

```
┌─────────────────┐
│  开发者创建 MR   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ GitLab CI 触发   │
│ /api/cr/trigger │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 获取 MR 变更文件 │
│ (gitlab_service)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  检查 Redis 缓存 │
└────────┬────────┘
         │ 缓存未命中
         ▼
┌─────────────────┐
│ 调用 OpenAI API │
│   进行代码评审   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 解析 JSON 结果   │
│ 缓存到 Redis    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 发布评论到 GitLab│
│ (整体评论+行级)  │
└─────────────────┘
```

---

## 评审规则

AI 会根据以下维度进行代码评审：

| 级别 | 说明 | 示例 |
|------|------|------|
| **bug** | 必须修复的问题 | SQL 注入、空指针、逻辑错误、安全漏洞 |
| **suggestion** | 建议改进的问题 | 代码风格、命名规范、性能优化、可读性 |

---

## 配置项说明

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `APP_NAME` | string | AI Code Review Service | 服务名称 |
| `DEBUG` | bool | false | 调试模式 |
| `HOST` | string | 0.0.0.0 | 监听地址 |
| `PORT` | int | 8000 | 监听端口 |
| `GITLAB_URL` | string | - | GitLab 实例地址 |
| `GITLAB_PRIVATE_TOKEN` | string | - | GitLab Access Token |
| `GITLAB_VERIFY_SSL` | bool | true | 是否验证 SSL |
| `LLM_PROVIDER` | string | openai | LLM 提供商 |
| `LLM_API_KEY` | string | - | OpenAI API Key |
| `LLM_BASE_URL` | string | - | 自定义 API 地址 |
| `LLM_MODEL` | string | gpt-4o | 使用的模型 |
| `LLM_TEMPERATURE` | float | 0.1 | 生成温度 |
| `LLM_MAX_TOKENS` | int | 4096 | 最大 token 数 |
| `REDIS_URL` | string | redis://localhost:6379/0 | Redis 连接地址 |
| `REDIS_CACHE_TTL` | int | 3600 | 缓存过期时间(秒) |
| `WEBHOOK_SECRET` | string | - | Webhook 验证密钥 |

---

## 开发指南

### 运行测试

```bash
cd ai-cr-service
uv run pytest
```

### 代码格式化

```bash
uv run ruff format .
```

### 本地开发启动

```bash
uv run python -m ai_cr_service.main
```

访问 `http://localhost:8000/docs` 查看交互式 API 文档。
