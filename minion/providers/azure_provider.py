from typing import List, Optional

from minion.providers.openai_provider import OpenAIProvider
from minion.providers.llm_provider_registry import llm_registry
from minion.schema.message_types import Message


@llm_registry.register("azure")
class AzureProvider(OpenAIProvider):
    def _setup(self) -> None:
        import openai
        
        # Azure OpenAI 需要特定的配置
        client_kwargs = {
            "api_key": self.config.api_key,
            "azure_endpoint": self.config.base_url,  # Azure 使用 endpoint 而不是 base_url
            "api_version": self.config.api_version or "2024-05-01-preview",  # Azure 需要 api_version
        }
        
        # Azure OpenAI 使用 azure_deployment_name 而不是 model
        if hasattr(self.config, "deployment_name"):
            client_kwargs["azure_deployment"] = self.config.deployment_name
        else:
            client_kwargs["azure_deployment"] = self.config.model
            
        self.client_sync = openai.AzureOpenAI(**client_kwargs)
        self.client = openai.AsyncAzureOpenAI(**client_kwargs)

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        # 移除 model 参数，因为 Azure 使用 deployment_name
        #kwargs.pop("model", None)
        return await super().generate(messages, temperature, **kwargs)

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        # 移除 model 参数，因为 Azure 使用 deployment_name
        #kwargs.pop("model", None)
        return await super().generate_stream(messages, temperature, **kwargs)
        
    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        # 移除 model 参数，因为 Azure 使用 deployment_name
        #kwargs.pop("model", None)
        return super().generate_sync(messages, temperature, **kwargs) 