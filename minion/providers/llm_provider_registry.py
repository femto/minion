import importlib
from typing import Type

from minion.configs.config import LLMConfig
from minion.providers.base_provider import BaseProvider


class LLMRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMRegistry, cls).__new__(cls)
            cls._instance.providers = {}
        return cls._instance

    def register(self, api_type: str):
        def decorator(cls):
            self.providers[api_type] = f"{cls.__module__}.{cls.__name__}"
            return cls

        return decorator

    def get_provider(self, api_type: str) -> Type[BaseProvider]:
        if api_type not in self.providers:
            # 尝试动态导入
            try:
                importlib.import_module(f"minion.providers.{api_type}_provider")
            except ImportError:
                raise ValueError(f"Unknown API type: {api_type}")

        if api_type not in self.providers:
            raise ValueError(f"No provider found for API type: {api_type}")

        module_path, class_name = self.providers[api_type].rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)


llm_registry = LLMRegistry()


def create_llm_provider(config: LLMConfig) -> BaseProvider:
    provider_cls = llm_registry.get_provider(config.api_type)
    return provider_cls(config)
