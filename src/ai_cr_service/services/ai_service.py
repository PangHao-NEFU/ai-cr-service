"""AI service for code review using LLM (LangChain version)."""

import json
import logging
import re
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..config import LLMProvider, Settings, get_settings
from ..models.schemas import AICRResult, CRIssue, CRIssueLevel, GitLabDiffFile
from .rule_service import get_rule_service

logger = logging.getLogger(__name__)

# System prompt
SYSTEM_PROMPT = """你是一个专业的代码评审工程师，擅长发现代码中的bug和改进点。你必须严格按照JSON格式输出。"""

# Code review prompt template
CR_PROMPT_TEMPLATE = """请对以下代码进行评审。

{rules_section}

## 评审要求
请将问题分为两类：
- **bug**: 必须修复的问题（潜在的bug、安全漏洞、逻辑错误）
- **suggestion**: 建议改进的问题（代码风格、可读性、性能优化）

## 注意事项
- 只评审新增或修改的代码（diff 中 + 开头的行）
- 忽略删除的代码（diff 中 - 开头的行）
- 行号应该是新文件中的行号

## 输出格式
严格按照以下JSON格式输出，禁止返回自然语言：
```json
{{
  "total_issues": 数字,
  "issues": [
    {{
      "file_path": "文件路径",
      "line_number": 行号,
      "level": "bug或suggestion",
      "title": "问题标题",
      "content": "问题描述和修改建议",
      "code_snippet": "问题代码片段"
    }}
  ]
}}
```
{context_section}

## 待评审代码
{code_content}

请开始评审："""


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string."""
    if not text:
        return 0

    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    remaining = (
        len(text) - chinese_chars - sum(len(w) for w in re.findall(r"[a-zA-Z]+", text))
    )

    return int(chinese_chars * 2 + english_words * 1.3 + remaining * 0.5)


class AIService:
    """Service for AI-powered code review using LangChain."""

    # 支持的模型上下文窗口大小
    MODEL_CONTEXT_LIMITS = {
        "Qwen3-235B-A22B": 128000,
        "deepseekv2": 128000,
    }

    DEFAULT_CONTEXT_WINDOW = 32000
    PROMPT_OVERHEAD = 2000
    RESPONSE_BUFFER = 4000

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._llm: ChatOpenAI | None = None
        self.rule_service = get_rule_service()

    @property
    def llm(self) -> ChatOpenAI:
        """Get or create LangChain ChatOpenAI instance."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.settings.llm_model,
                api_key=self.settings.llm_api_key,
                base_url=(
                    self.settings.llm_base_url
                    if self.settings.llm_provider == LLMProvider.CUSTOM
                    else None
                ),
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
                timeout=self.settings.llm_timeout,
            )
        return self._llm

    @property
    def max_code_tokens(self) -> int:
        """Get maximum tokens available for code content."""
        context_limit = self.MODEL_CONTEXT_LIMITS.get(
            self.settings.llm_model, self.DEFAULT_CONTEXT_WINDOW
        )
        return context_limit - self.PROMPT_OVERHEAD - self.RESPONSE_BUFFER

    def _build_prompt(self) -> ChatPromptTemplate:
        """Build the ChatPromptTemplate for code review."""
        return ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("user", CR_PROMPT_TEMPLATE),
            ]
        )

    def review_code(
        self,
        diff_files: List[GitLabDiffFile],
        context: dict | None = None,
    ) -> AICRResult:
        """
        Perform AI code review on changed files.

        Only sends diff content (with built-in context) to LLM.
        Automatically splits large MRs into chunks if needed.
        """
        if not diff_files:
            return AICRResult(total_issues=0, issues=[])

        # 检测语言并加载规范
        file_paths = [f.new_path for f in diff_files]
        languages = self.rule_service.detect_languages(file_paths)
        rules_content = self.rule_service.get_rules_for_languages(languages)
        logger.info(f"Loaded rules for languages: {languages}")

        code_content = self._build_code_content(diff_files)
        estimated_tokens = estimate_tokens(code_content)

        logger.info(
            f"Estimated tokens: {estimated_tokens}, max allowed: {self.max_code_tokens}"
        )

        if estimated_tokens <= self.max_code_tokens:
            return self._review_single(diff_files, rules_content, context)
        else:
            logger.info(
                f"Code too large ({estimated_tokens} tokens), splitting into chunks"
            )
            return self._review_chunked(diff_files, rules_content, context)

    def _review_single(
        self,
        diff_files: List[GitLabDiffFile],
        rules_content: str,
        context: dict | None = None,
    ) -> AICRResult:
        """Review code in a single LLM call using LangChain."""
        code_content = self._build_code_content(diff_files)
        context_section = self._build_context_section(context)

        # 构建规范部分
        rules_section = f"## 代码规范\n\n{rules_content}" if rules_content else ""

        # 构建 prompt
        prompt = self._build_prompt()

        # 创建链
        chain = prompt | self.llm | StrOutputParser()

        try:
            # 执行链
            result_text = chain.invoke(
                {
                    "rules_section": rules_section,
                    "code_content": code_content,
                    "context_section": context_section,
                }
            )

            if not result_text:
                logger.warning("Empty response from LLM")
                return AICRResult(total_issues=0, issues=[])

            return self._parse_result(result_text, diff_files)

        except Exception as e:
            logger.error(f"Failed to call LLM: {e}")
            raise

    def _build_context_section(self, context: dict | None) -> str:
        """Build MR context section for prompt."""
        if not context:
            return ""

        parts = []

        mr_title = context.get("mr_title", "")
        author = context.get("author", "")
        source_branch = context.get("source_branch", "")
        target_branch = context.get("target_branch", "")
        mr_description = context.get("mr_description", "")

        if mr_title:
            parts.append(f"- 标题: {mr_title}")
        if author:
            parts.append(f"- 作者: {author}")
        if source_branch and target_branch:
            parts.append(f"- 分支: {source_branch} → {target_branch}")

        if mr_description:
            parts.append(f"\n### MR 描述\n{mr_description[:500]}")

        if parts:
            return "\n## MR 上下文\n" + "\n".join(parts)

        return ""

    def _review_chunked(
        self,
        diff_files: List[GitLabDiffFile],
        rules_content: str,
        context: dict | None = None,
    ) -> AICRResult:
        """Review large MR by splitting into chunks."""
        chunks = self._split_into_chunks(diff_files)
        logger.info(f"Split into {len(chunks)} chunks")

        all_issues: List[CRIssue] = []

        for i, chunk_files in enumerate(chunks):
            logger.info(
                f"Reviewing chunk {i + 1}/{len(chunks)} ({len(chunk_files)} files)"
            )

            try:
                result = self._review_single(chunk_files, rules_content, context)
                all_issues.extend(result.issues)
            except Exception as e:
                logger.error(f"Failed to review chunk {i + 1}: {e}")
                continue

        unique_issues = self._deduplicate_issues(all_issues)

        return AICRResult(total_issues=len(unique_issues), issues=unique_issues)

    def _split_into_chunks(
        self, diff_files: List[GitLabDiffFile]
    ) -> List[List[GitLabDiffFile]]:
        """Split files into chunks that fit within token limit."""
        chunks: List[List[GitLabDiffFile]] = []
        current_chunk: List[GitLabDiffFile] = []
        current_tokens = 0

        file_tokens = [(f, estimate_tokens(f.diff)) for f in diff_files]
        file_tokens.sort(key=lambda x: x[1], reverse=True)

        for file, tokens in file_tokens:
            separator_tokens = 50

            if current_tokens + tokens + separator_tokens > self.max_code_tokens:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [file]
                current_tokens = tokens
            else:
                current_chunk.append(file)
                current_tokens += tokens + separator_tokens

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _deduplicate_issues(self, issues: List[CRIssue]) -> List[CRIssue]:
        """Remove duplicate issues."""
        seen = set()
        unique_issues = []

        for issue in issues:
            key = (issue.file_path, issue.line_number, issue.title)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        return unique_issues

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

    def _extract_json_from_response(self, result_text: str) -> str | None:
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

    def _parse_result(
        self, result_text: str, diff_files: List[GitLabDiffFile]
    ) -> AICRResult:
        """Parse LLM response into AICRResult."""
        # 提取 JSON 内容（过滤 thinking 过程）
        json_content = self._extract_json_from_response(result_text)

        if not json_content:
            logger.warning("Failed to extract JSON from LLM response")
            logger.debug(f"Raw response: {result_text[:500]}")
            return AICRResult(total_issues=0, issues=[])

        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Extracted content: {json_content[:500]}")
            return AICRResult(total_issues=0, issues=[])

        issues = []
        file_paths = {f.new_path for f in diff_files}

        for issue_data in data.get("issues", []):
            file_path = issue_data.get("file_path", "")
            if file_path not in file_paths:
                for fp in file_paths:
                    if file_path in fp or fp.endswith(file_path):
                        file_path = fp
                        break

            level_str = issue_data.get("level", "suggestion").lower()
            try:
                level = CRIssueLevel(level_str)
            except ValueError:
                level = CRIssueLevel.SUGGESTION

            issues.append(
                CRIssue(
                    file_path=file_path,
                    line_number=issue_data.get("line_number", 1),
                    level=level,
                    title=issue_data.get("title", "Code issue"),
                    content=issue_data.get("content", ""),
                    code_snippet=issue_data.get("code_snippet"),
                )
            )

        return AICRResult(total_issues=len(issues), issues=issues)

    def health_check(self) -> bool:
        """Check if LLM service is available."""
        try:
            response = self.llm.invoke("你是什么模型")
            return bool(response.content)
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False
