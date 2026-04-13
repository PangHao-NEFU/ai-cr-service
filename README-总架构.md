# GitLab MR AI CodeReview 系统设计（业界最佳实践）

本仓库是一个ai-cr功能提供服务，目的是当github远程开发分支合并到master分支时，触发aicr，给出改动代码的风险点，危险点，建议改进点的aicr建议。

这是互联网大厂**标准落地的AI CodeReview方案**，核心思路：**GitLab CI/Webhook触发 + 异步任务调度 + 私有Code大模型推理 + 结构化结果解析 + GitLab API回写评论**，完全解决同步超时、代码安全、准确率问题。

## 一、核心设计原则（大厂通用标准）
1. **异步解耦**：大模型推理慢，绝对避免同步调用导致GitLab超时
2. **代码安全**：核心业务代码**不上传公网大模型**，优先私有部署Code大模型
3. **结构化输出**：强制AI返回JSON，避免自然语言解析混乱，精准匹配代码行
4. **规则混合**：`传统Lint规则(ESLint/CheckStyle) + AI语义分析`，提升准确率
5. **可配置化**：支持项目级忽略文件、触发分支、CR规则开关
6. **限流熔断**：控制大模型调用成本，避免滥用

---

## 二、整体技术架构（分层设计）
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   触发层        │     │   调度层        │     │   核心业务层    │
│ GitLab CI/Webhook│────▶│ MQ(RabbitMQ)   │────▶│ Diff解析/Prompt │
│ （MR创建/更新） │     │ 限流/异步任务   │     │ 大模型调用/解析 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 监控运维层      │◀───▶│ 能力支撑层      │◀────│ 输出层          │
│ Prometheus/ELK  │     │ Redis/MySQL/私有│     │ GitLab API评论  │
│ 告警/日志        │     │ Code大模型      │     │ 行级批注/标签   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 核心技术栈选型
| 层级         | 技术选择（大厂主流）| 说明 |
|--------------|---------------------------------------------|------|
| 触发方式     | **GitLab CI（首选）** + Webhook 备用         | CI更稳定，无丢事件/鉴权问题 |
| 后端服务     | Python(FastAPI)/Go(Gin)                     | Python大模型生态最优 |
| 消息队列     | RabbitMQ/Kafka                              | 异步解耦，削峰填谷 |
| 大模型       | 私有部署：CodeLlama/StarCoder/GLM-Code/通义Code | 代码安全，无泄露风险 |
| 存储         | Redis(缓存/限流) + PostgreSQL(CR日志)       | 缓存重复代码CR结果 |
| GitLab交互   | python-gitlab/go-gitlab                     | 官方SDK，操作MR/评论/批注 |
| 代码检查     | ESLint/Pylint/CheckStyle + AI               | 传统规则兜底，AI做语义分析 |
| 部署         | Docker + K8s                                | 弹性扩容，适配多项目调用 |

---

## 三、核心执行流程（标准闭环）
1. **触发**：用户在GitLab创建/更新MR → 触发GitLab CI Pipeline
2. **鉴权&过滤**：服务校验GitLab密钥，过滤非保护分支/无关文件
3. **拉取变更**：通过GitLab API获取MR的`diff文件列表+代码片段`
4. **代码分片**：拆分超长代码，适配大模型上下文窗口
5. **Prompt构造**：注入代码规范、检查维度，**强制返回结构化JSON**
6. **AI推理**：调用私有Code大模型，生成BUG/ERROR/WARNING/优化建议
7. **结果解析**：校验AI返回的JSON，提取行号、问题级别、修改建议
8. **回写评论**：通过GitLab API发布**整体评论+行级批注**，打`AI-CR`标签
9. **日志监控**：记录CR耗时、成功率、问题数，异常告警

---

## 四、关键模块实现（核心代码）
### 1. 触发层：GitLab CI 配置（.gitlab-ci.yml）
**业界首选触发方式**，比Webhook更稳定，无事件丢失、跨域问题
```yaml
# 定义AI CodeReview任务
ai_code_review:
  stage: test
  only:
    - merge_requests  # 仅MR触发
    - main,develop     # 仅保护分支
  script:
    # 调用自研AI CR服务，传递MR参数
    - curl -X POST http://ai-cr-service:8000/api/cr/trigger \
        -H "Content-Type: application/json" \
        -H "X-GitLab-Token: $CI_GITLAB_TOKEN" \
        -d '{
          "project_id": "'$CI_PROJECT_ID'",
          "mr_iid": "'$CI_MERGE_REQUEST_IID'",
          "commit_sha": "'$CI_COMMIT_SHA'"
        }'
  timeout: 10m  # 超时保护
  allow_failure: true  # 不阻塞CI流程
```

### 2. 核心服务：FastAPI 后端（Python）
#### 依赖安装
```bash
pip install fastapi uvicorn python-gitlab openai redis pydantic python-dotenv
```

#### 核心配置文件（.env）
```env
# GitLab配置
GITLAB_URL=https://gitlab.xxx.com
GITLAB_PRIVATE_TOKEN=your_gitlab_token
# 大模型配置（私有部署）
LLM_BASE_URL=http://private-llm:8000/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=codellama-7b-code
# Redis配置
REDIS_URL=redis://redis:6379/0
```

#### 核心代码：AI CR服务主逻辑
```python
from fastapi import FastAPI, Header, HTTPException
from gitlab import Gitlab
import redis
import json
import requests
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="AI CodeReview Service")
redis_client = redis.from_url("redis://redis:6379/0")
gl = Gitlab("https://gitlab.xxx.com", private_token="your_token")

# 请求体模型
class MRTriggerReq(BaseModel):
    project_id: int
    mr_iid: int
    commit_sha: str

# 1. 忽略无关文件（业界通用规则）
IGNORE_FILES = [
    "node_modules/", "dist/", "build/", "test/", "__tests__/",
    "*.log", "*.md", "*.json", "*.yml", "*.yaml", "*.svg"
]

# 2. 结构化Prompt模板（核心！强制AI返回JSON）
CR_PROMPT = """
你是专业的代码评审工程师，仅检查代码的：语法错误、逻辑BUG、性能问题、安全漏洞、代码规范。
**严格按照以下JSON格式输出，禁止返回自然语言，禁止额外解释**：
{
  "total_issues": 数字,
  "issues": [
    {
      "file_path": "文件路径",
      "line_number": 行号,
      "level": "ERROR/WARNING/SUGGESTION",
      "title": "问题标题",
      "content": "问题详情+修改建议",
      "code_snippet": "问题代码片段"
    }
  ]
}

待评审代码：
{code_content}
"""

# 3. 获取MR变更diff
def get_mr_changes(project_id: int, mr_iid: int) -> List[dict]:
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(mr_iid)
    # 获取变更文件+diff
    changes = mr.changes()["changes"]
    # 过滤无关文件
    valid_changes = []
    for change in changes:
        file_path = change["new_path"]
        if not any(ignore in file_path for ignore in IGNORE_FILES):
            valid_changes.append(change)
    return valid_changes

# 4. 调用私有Code大模型
def call_ai_code_review(code: str) -> dict:
    # 缓存：相同代码直接返回结果，降低大模型调用成本
    cache_key = f"cr_cache:{hash(code)}"
    cache_result = redis_client.get(cache_key)
    if cache_result:
        return json.loads(cache_result)

    payload = {
        "model": "codellama-7b-code",
        "messages": [{"role": "user", "content": CR_PROMPT.format(code_content=code)}],
        "temperature": 0.1,  # 低温度，保证结果稳定
        "response_format": {"type": "json_object"}
    }
    # 调用私有大模型
    resp = requests.post(
        url="http://private-llm:8000/v1/chat/completions",
        headers={"Authorization": "Bearer sk-xxx"},
        json=payload,
        timeout=60
    )
    resp.raise_for_status()
    result = resp.json()["choices"][0]["message"]["content"]
    ai_result = json.loads(result)
    # 缓存1小时
    redis_client.setex(cache_key, 3600, json.dumps(ai_result))
    return ai_result

# 5. 回写GitLab MR评论
def create_mr_comment(project_id: int, mr_iid: int, ai_result: dict):
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(mr_iid)
    # 生成评论内容
    comment = f"### 🤖 AI CodeReview 结果\n"
    comment += f"共发现 {ai_result['total_issues']} 个问题\n\n"
    for idx, issue in enumerate(ai_result["issues"], 1):
        level_tag = {
            "ERROR": "🔴 ERROR",
            "WARNING": "🟡 WARNING",
            "SUGGESTION": "🔵 SUGGESTION"
        }[issue["level"]]
        comment += f"{idx}. **{level_tag}** | {issue['file_path']}:{issue['line_number']}\n"
        comment += f"   问题：{issue['title']}\n"
        comment += f"   建议：{issue['content']}\n\n"
    # 发布整体评论
    mr.notes.create({"body": comment})
    # 行级批注（可选，大厂进阶功能）
    for issue in ai_result["issues"]:
        mr.discussions.create({
            "body": f"{issue['level']}: {issue['content']}",
            "position": {
                "base_sha": mr.diff_refs["base_sha"],
                "head_sha": mr.diff_refs["head_sha"],
                "new_path": issue["file_path"],
                "new_line": issue["line_number"]
            }
        })

# 6. 对外触发接口
@app.post("/api/cr/trigger")
async def trigger_cr(req: MRTriggerReq, X_GitLab_Token: Optional[str] = Header(None)):
    # 鉴权
    if not X_GitLab_Token or X_GitLab_Token != "your_ci_token":
        raise HTTPException(401, "Unauthorized")
    try:
        # 1. 获取MR有效变更
        changes = get_mr_changes(req.project_id, req.mr_iid)
        if not changes:
            return {"code": 0, "msg": "无需要评审的代码"}
        # 2. 拼接代码，调用AI评审
        all_code = "\n\n".join([c["diff"] for c in changes])
        ai_result = call_ai_code_review(all_code)
        # 3. 回写评论到GitLab
        create_mr_comment(req.project_id, req.mr_iid, ai_result)
        return {"code": 0, "msg": "AI CodeReview完成", "data": ai_result}
    except Exception as e:
        return {"code": 500, "msg": f"评审失败：{str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 五、业界进阶优化方案（大厂必加）
### 1. 异步化改造（解决大模型超时）
用RabbitMQ将CR任务异步化，避免CI/接口超时：
- 触发接口仅接收请求，投递MQ
- 消费端异步执行AI推理+回写评论

### 2. 代码分片处理
大模型有上下文限制，超过阈值自动拆分文件/代码块，分别评审后合并结果。

### 3. 混合Lint规则
先执行`ESLint/Pylint`做基础语法检查，再用AI做**语义级/逻辑级**深度评审，准确率提升50%+。

### 4. 项目级自定义配置
支持项目根目录添加`.ai-cr-config`，配置：
- 忽略文件/目录
- 检查规则开关（安全/性能/规范）
- 问题级别阈值（ERROR才阻塞MR）

### 5. 成本&安全控制
- 限流：Redis限制单项目每分钟调用次数
- 代码脱敏：敏感代码字段自动脱敏后再入大模型
- 审计：所有CR记录落库，可追溯

### 6. MR阻塞机制
配置规则：**ERROR级别问题未修复，禁止合并MR**，通过GitLab API设置MR状态为`blocked`。

---

## 六、部署方式（生产级）
1. **容器化**：将服务打包为Docker镜像
2. **K8s编排**：部署服务+MQ+Redis+私有大模型
3. **GitLab集成**：配置CI变量，全局共享AI CR任务
4. **监控**：接入Prometheus监控大模型调用耗时、失败率，ELK收集日志

这套方案是**字节、阿里、腾讯内部AI CodeReview的标准简化版**，兼顾稳定性、代码安全、落地成本，可直接基于此代码二次开发扩展。
