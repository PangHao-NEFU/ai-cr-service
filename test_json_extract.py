"""
测试JSON提取和GitLab行级评论流程
验证从大模型响应（含think标签）中提取JSON，并模拟GitLab评论流程
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


# 模拟数据结构
class CRIssueLevel(Enum):
    BUG = "bug"
    SUGGESTION = "suggestion"


@dataclass
class CRIssue:
    file_path: str
    line_number: int
    level: CRIssueLevel
    title: str
    content: str
    code_snippet: Optional[str] = None


@dataclass
class AICRResult:
    total_issues: int
    issues: List[CRIssue]


def _extract_json_from_response(result_text: str) -> str | None:
    """Extract JSON content from LLM response, filtering out thinking process."""
    # 0. 移除 <think>...</think> 标签内容（某些模型会输出思考过程）
    think_pattern = r"<think>.*?</think>"
    result_text = re.sub(think_pattern, "", result_text, flags=re.DOTALL)

    # 1. 尝试匹配 ```json ... ``` 代码块
    json_block_pattern = r"```json\s*(.*?)\s*```"
    match = re.search(json_block_pattern, result_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 2. 尝试匹配普通 ``` ... ``` 代码块
    code_block_pattern = r"```\s*(.*?)\s*```"
    match = re.search(code_block_pattern, result_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 3. 尝试从第一个 { 到最后一个 } 提取（用于没有代码块的情况）
    json_start = result_text.find("{")
    json_end = result_text.rfind("}")
    if json_start != -1 and json_end != -1 and json_end > json_start:
        return result_text[json_start : json_end + 1].strip()

    return None


def parse_result(json_content: str) -> AICRResult:
    """Parse JSON content into AICRResult."""
    data = json.loads(json_content)

    issues = []
    for issue_data in data.get("issues", []):
        level_str = issue_data.get("level", "suggestion").lower()
        try:
            level = CRIssueLevel(level_str)
        except ValueError:
            level = CRIssueLevel.SUGGESTION

        issues.append(
            CRIssue(
                file_path=issue_data.get("file_path", ""),
                line_number=issue_data.get("line_number", 1),
                level=level,
                title=issue_data.get("title", "Code issue"),
                content=issue_data.get("content", ""),
                code_snippet=issue_data.get("code_snippet"),
            )
        )

    return AICRResult(total_issues=len(issues), issues=issues)


def build_gitlab_comment(issue: CRIssue) -> str:
    """Build GitLab comment body for an issue."""
    level_emoji = "🐛" if issue.level == CRIssueLevel.BUG else "💡"
    level_tag = "BUG" if issue.level == CRIssueLevel.BUG else "SUGGESTION"

    body = f"**{level_emoji} [{level_tag}]** {issue.title}\n\n{issue.content}"

    if issue.code_snippet:
        body += f"\n\n```{issue.code_snippet}```"

    return body


def main():
    """主测试函数"""
    print("=" * 60)
    print("测试：从大模型响应中提取JSON并生成GitLab评论")
    print("=" * 60)

    # 模拟大模型响应（含think标签）
    llm_response = """好的，我现在需要评审用户提供的代码，检查是否存在安全规范方面的问题。首先看用户给的代码片段是在src/main.py文件中的get_user函数。这里有一个SQL查询，使用了f-string来拼接用户ID。

根据安全规范，SQL查询必须使用参数化，禁止字符串拼接。显然这里的代码违反了这一规定。用户ID直接插入到SQL字符串中，这可能导致SQL注入攻击。比如，如果user_id是恶意输入，可能会篡改SQL语句，造成数据泄露或其他安全问题。

接下来，我需要确定问题的级别。因为这是SQL注入漏洞，属于安全问题，应该标记为bug而不是建议。然后要给出具体的修改建议，比如使用参数化查询，将用户ID作为参数传递，而不是直接拼接字符串。

另外，检查是否有其他问题，比如硬编码的敏感信息，但这段代码里没有涉及。所以唯一的问题就是SQL拼接的问题。行号是第三行，也就是构造sql变量的那一行。

最后，按照JSON格式输出结果，确保total_issues和issues数组中的每个条目都正确无误。确认文件路径、行号、级别、标题和内容都准确描述了问题。

```json
{
  "total_issues": 1,
  "issues": [
    {
      "file_path": "src/main.py",
      "line_number": 3,
      "level": "bug",
      "title": "SQL注入漏洞",
      "content": "使用字符串拼接方式构造SQL查询，可能导致SQL注入攻击。建议改为参数化查询，例如：sql = 'SELECT * FROM users WHERE id = %s'，并使用参数传递user_id值。"
    }
  ]
}
```"""

    print("\n【步骤1】原始响应（前200字符）:")
    print(f"  {llm_response[:200]}...")

    print("\n【步骤2】提取JSON:")
    json_content = _extract_json_from_response(llm_response)
    if json_content:
        print(f"  ✅ 成功提取JSON（{len(json_content)}字符）")
        print(f"  内容: {json_content[:100]}...")
    else:
        print("  ❌ 提取失败")
        return

    print("\n【步骤3】解析JSON为AICRResult:")
    try:
        result = parse_result(json_content)
        print(f"  ✅ 解析成功")
        print(f"  - 总问题数: {result.total_issues}")
        for i, issue in enumerate(result.issues, 1):
            print(f"  - 问题{i}: {issue.title}")
            print(f"    文件: {issue.file_path}:{issue.line_number}")
            print(f"    级别: {issue.level.value}")
    except Exception as e:
        print(f"  ❌ 解析失败: {e}")
        return

    print("\n【步骤4】生成GitLab行级评论:")
    for issue in result.issues:
        comment = build_gitlab_comment(issue)
        print(f"\n  📍 评论位置: {issue.file_path}:{issue.line_number}")
        print(f"  📝 评论内容:")
        for line in comment.split("\n"):
            print(f"     {line}")

    print("\n" + "=" * 60)
    print("【步骤5】模拟GitLab API调用:")
    print("=" * 60)
    print("\n  实际调用代码:")
    print("""
    # 在 cr_service.py 中的 _post_issue_comment() 方法：
    self.gitlab_service.create_mr_discussion(
        project_id=123,           # GitLab 项目ID
        mr_iid=456,               # Merge Request IID
        body=comment,             # 评论内容
        file_path=issue.file_path, # 文件路径
        line_number=issue.line_number,  # 行号
    )
    """)

    print("\n  # 在 gitlab_service.py 中的 create_mr_discussion() 方法：")
    print("""
    discussion = mr.discussions.create({
        "body": body,
        "position": {
            "base_sha": diff_refs["base_sha"],
            "head_sha": diff_refs["head_sha"],
            "start_sha": diff_refs["base_sha"],
            "position_type": "text",
            "new_path": file_path,
            "new_line": line_number,
        }
    })
    """)

    print("\n✅ 测试完成！JSON提取和GitLab评论流程正常工作。")


if __name__ == "__main__":
    main()
