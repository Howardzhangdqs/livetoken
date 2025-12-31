"""配置管理模块

支持两种配置方式，优先级从高到低：
1. 环境变量
2. 配置文件 (config.toml)
3. 代码默认值
"""
import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


def _load_config_file() -> dict[str, Any]:
    """加载配置文件 config.toml"""
    config_path = Path("config.toml")
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _get_from_config_or_env(config_key: str, env_key: str, default: str) -> str:
    """从配置文件或环境变量获取值，环境变量优先"""
    # 优先环境变量
    env_value = os.getenv(env_key)
    if env_value:
        return env_value

    # 其次配置文件
    config = _load_config_file()
    value = config.get(config_key, default)
    return str(value) if value else default


class Settings(BaseSettings):
    """应用配置"""

    # 服务端口
    port: int = int(os.getenv("LIVETOKEN_PORT", "7357"))

    # Anthropic API 上游地址
    anthropic_base_url: str = os.getenv(
        "ANTHROPIC_BASE_URL",
        _get_from_config_or_env("anthropic_base_url", "ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    )

    # OpenAI API 上游地址
    openai_base_url: str = os.getenv(
        "OPENAI_BASE_URL",
        _get_from_config_or_env("openai_base_url", "OPENAI_BASE_URL", "https://api.openai.com")
    )

    # 默认 API Key (可选，用于转发时添加认证)
    api_key: str | None = os.getenv(
        "API_KEY",
        _get_from_config_or_env("api_key", "API_KEY", "")
    ) or None

    # 是否启用 Rich Console 终端输出
    enable_console: bool = os.getenv("ENABLE_CONSOLE", "true").lower() == "true"

    # 最大历史记录数
    max_history: int = int(os.getenv("MAX_HISTORY", "100"))


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
