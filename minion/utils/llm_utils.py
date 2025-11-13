"""
Utility functions for LLM configuration and management
"""
from typing import Dict, Union, Optional
from ..types.llm_types import ModelType, AgentLLMConfig, create_llm_from_model
from ..providers.base_provider import BaseProvider

#some hint about using different llms for different tasks.
#AgentLLMConfig is now implemented in minion.types.llm_types

def create_agent_llm_config(
        primary: Union[ModelType, str] = ModelType.GPT_4O,
        code: Optional[Union[ModelType, str]] = None,
        math: Optional[Union[ModelType, str]] = None,
        creative: Optional[Union[ModelType, str]] = None,
        fast: Optional[Union[ModelType, str]] = None,
        **specialized_models
) -> AgentLLMConfig:
    """
    Create AgentLLMConfig with common specialized models

    Args:
        primary: Primary model for general tasks
        code: Model for coding tasks (defaults to DEEPSEEK_R1)
        math: Model for mathematical tasks (defaults to PHI_4)
        creative: Model for creative tasks (defaults to GEMINI_2_0_FLASH_EXP)
        fast: Model for quick responses (defaults to GPT_4O_MINI)
        **specialized_models: Additional specialized models

    Returns:
        AgentLLMConfig: Configured LLM setup
    """
    specialized = {}

    # Add common specialized models if specified
    if code is not None:
        specialized["code"] = code
    elif code is None and primary != ModelType.DEEPSEEK_R1:
        specialized["code"] = ModelType.DEEPSEEK_R1

    if math is not None:
        specialized["math"] = math
    elif math is None and primary != ModelType.PHI_4:
        specialized["math"] = ModelType.PHI_4

    if creative is not None:
        specialized["creative"] = creative
    elif creative is None and primary != ModelType.GEMINI_2_0_FLASH_EXP:
        specialized["creative"] = ModelType.GEMINI_2_0_FLASH_EXP

    if fast is not None:
        specialized["fast"] = fast
    elif fast is None and primary != ModelType.GPT_4O_MINI:
        specialized["fast"] = ModelType.GPT_4O_MINI

    # Add any additional specialized models
    specialized.update(specialized_models)

    return AgentLLMConfig(
        primary_model=primary,
        specialized_models=specialized if specialized else None
    )


def get_recommended_model_for_task(task_description: str) -> ModelType:
    """
    Get recommended model based on task description

    Args:
        task_description: Description of the task

    Returns:
        ModelType: Recommended model for the task
    """
    task_lower = task_description.lower()

    # Code-related tasks
    if any(keyword in task_lower for keyword in [
        "code", "program", "function", "class", "debug", "python", "javascript",
        "java", "c++", "programming", "algorithm", "software", "api"
    ]):
        return ModelType.DEEPSEEK_R1

    # Math-related tasks
    elif any(keyword in task_lower for keyword in [
        "math", "calculate", "equation", "solve", "number", "statistics",
        "probability", "algebra", "geometry", "calculus", "formula"
    ]):
        return ModelType.PHI_4

    # Creative tasks
    elif any(keyword in task_lower for keyword in [
        "creative", "story", "poem", "art", "imagine", "design", "brainstorm",
        "creative writing", "narrative", "fiction", "artistic"
    ]):
        return ModelType.GEMINI_2_0_FLASH_EXP

    # Quick/simple tasks
    elif any(keyword in task_lower for keyword in [
        "quick", "fast", "simple", "brief", "short", "summarize", "list"
    ]):
        return ModelType.GPT_4O_MINI

    # Default to GPT-4O for general tasks
    else:
        return ModelType.GPT_4O


def create_multi_model_dict(
        primary: Union[ModelType, str] = ModelType.GPT_4O,
        include_common: bool = True,
        **additional_models
) -> Dict[str, Union[ModelType, str]]:
    """
    Create a dictionary of models for the llms parameter

    Args:
        primary: Primary model (not included in the dict)
        include_common: Whether to include common specialized models
        **additional_models: Additional models to include

    Returns:
        Dict mapping model names to model types
    """
    models = {}

    if include_common:
        models.update({
            "code": ModelType.DEEPSEEK_R1,
            "math": ModelType.PHI_4,
            "creative": ModelType.GEMINI_2_0_FLASH_EXP,
            "fast": ModelType.GPT_4O_MINI
        })

        # Remove primary model from specialized if it's the same
        models = {k: v for k, v in models.items() if v != primary}

    models.update(additional_models)
    return models


# Convenience constants for common configurations
CODING_AGENT_CONFIG = AgentLLMConfig(
    primary_model=ModelType.DEEPSEEK_R1,
    specialized_models={
        "general": ModelType.GPT_4O,
        "fast": ModelType.GPT_4O_MINI
    }
)

CREATIVE_AGENT_CONFIG = AgentLLMConfig(
    primary_model=ModelType.GEMINI_2_0_FLASH_EXP,
    specialized_models={
        "general": ModelType.GPT_4O,
        "fast": ModelType.GPT_4O_MINI
    }
)

MATH_AGENT_CONFIG = AgentLLMConfig(
    primary_model=ModelType.PHI_4,
    specialized_models={
        "general": ModelType.GPT_4O,
        "fast": ModelType.GPT_4O_MINI
    }
)

BALANCED_AGENT_CONFIG = AgentLLMConfig(
    primary_model=ModelType.GPT_4O,
    specialized_models={
        "code": ModelType.DEEPSEEK_R1,
        "math": ModelType.PHI_4,
        "creative": ModelType.GEMINI_2_0_FLASH_EXP,
        "fast": ModelType.GPT_4O_MINI
    }
)