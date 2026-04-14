"""Configuration management using pydantic-settings."""

from enum import Enum
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"  # 兼容 OpenAI 协议的私有模型（DeepSeek、Qwen 等）


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略 .env 中多余的配置项
    )

    # Server settings
    app_name: str = "AI Code Review Service"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # GitLab settings
    gitlab_url: str = Field(..., description="GitLab instance URL")
    gitlab_private_token: str = Field(..., description="GitLab private token")
    gitlab_verify_ssl: bool = True

    # LLM settings
    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_api_key: str = Field(..., description="LLM API key")
    llm_base_url: str | None = Field(None, description="LLM base URL for custom provider")
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1  # 低温度保证稳定输出
    llm_max_tokens: int = 4096
    llm_timeout: int = 120

    # TODO: Redis 缓存暂不启用，后续可能接入
    # redis_url: str = "redis://localhost:6379/0"
    # redis_cache_ttl: int = 3600

    # CR settings - 忽略的文件和扩展名
    cr_ignore_files: List[str] = Field(
        default=[
            "node_modules/",
            "dist/",
            "build/",
            "__pycache__/",
            ".git/",
            "vendor/",
            "*.lock",
            "*.min.js",
            "*.min.css",
            "*.svg",
            "*.png",
            "*.jpg",
            "*.gif",
            "*.ico",
        ],
        description="Files/patterns to ignore during CR",
    )

    cr_ignore_extensions: List[str] = Field(
        default=[
            ".md",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".txt",
            ".log",
        ],
        description="File extensions to ignore during CR",
    )

    # Security settings
    webhook_secret: str | None = Field(None, description="Secret for webhook verification")

    # Rate limiting
    rate_limit_per_minute: int = 10


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
