"""Code rules service for loading coding standards."""

import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

# 文件扩展名到语言的映射
LANGUAGE_MAP: Dict[str, str] = {
    # Python
    ".py": "python",
    # Go
    ".go": "go",
    # Java
    ".java": "java",
    ".kt": "java",  # Kotlin 使用类似规范
    ".kts": "java",
    # TypeScript / JavaScript
    ".ts": "typescript",
    ".tsx": "react",
    ".js": "typescript",
    ".jsx": "react",
    ".mjs": "typescript",
    ".cjs": "typescript",
    # Vue
    ".vue": "vue",
    # 其他语言（可扩展）
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".swift": "swift",
    ".scala": "scala",
}


class RuleSource(ABC):
    """规范来源抽象基类，支持扩展不同的规范获取方式。"""

    @abstractmethod
    def get_rule(self, name: str) -> Optional[str]:
        """获取指定名称的规范内容。"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查规范源是否可用。"""
        pass


class LocalFileRuleSource(RuleSource):
    """本地文件系统规范源。"""

    def __init__(self, rules_dir: Path):
        self.rules_dir = rules_dir

    def get_rule(self, name: str) -> Optional[str]:
        """从本地文件加载规范。"""
        rule_path = self.rules_dir / f"{name}.md"
        if not rule_path.exists():
            return None

        try:
            return rule_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to load rule file {rule_path}: {e}")
            return None

    def is_available(self) -> bool:
        """检查规则目录是否存在。"""
        return self.rules_dir.exists() and self.rules_dir.is_dir()


class FeishuRuleSource(RuleSource):
    """
    飞书文档规范源（预留接口）。

    使用方式：
    1. 配置飞书应用 ID 和密钥
    2. 配置规范文档的 token 或 URL
    3. 自动从飞书获取规范内容

    TODO: 实现飞书 API 调用
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        rule_tokens: Optional[Dict[str, str]] = None,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.rule_tokens = rule_tokens or {}  # name -> doc_token
        self._access_token: Optional[str] = None

    def get_rule(self, name: str) -> Optional[str]:
        """从飞书文档获取规范内容。"""
        if name not in self.rule_tokens:
            return None

        # TODO: 实现飞书 API 调用
        # 1. 获取 access_token
        # 2. 调用飞书文档 API 获取内容
        # 3. 解析并返回

        logger.warning(f"Feishu rule source not implemented yet for: {name}")
        return None

    def is_available(self) -> bool:
        """检查飞书配置是否完整。"""
        return bool(self.app_id and self.app_secret and self.rule_tokens)

    def _get_access_token(self) -> Optional[str]:
        """获取飞书访问令牌。"""
        # TODO: 实现获取 access_token
        # 参考: https://open.feishu.cn/document/ukTMukTMukTM/uYTM5UjL2ETO14iNxkTN/g
        return None


class RuleService:
    """
    规范服务，管理代码规范加载。

    支持多种规范来源：
    1. 本地文件（默认）
    2. 飞书文档（预留）
    3. 其他远程源（可扩展）
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

        # 规范来源列表（按优先级）
        self.sources: List[RuleSource] = []

        # 初始化本地规范源
        rules_dir = Path(__file__).parent.parent.parent.parent / "rules"
        self.sources.append(LocalFileRuleSource(rules_dir))

        # TODO: 初始化飞书规范源（如果配置了）
        # if settings.feishu_app_id:
        #     self.sources.append(FeishuRuleSource(...))

        # 规范缓存
        self._cache: Dict[str, str] = {}

    def get_rule(self, name: str) -> Optional[str]:
        """
        获取指定规范内容。

        按来源优先级依次尝试获取，结果会被缓存。
        """
        if name in self._cache:
            return self._cache[name]

        for source in self.sources:
            if not source.is_available():
                continue

            content = source.get_rule(name)
            if content:
                self._cache[name] = content
                logger.debug(f"Loaded rule '{name}' from {source.__class__.__name__}")
                return content

        logger.warning(f"Rule '{name}' not found in any source")
        return None

    def get_rules_for_languages(self, languages: Set[str]) -> str:
        """
        获取指定语言的规范内容。

        Args:
            languages: 语言名称集合（如 {"python", "go"}）

        Returns:
            合并后的规范内容字符串
        """
        rules = []

        # 1. 始终加载安全规范
        security_rule = self.get_rule("security")
        if security_rule:
            rules.append(("安全规范", security_rule))

        # 2. 加载语言规范
        for lang in sorted(languages):
            rule = self.get_rule(lang)
            if rule:
                rules.append((self._get_rule_title(lang), rule))

        # 3. 如果没有匹配任何语言规范，加载默认规范
        if len(rules) <= 1:  # 只有安全规范
            default_rule = self.get_rule("default")
            if default_rule:
                rules.append(("通用规范", default_rule))

        # 合并所有规范
        return self._format_rules(rules)

    def _get_rule_title(self, lang: str) -> str:
        """获取规范标题。"""
        lang_titles = {
            "python": "Python 代码规范",
            "go": "Go 代码规范",
            "java": "Java 代码规范",
            "typescript": "TypeScript 代码规范",
            "react": "React 代码规范",
            "vue": "Vue 代码规范",
            "rust": "Rust 代码规范",
            "ruby": "Ruby 代码规范",
            "php": "PHP 代码规范",
            "csharp": "C# 代码规范",
            "cpp": "C++ 代码规范",
            "swift": "Swift 代码规范",
            "scala": "Scala 代码规范",
        }
        return lang_titles.get(lang, f"{lang.title()} 代码规范")

    def _format_rules(self, rules: List[tuple]) -> str:
        """格式化规范内容。"""
        if not rules:
            return ""

        parts = []
        for title, content in rules:
            # 提取规范的标题行（第一个 # 标题）
            lines = content.strip().split("\n")
            if lines and lines[0].startswith("# "):
                # 移除原标题，使用我们生成的标题
                content = "\n".join(lines[1:]).strip()

            parts.append(f"## {title}\n\n{content}")

        return "\n\n---\n\n".join(parts)

    def detect_languages(self, file_paths: List[str]) -> Set[str]:
        """
        根据文件路径检测涉及的编程语言。

        Args:
            file_paths: 文件路径列表

        Returns:
            语言名称集合
        """
        languages: Set[str] = set()

        for file_path in file_paths:
            # 获取文件扩展名
            ext = Path(file_path).suffix.lower()
            if ext in LANGUAGE_MAP:
                languages.add(LANGUAGE_MAP[ext])

        return languages

    def clear_cache(self) -> None:
        """清空规范缓存。"""
        self._cache.clear()
        logger.info("Rule cache cleared")


# 单例
_rule_service: Optional[RuleService] = None


def get_rule_service() -> RuleService:
    """获取规范服务单例。"""
    global _rule_service
    if _rule_service is None:
        _rule_service = RuleService()
    return _rule_service
