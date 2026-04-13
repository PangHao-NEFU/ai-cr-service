"""AI service for code review using LLM."""

import json
import logging
from typing import List

from openai import OpenAI

from ..config import LLMProvider, Settings, get_settings
from ..models.schemas import AICRResult, CRIssue, CRIssueLevel, GitLabDiffFile

logger = logging.getLogger(__name__)


# Code review prompt template
CR_PROMPT_TEMPLATE = """你是一个专业的代码评审工程师。请根据以下团队代码规范对代码进行评审：

## 代码规范
1. 代码风格：遵循对应语言的官方代码风格指南
2. 命名规范：变量、函数、类使用有意义的名称
3. 错误处理：正确处理异常和边界情况
4. 安全性：避免常见安全漏洞（SQL注入、XSS、敏感信息泄露等）
5. 性能：避免明显的性能问题
6. 可维护性：代码清晰、模块化、易于理解

## 评审要求
请将问题分为两类：
- **bug**: 必须修复的问题（潜在的bug、安全漏洞、逻辑错误）
- **suggestion**: 建议改进的问题（代码风格、可读性、性能优化）

## 输出格式
严格按照以下JSON格式输出，禁止返回自然语言：
```json
{
  "total_issues": 数字,
  "issues": [
    {
      "file_path": "文件路径",
      "line_number": 行号(估算),
      "level": "bug或suggestion",
      "title": "问题标题",
      "content": "问题描述和修改建议",
      "code_snippet": "问题代码片段"
    }
  ]
}
```

## 待评审代码
{code_content}

请开始评审："""


class AIService:
    """Service for AI-powered code review."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            if self.settings.llm_provider == LLMProvider.CUSTOM and self.settings.llm_base_url:
                self._client = OpenAI(
                    api_key=self.settings.llm_api_key,
                    base_url=self.settings.llm_base_url,
                )
            else:
                self._client = OpenAI(
                    api_key=self.settings.llm_api_key,
                )
        return self._client

    def review_code(
        self,
        diff_files: List[GitLabDiffFile],
        code_standards: str | None = None,
    ) -> AICRResult:
        """
        Perform AI code review on changed files.

        Args:
            diff_files: List of changed files with diffs
            code_standards: Optional custom code standards

        Returns:
            AICRResult with issues found
        """
        if not diff_files:
            return AICRResult(total_issues=0, issues=[])

        # Build code content for review
        code_content = self._build_code_content(diff_files)

        # Build prompt
        prompt = CR_PROMPT_TEMPLATE.format(code_content=code_content)
        if code_standards:
            prompt = prompt.replace("## 代码规范\n1. 代码风格", f"## 代码规范\n{code_standards}\n\n1. 代码风格")

        try:
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的代码评审工程师，擅长发现代码中的bug和改进点。你必须严格按照JSON格式输出。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            if not result_text:
                logger.warning("Empty response from LLM")
                return AICRResult(total_issues=0, issues=[])

            # Parse result
            result = self._parse_result(result_text, diff_files)
            return result

        except Exception as e:
            logger.error(f"Failed to call LLM: {e}")
            raise

    def _build_code_content(self, diff_files: List[GitLabDiffFile]) -> str:
        """Build code content string from diff files."""
        parts = []
        for file in diff_files:
            header = f"### File: {file.new_path}"
            if file.new_file:
                header += " (NEW)"
            elif file.renamed_file:
                header += f" (RENAMED from {file.old_path})"

            parts.append(f"{header}\n\n```diff\n{file.diff}\n```")

        return "\n\n---\n\n".join(parts)

    def _parse_result(
        self,
        result_text: str,
        diff_files: List[GitLabDiffFile],
    ) -> AICRResult:
        """Parse LLM response into AICRResult."""
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return AICRResult(total_issues=0, issues=[])

        issues = []
        file_paths = {f.new_path for f in diff_files}

        for issue_data in data.get("issues", []):
            # Validate file path
            file_path = issue_data.get("file_path", "")
            if file_path not in file_paths:
                # Try to find closest match
                for fp in file_paths:
                    if file_path in fp or fp.endswith(file_path):
                        file_path = fp
                        break

            # Parse level
            level_str = issue_data.get("level", "suggestion").lower()
            try:
                level = CRIssueLevel(level_str)
            except ValueError:
                level = CRIssueLevel.SUGGESTION

            issues.append(CRIssue(
                file_path=file_path,
                line_number=issue_data.get("line_number", 1),
                level=level,
                title=issue_data.get("title", "Code issue"),
                content=issue_data.get("content", ""),
                code_snippet=issue_data.get("code_snippet"),
            ))

        return AICRResult(
            total_issues=len(issues),
            issues=issues,
        )

    def health_check(self) -> bool:
        """Check if LLM service is available."""
        try:
            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
            )
            return bool(response.choices)
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False
