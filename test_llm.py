"""
测试大模型连接脚本
用于验证 LLM 配置是否正确（兼容 OpenAI 协议的模型如 DeepSeek、Qwen、豆包等）

使用方法:
    uv run python test_llm.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env 文件
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# 从环境变量读取配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TEMPERATURE = os.getenv("LLM_TEMPERATURE", 0.1)


def test_llm_connection():
    """测试大模型连接"""
    print("=" * 50)
    print("大模型连接测试")
    print("=" * 50)
    print(f"Base URL: {LLM_BASE_URL}")
    print(f"Model: {LLM_MODEL}")
    print(f"API Key: {LLM_API_KEY[:10]}..." if LLM_API_KEY else "API Key 未设置!")
    print("=" * 50)

    if not LLM_API_KEY:
        print("❌ 错误: LLM_API_KEY 未设置")
        return False

    try:
        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
        )

        print("\n正在调用模型...")
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一个有帮助的助手。"},
                {"role": "user", "content": "请用一句话回答: 1+1等于几？"},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=100,
        )

        print("\n✅ 连接成功!")
        print("-" * 50)
        print(f"响应内容: {response.choices[0].message.content}")
        print(f"模型: {response.model}")
        print(
            f"Token 使用: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}"
        )
        return True

    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        return False


def test_cr_prompt():
    """测试代码评审 Prompt"""
    print("\n" + "=" * 50)
    print("代码评审 Prompt 测试")
    print("=" * 50)

    test_code = """
### File: src/main.py (NEW)

```diff
+def get_user(user_id):
+    sql = f"SELECT * FROM users WHERE id = {user_id}"
+    return db.execute(sql)
```
"""

    prompt = f"""你是一个专业的代码评审工程师。请对以下代码进行评审。

## 评审要求
将问题分为两类：
- **bug**: 必须修复的问题
- **suggestion**: 建议改进的问题

## 输出格式
严格按照以下JSON格式输出：
```json
{{
  "total_issues": 数字,
  "issues": [
    {{
      "file_path": "文件路径",
      "line_number": 行号,
      "level": "bug或suggestion",
      "title": "问题标题",
      "content": "问题描述和修改建议"
    }}
  ]
}}
```

## 待评审代码
{test_code}

请开始评审："""

    try:
        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
        )

        print("正在调用模型进行代码评审...")
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的代码评审工程师，擅长发现代码中的bug和改进点。你必须严格按照JSON格式输出。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )

        print("\n✅ 评审成功!")
        print("-" * 50)
        print(f"评审结果:\n{response.choices[0].message.content}")
        return True

    except Exception as e:
        print(f"\n❌ 评审失败: {e}")
        return False


if __name__ == "__main__":
    # 测试基本连接
    success = test_llm_connection()

    # 如果基本连接成功，测试 CR prompt
    if success:
        test_cr_prompt()
