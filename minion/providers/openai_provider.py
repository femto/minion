from typing import List, Optional

from openai.types import CompletionUsage

from minion.configs.config import ContentType, ImageDetail, config
from minion.const import MINION_ROOT
from minion.logs import log_llm_stream
from minion.schema.message_types import ImageContent, ImageUtils, Message, MessageContent
from minion.providers.base_provider import BaseProvider

from minion.providers.cost import CostManager
from minion.providers.llm_provider_registry import llm_registry


@llm_registry.register("openai")
class OpenAIProvider(BaseProvider):
    def _setup(self) -> None:
        import openai
        # 创建客户端配置
        client_kwargs = {"api_key": self.config.api_key}
        if self.config.base_url:
            client_kwargs["base_url"] = str(self.config.base_url)
        
        self.client_sync = openai.OpenAI(**client_kwargs)
        self.client = openai.AsyncOpenAI(**client_kwargs)

    #or should we call _convert_messages
    def _prepare_messages(self, messages: List[Message] | Message | str) -> List[dict]:
        """准备发送给API的消息格式
        
        Args:
            messages: 可以是消息列表、单个消息或字符串
        Returns:
            List[dict]: OpenAI API所需的消息格式
        """
        # 统一转换为列表格式处理
        if isinstance(messages, (str, Message)):
            messages = [messages if isinstance(messages, Message) else Message(role="user", content=messages)]
        
        prepared_messages = []
        for msg in messages:
            if isinstance(msg.content, str):
                prepared_messages.append({"role": msg.role, "content": msg.content})
            elif isinstance(msg.content, list):
                # 处理content为列表的情况
                content = []
                for item in msg.content:
                    if isinstance(item, str):
                        content.append({"type": "text", "text": item})
                    elif hasattr(item, 'type'):
                        if item.type == ContentType.TEXT:
                            content.append({"type": "text", "text": item.text})
                        elif item.type == ContentType.IMAGE_BASE64:
                            image_data = {
                                "type": "image_url",
                                "image_url": {"url": item.image.data, "detail": item.image.detail},
                            }
                            content.append(image_data)
                prepared_messages.append({"role": msg.role, "content": content})
            else:
                # 处理现有的 MessageContent 情况
                if msg.content.type == ContentType.TEXT:
                    prepared_messages.append({"role": msg.role, "content": msg.content.text})
                else:
                    # 处理包含图像的消息
                    content = []
                    if msg.content.text:
                        content.append({"type": "text", "text": msg.content.text})
                    if msg.content.image:
                        image_data = {
                            "type": "image_url",
                            "image_url": {"url": msg.content.image.data, "detail": msg.content.image.detail},
                        }
                        content.append(image_data)
                    prepared_messages.append({"role": msg.role, "content": content})
        return prepared_messages

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        prepared_messages = self._prepare_messages(messages)
        model = self.config.model

        response = await self.client.chat.completions.create(
            model=model, messages=prepared_messages, temperature=temperature or self.config.temperature, **kwargs
        )

        completion_tokens = response.usage.completion_tokens
        prompt_tokens, _ = CostManager.calculate(prepared_messages, completion_tokens, model)
        self.cost_manager.update_cost(prompt_tokens, completion_tokens, model)

        return response.choices[0].message.content

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        prepared_messages = self._prepare_messages(messages)
        model = self.config.model
        stream = await self.client.chat.completions.create(
            model=model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            stream=True,
            **kwargs,
        )

        completion_tokens = 0
        full_content = ""
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                finish_reason = (
                    chunk.choices[0].finish_reason if chunk.choices and hasattr(chunk.choices[0],
                                                                                "finish_reason") else None
                )
                if finish_reason:
                    if hasattr(chunk, "usage") and chunk.usage is not None:
                        # Some services have usage as an attribute of the chunk, such as Fireworks
                        if isinstance(chunk.usage, CompletionUsage):
                            usage = chunk.usage
                        else:
                            usage = CompletionUsage(**chunk.usage)
                    elif hasattr(chunk.choices[0], "usage"):
                        # The usage of some services is an attribute of chunk.choices[0], such as Moonshot
                        usage = CompletionUsage(**chunk.choices[0].usage)
                    # elif "openrouter.ai" in self.config.base_url:
                    #     # due to it get token cost from api
                    #     usage = await get_openrouter_tokens(chunk)
                completion_tokens += 1
                chunk_message = chunk.choices[0].delta.content
                full_content += chunk_message
                log_llm_stream(chunk_message)

        prompt_tokens, _ = CostManager.calculate(prepared_messages, completion_tokens, model)
        self.cost_manager.update_cost(prompt_tokens, completion_tokens, model)

        return full_content

    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion from messages synchronously"""
        prepared_messages = self._prepare_messages(messages)
        model = self.config.model

        response = self.client_sync.chat.completions.create(
            model=model, 
            messages=prepared_messages, 
            temperature=temperature or self.config.temperature, 
            **kwargs
        )

        completion_tokens = response.usage.completion_tokens
        prompt_tokens, _ = CostManager.calculate(prepared_messages, completion_tokens, model)
        self.cost_manager.update_cost(prompt_tokens, completion_tokens, model)

        return response.choices[0].message.content


# 使用示例
async def main():
    llm = OpenAIProvider(config=config.models.get("gpt-4o-mini"))

    # 处理图像示例

    image_path = MINION_ROOT / "assets/robot.jpg"
    image_base64 = await ImageUtils.encode_image_to_base64(image_path)

    messages = [
        # Message(role="system", content="你是一个能理解图像的AI助手。"),
        Message(
            role="user",
            content=MessageContent(
                type=ContentType.IMAGE_BASE64,
                text="这张图片里有什么?",
                image=ImageContent(type="image_base64", data=image_base64, detail=ImageDetail.AUTO),
            ),
        )
    ]

    response = await llm.generate(messages)
    print(f"Response: {response}")
    print(f"Cost: ${llm.get_cost().total_cost:.6f}")

    # 对于流式生成
    async for chunk in llm.generate_stream(messages):
        print(chunk, end="", flush=True)
    print(f"\nFinal cost: ${llm.get_cost().total_cost:.6f}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
