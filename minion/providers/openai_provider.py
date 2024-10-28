from typing import List, Optional

from minion.configs.config import ContentType, ImageDetail, config
from minion.const import MINION_ROOT
from minion.message_types import ImageContent, ImageUtils, Message, MessageContent
from minion.providers.base_llm import BaseLLM
from minion.providers.cost import CostManager
from minion.providers.llm_provider_registry import llm_registry


@llm_registry.register("openai")
class OpenAIProvider(BaseLLM):
    def _setup(self) -> None:
        import openai
        self.client_ell = openai.OpenAI(api_key=self.config.api_key, base_url=str(self.config.base_url))
        self.client = openai.AsyncOpenAI(api_key=self.config.api_key, base_url=str(self.config.base_url))

    def _prepare_messages(self, messages: List[Message]) -> List[dict]:
        """准备发送给API的消息格式"""
        prepared_messages = []
        for msg in messages:
            if isinstance(msg.content, str):
                prepared_messages.append({"role": msg.role, "content": msg.content})
            else:
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
                completion_tokens += 1
                full_content += chunk.choices[0].delta.content

        prompt_tokens, _ = CostManager.calculate(prepared_messages, completion_tokens, model)
        self.cost_manager.update_cost(prompt_tokens, completion_tokens, model)

        return full_content


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
