import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict

from minion.const import MINION_ROOT


class APIType(str, Enum):
    OPENAI = "openai"
    LITELLM = "litellm"
    AZURE = "azure"
    OLLAMA = "ollama"
    GROQ = "groq"


class ContentType(str, Enum):
    TEXT = "text"
    IMAGE_URL = "image_url"
    IMAGE_BASE64 = "image_base64"


class ImageDetail(str, Enum):
    AUTO = "auto"
    LOW = "low"
    HIGH = "high"


class LLMConfig(BaseModel):
    api_type: str = "openai"
    api_key: str = ""  # For most providers
    access_key_id: Optional[str] = None  # For AWS Bedrock
    secret_access_key: Optional[str] = None  # For AWS Bedrock
    api_version: Optional[str] = None
    # base_url: Optional[HttpUrl] = None
    base_url: Optional[str] = None
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4000
    vision_enabled: bool = False
    region: Optional[str] = None  # For AWS Bedrock and other cloud providers

    model_config = ConfigDict(use_enum_values=True)


class EllConfig(BaseModel):
    store: str = 'logs'
    autocommit: bool = True
    verbose: bool = True


class Config(BaseModel):
    environment: Dict[str, str] = Field(default_factory=dict)
    env_file: List[str] = Field(default_factory=list)
    llm: LLMConfig
    models: Dict[str, LLMConfig]
    ell: Dict[str, Any] = Field(default_factory=dict)
    mem0: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


@lru_cache()
def get_config():
    return load_config()


def _get_env_var_config() -> Dict[str, Any]:
    """Build config from environment variables when no config file exists."""
    # Check for common API keys in environment
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    models: Dict[str, Any] = {}
    default_model = None

    # Add OpenAI models if key exists
    if openai_key:
        models["gpt-4o"] = {
            "api_type": "openai",
            "api_key": openai_key,
            "model": "gpt-4o",
        }
        models["gpt-4o-mini"] = {
            "api_type": "openai",
            "api_key": openai_key,
            "model": "gpt-4o-mini",
        }
        default_model = "gpt-4o"

    # Add Anthropic models if key exists (via litellm)
    if anthropic_key:
        models["claude-sonnet-4-20250514"] = {
            "api_type": "litellm",
            "api_key": anthropic_key,
            "model": "claude-sonnet-4-20250514",
        }
        models["claude-3-5-sonnet"] = {
            "api_type": "litellm",
            "api_key": anthropic_key,
            "model": "claude-3-5-sonnet-20241022",
        }
        if not default_model:
            default_model = "claude-sonnet-4-20250514"

    if not models:
        return {}

    return {
        "models": models,
        "llm": models.get(default_model, next(iter(models.values()))),
    }


def load_config(root_path: Optional[Path] = None, override_env: bool = False):
    root_path = root_path or MINION_ROOT
    base_config_path = root_path / "config/config.yaml"
    user_config_path = Path.home() / ".minion/config.yaml"

    config_dict: Dict[str, Any] = {}

    # 首先加载用户配置
    if user_config_path.exists():
        with user_config_path.open("r") as f:
            config_dict = yaml.safe_load(f) or {}

        # 加载用户配置中指定的 env_file
        load_env_files(user_config_path.parent, config_dict.get("env_file", []), override_env)

    # 然后加载基础配置，覆盖用户配置
    if base_config_path.exists():
        with base_config_path.open("r") as f:
            base_config = yaml.safe_load(f) or {}

        # 加载基础配置中指定的 env_file
        load_env_files(base_config_path.parent, base_config.get("env_file", []), override_env)

        config_dict.update(base_config)

    # If no config files found, try to build from environment variables
    if not config_dict or "models" not in config_dict:
        env_config = _get_env_var_config()
        if env_config:
            config_dict.update(env_config)

    # 设置 environment 中指定的环境变量
    for key, value in config_dict.get("environment", {}).items():
        if override_env or key not in os.environ:
            os.environ[key] = process_env_var(value)

    # 处理配置中的环境变量
    config_dict = process_env_vars(config_dict)

    if "models" in config_dict:
        for key, model_config in config_dict["models"].items():
            if "model" not in model_config:
                model_config["model"] = key

    if "llm" not in config_dict:
        config_dict["llm"] = config_dict.get("models", {}).get("default", next(iter(config_dict.get("models", {}).values()), {}))

    # 确保 ell 配置存在，如果不存在则使用默认值
    if "ell" not in config_dict:
        config_dict["ell"] = {
            "store": 'logs',
            "autocommit": True,
            "verbose": True
        }

    return Config(**config_dict)


def load_env_files(base_path: Path, env_files: List[str], override: bool = False):
    for env_file in env_files:
        env_path = base_path / env_file
        if env_path.exists():
            load_dotenv(env_path, override=override)


def process_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """递归处理配置字典，用环境变量替换值"""
    for key, value in config.items():
        if isinstance(value, dict):
            config[key] = process_env_vars(value)
        elif isinstance(value, str):
            config[key] = process_env_var(value)
    return config


def process_env_var(value: str) -> str:
    """处理单个环境变量值"""
    if value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, value)
    return value


config = load_config()


def reload_config(root_path: Optional[Path] = None, override_env: bool = False):
    global config
    config = load_config(root_path, override_env)


__all__ = ["config", "reload_config", "APIType", "ContentType", "ImageDetail", "LLMConfig", "Config"]

if __name__ == "__main__":
    print(f"配置加载完成，llm api_key: {config.llm.api_key[:5]}...")  # 只打印 api_key 的前5个字符
