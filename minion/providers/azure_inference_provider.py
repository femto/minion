from typing import List, Optional, Dict, Any
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential

from minion.logs import log_llm_stream
from minion.providers.base_provider import BaseProvider
from minion.providers.llm_provider_registry import llm_registry
from minion.schema.message_types import Message, MessageContent, ContentType
from minion.providers.openai_provider import OpenAIProvider


@llm_registry.register("azure_inference")
class AzureInferenceProvider(OpenAIProvider):
    def _setup(self) -> None:
        """Setup Azure Inference SDK client"""
        endpoint = self.config.base_url
        key = self.config.api_key
        self.model = self.config.model or self.config.deployment_name
        
        self.client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
        # Also use the same client for sync operations since Azure Inference SDK
        # doesn't have separate sync/async clients
        self.client_sync = self.client

    # def _prepare_messages(self, messages: List[Message] | Message | str) -> List[Any]:
    #     """Convert minion Message objects to Azure Inference SDK message objects"""
    #     # Convert single message or string to list
    #     if isinstance(messages, (str, Message)):
    #         messages = [messages if isinstance(messages, Message) else Message(role="user", content=messages)]
    #
    #     azure_messages = []
    #     for msg in messages:
    #         content = msg.content
    #         if isinstance(content, str):
    #             text_content = content
    #         elif isinstance(content, MessageContent):
    #             if content.type == ContentType.TEXT:
    #                 text_content = content.text
    #             else:
    #                 # For now, we only handle text content for Azure Inference
    #                 # TODO: Add support for image content if Azure Inference SDK supports it
    #                 text_content = content.text if content.text else ""
    #         else:
    #             text_content = str(content)
    #
    #         if msg.role == "system":
    #             azure_messages.append(SystemMessage(content=text_content))
    #         elif msg.role == "user":
    #             azure_messages.append(UserMessage(content=text_content))
    #         elif msg.role == "assistant":
    #             azure_messages.append(AssistantMessage(content=text_content))
    #     return azure_messages

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion using Azure Inference SDK"""
        azure_messages = self._prepare_messages(messages)
        
        # Prepare parameters
        params = {
            "messages": azure_messages,
            "model": self.model,
            "temperature": temperature if temperature is not None else 0.6,
            "max_tokens": kwargs.get("max_tokens", 1000)
        }
        
        # Add optional parameters if provided
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        if "frequency_penalty" in kwargs:
            params["frequency_penalty"] = kwargs["frequency_penalty"]
        if "presence_penalty" in kwargs:
            params["presence_penalty"] = kwargs["presence_penalty"]
        
        response = self.client.complete(**params)
        return response.messages[0].content

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate streaming completion using Azure Inference SDK"""
        azure_messages = self._prepare_messages(messages)
        
        # Prepare parameters
        params = {
            "messages": azure_messages,
            "model": self.model,
            "temperature": temperature if temperature is not None else 0.6,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "stream": True
        }
        
        # Add optional parameters if provided
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        if "frequency_penalty" in kwargs:
            params["frequency_penalty"] = kwargs["frequency_penalty"]
        if "presence_penalty" in kwargs:
            params["presence_penalty"] = kwargs["presence_penalty"]
        
        response = self.client.complete(**params)
        full_content = ""
        completion_tokens = 0
        for chunk in response:
            if chunk.choices:
                completion_tokens += 1
                chunk_message = chunk.choices[0].delta.content
                if chunk_message:
                    full_content += chunk_message
                    log_llm_stream(chunk_message)
                #yield chunk_message
        return full_content
        
    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion synchronously using Azure Inference SDK"""
        azure_messages = self._prepare_messages(messages)
        
        # Prepare parameters
        params = {
            "messages": azure_messages,
            "model": self.model,
            "temperature": temperature if temperature is not None else 0.6,
            "max_tokens": kwargs.get("max_tokens", 1000)
        }
        
        # Add optional parameters if provided
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        if "frequency_penalty" in kwargs:
            params["frequency_penalty"] = kwargs["frequency_penalty"]
        if "presence_penalty" in kwargs:
            params["presence_penalty"] = kwargs["presence_penalty"]
        
        response = self.client_sync.complete(**params)
        return response.messages[0].content