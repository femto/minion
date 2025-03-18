import os
import warnings
from typing import AsyncIterator, List, Optional

from minion.schema.message_types import ContentType, Message

from minion.providers.base_provider import BaseProvider
from minion.providers.llm_provider_registry import llm_registry

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import litellm


os.environ["LITELLM_LOG"] = "DEBUG"


@llm_registry.register("litellm")
class LiteLLMProvider(BaseProvider):
    def _setup(self) -> None:
        # 设置API密钥
        os.environ["OPENAI_API_KEY"] = self.config.api_key

        # 如果有自定义base_url，设置它
        if self.config.base_url:
            litellm.api_base = str(self.config.base_url)

    def _prepare_messages(self, messages: List[Message]) -> List[dict]:
        """准备发送给API的消息格式"""
        prepared_messages = []
        for msg in messages:
            if isinstance(msg.content, str):
                prepared_messages.append({"role": msg.role, "content": msg.content})
            else:
                content = msg.content.text or ""
                if msg.content.type == ContentType.IMAGE_BASE64 and msg.content.image:
                    content = [
                        {"type": "text", "text": content},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{msg.content.image.data}",
                                "detail": msg.content.image.detail,
                            },
                        },
                    ]
                prepared_messages.append({"role": msg.role, "content": content})
        return prepared_messages

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        prepared_messages = self._prepare_messages(messages)

        response = await litellm.acompletion(
            model=self.config.model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            **kwargs,
        )
        return response.choices[0].message.content

    async def generate_stream(
        self, messages: List[Message], temperature: Optional[float] = None, **kwargs
    ) -> AsyncIterator[str]:
        prepared_messages = self._prepare_messages(messages)

        async for chunk in litellm.acompletion(
            model=self.config.model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            stream=True,
            **kwargs,
        ):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
