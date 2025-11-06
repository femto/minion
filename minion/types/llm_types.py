"""
Strong-typed LLM configuration for agents
"""
from enum import Enum
from typing import Union

from ..configs.config import LLMConfig
from ..providers.base_provider import BaseProvider


class ModelType(str, Enum):
    """Supported model types with strong typing"""
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GEMINI_2_0_FLASH_EXP = "gemini-2.0-flash-exp"
    DEEPSEEK_R1 = "deepseek-r1"
    PHI_4 = "phi-4"
    LLAMA_3_2 = "llama3.2"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20240620"
    DEFAULT = "default"


def get_model_config(model: Union[ModelType, str]) -> LLMConfig:
    """
    Get LLM configuration for a model type
    
    Args:
        model: Model type or string identifier
        
    Returns:
        LLMConfig: Configuration for the specified model
    """
    from ..configs.config import config
    
    if isinstance(model, ModelType):
        model_name = model.value
    else:
        model_name = str(model)
    
    llm_config = config.models.get(model_name)
    if not llm_config:
        raise ValueError(f"Model '{model_name}' not found in configuration. Available models: {list(config.models.keys())}")
    
    return llm_config


def create_llm_from_model(model: Union[ModelType, str, BaseProvider]) -> BaseProvider:
    """
    Create LLM provider from model specification
    
    Args:
        model: Model type, string identifier, or existing provider instance
        
    Returns:
        BaseProvider: LLM provider instance
    """
    from ..providers.llm_provider_registry import create_llm_provider
    
    # If it's already a BaseProvider instance, return it directly
    if isinstance(model, BaseProvider):
        return model
    
    # Otherwise, create from config
    llm_config = get_model_config(model)
    return create_llm_provider(llm_config)