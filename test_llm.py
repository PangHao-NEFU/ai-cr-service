"""
测试大模型连接脚本
用于验证 LLM 配置是否正确（兼容 OpenAI 协议的模型如 DeepSeek、Qwen、豆包等）

使用方法:
    uv run python test_llm.py
"""

import os
import requests
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 加载 .env 文件
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# 从环境变量读取配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))


def test_llm_with_requests():
    """用 requests 直接测试大模型连接"""
    print("=" * 50)
    print("大模型连接测试 (requests)")
    print("=" * 50)
    print(f"Base URL: {LLM_BASE_URL}")
    print(f"Model: {LLM_MODEL}")
    print(f"API Key: {LLM_API_KEY[:10]}..." if LLM_API_KEY else "API Key 未设置!")
    print("=" * 50)

    if not LLM_API_KEY:
        print("❌ 错误: LLM_API_KEY 未设置")
        return False

    # 构建完整的 API URL
    api_url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    print(f"\n请求 URL: {api_url}")

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "user", "content": "who are you？what is your model name"}
        ],
        "temperature": LLM_TEMPERATURE,
        "enable_thinking": False,
    }

    try:
        print("\nrequest正在调用模型...")
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)

        print(f"HTTP 状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n✅ request连接成功!")
            print("-" * 50)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"响应内容: {content}")
            return True
        else:
            print(f"\n❌ request请求失败: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("\n❌ request请求超时 (60秒)")
        return False
    except Exception as e:
        print(f"\n❌ request连接失败: {e}")
        return False


def test_llm_connection():
    """测试大模型连接（使用 LangChain）"""
    print("=" * 50)
    print("大模型连接测试 (LangChain)")
    print("=" * 50)
    print(f"Base URL: {LLM_BASE_URL}")
    print(f"Model: {LLM_MODEL}")
    print(f"API Key: {LLM_API_KEY[:10]}..." if LLM_API_KEY else "API Key 未设置!")
    print("=" * 50)

    if not LLM_API_KEY:
        print("❌ 错误: LLM_API_KEY 未设置")
        return False

    try:
        # 使用 LangChain ChatOpenAI
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=LLM_TEMPERATURE,
            extra_body={"enable_thinking": False},
        )

        print("\n正在调用模型...")

        # 简单测试
        response = llm.invoke("who are you")

        print("\n✅ 连接成功!")
        print("-" * 50)
        print(f"响应内容: {response.content}")
        print(f"Token 使用: { response.usage_metadata }")
        return True

    except Exception as e:
        print(f"\n❌ 连接失败: { e }")
        return False


def test_cr_prompt():
    """测试代码评审 Prompt（使用 LangChain PromptTemplate）"""
    print("\n" + "=" * 50)
    print("代码评审 Prompt 测试 (LangChain)")
    print("=" * 50)

    # 定义 Prompt 模板
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一个专业的代码评审工程师，擅长发现代码中的bug和改进点。你必须严格按照JSON格式输出。",
            ),
            (
                "user",
                """请对以下代码进行评审。

## 安全规范
- 禁止硬编码密码、API Key、Token 等敏感信息
- SQL 查询必须使用参数化，禁止字符串拼接

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
{code_content}

请开始评审：""",
            ),
        ]
    )

    test_code = """
### File: src/main.py (NEW)

```diff
+def get_user(user_id):
+    sql = f"SELECT * FROM users WHERE id = {user_id}"
+    return db.execute(sql)
```
"""

    try:
        # 创建 LLM
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=LLM_TEMPERATURE,
        )

        # 创建链
        chain = prompt | llm | StrOutputParser()

        print("正在调用模型进行代码评审...")

        # 执行链
        result = chain.invoke({"code_content": test_code})

        print("\n✅ 评审成功!")
        print("-" * 50)
        print(f"评审结果:\n{result}")
        return True

    except Exception as e:
        print(f"\n❌ 评审失败: {e}")
        return False


def test_prompt_template():
    """测试 Prompt 模板管理功能"""
    print("\n" + "=" * 50)
    print("Prompt 模板管理测试")
    print("=" * 50)

    # 定义模板
    template = ChatPromptTemplate.from_messages(
        [
            ("system", "你是 {role}。"),
            ("user", "{task}"),
        ]
    )

    # 演示模板变量
    messages = template.format_messages(
        role="专业的代码评审工程师", task="请评审这段代码: def hello(): pass"
    )

    print("\n生成的消息:")
    for msg in messages:
        print(f"  [{msg.type}]: {msg.content[:50]}...")

    print("\n✅ Prompt 模板功能正常")
    return True


if __name__ == "__main__":
    # 先用 requests 测试，更直观地看到问题
    success = test_llm_with_requests()

    # 如果 requests 成功，再用 LangChain 测试
    if success:
        print("\n" + "=" * 50)
        print("requests 测试成功，继续测试 LangChain...")
        print("=" * 50)
        if test_llm_connection():
            test_cr_prompt()
            test_prompt_template()
    else:
        print("requests 测试失败❎，检查网络或者baseurl")
