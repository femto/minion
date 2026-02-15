"""
Strong-typed LLM configuration for agents
"""
from __future__ import annotations
from enum import Enum
from typing import Union, Optional, Dict
from dataclasses import dataclass

from ..configs.config import LLMConfig
from ..providers.base_provider import BaseProvider


@dataclass
class AgentLLMConfig:
    """
    Configuration for agent LLM setup with primary and specialized models
    """
    primary_model: Union[ModelType, str]
    specialized_models: Optional[Dict[str, Union[ModelType, str]]] = None
    
    def get_model_for_task(self, task_type: str) -> Union[ModelType, str]:
        """
        Get the appropriate model for a specific task type
        
        Args:
            task_type: Type of task (e.g., "code", "math", "creative", "fast")
            
        Returns:
            Model to use for the task, falls back to primary_model if not found
        """
        if self.specialized_models and task_type in self.specialized_models:
            return self.specialized_models[task_type]
        return self.primary_model
    
    def get_available_models(self) -> Dict[str, Union[ModelType, str]]:
        """
        Get all available models including primary and specialized
        
        Returns:
            Dictionary mapping model names to model types
        """
        models = {"primary": self.primary_model}
        if self.specialized_models:
            models.update(self.specialized_models)
        return models
    
    def create_llm_provider(self, task_type: Optional[str] = None) -> BaseProvider:
        """
        Create LLM provider for a specific task type
        
        Args:
            task_type: Type of task, uses primary model if None
            
        Returns:
            BaseProvider instance for the appropriate model
        """
        model = self.get_model_for_task(task_type) if task_type else self.primary_model
        return create_llm_from_model(model)


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

    # Handle pseudo model specially - return a pseudo LLMConfig
    if model_name == "pseudo":
        return LLMConfig(api_type="pseudo", model="pseudo")

    llm_config = config.models.get(model_name)
    if not llm_config:
        # Return pseudo config for any missing model instead of raising error
        from loguru import logger
        logger.warning(f"Model '{model_name}' not found in configuration. Using pseudo provider.")
        return LLMConfig(api_type="pseudo", model="pseudo")

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

    # Handle pseudo model specially - return the pseudo provider
    if isinstance(model, str) and model == "pseudo":
        from ..providers.pseudo_provider import get_pseudo_provider
        return get_pseudo_provider()

    # Otherwise, create from config
    llm_config = get_model_config(model)
    return create_llm_provider(llm_config)

