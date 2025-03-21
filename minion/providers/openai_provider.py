from typing import List, Optional, Dict

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
            prepared_msg = {"role": msg.role}
            
            # 处理消息内容
            if isinstance(msg.content, str):
                prepared_msg["content"] = msg.content
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
                prepared_msg["content"] = content
            else:
                # 处理现有的 MessageContent 情况
                if msg.content.type == ContentType.TEXT:
                    prepared_msg["content"] = msg.content.text
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
                    prepared_msg["content"] = content
            
            # 确保function或tool消息包含name字段
            if msg.role in ["function", "tool"]:
                if hasattr(msg, "name") and msg.name:
                    prepared_msg["name"] = msg.name
                else:
                    # 如果缺少name，添加一个默认值避免API错误
                    prepared_msg["name"] = "function_call"
                    print(f"Warning: Adding missing 'name' field to '{msg.role}' message")
            
            # 处理tool_calls字段
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                prepared_msg["tool_calls"] = msg.tool_calls
            
            # 处理tool_call_id字段
            if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                prepared_msg["tool_call_id"] = msg.tool_call_id
                
            prepared_messages.append(prepared_msg)
            
        return prepared_messages

    def _prepare_tools(self, tools: List[Dict]) -> List[Dict]:
        """
        将工具格式转换为OpenAI API所需的格式
        
        Args:
            tools: 原始工具列表
            
        Returns:
            List[Dict]: 格式化后的工具列表
        """
        if not tools:
            return None
            
        prepared_tools = []
        for tool in tools:
            # 如果已经是OpenAI格式（包含type和function字段），则直接使用
            if 'type' in tool and 'function' in tool:
                prepared_tools.append(tool)
            else:
                # 如果是minion格式（没有type和function嵌套），则转换为OpenAI格式
                function_data = {}
                # 提取工具的基本信息
                for key in ["name", "description", "parameters"]:
                    if key in tool:
                        function_data[key] = tool[key]
                
                # 确保有必要的字段
                if "name" in function_data and "description" in function_data:
                    prepared_tools.append({
                        "type": "function",
                        "function": function_data
                    })
        
        return prepared_tools if prepared_tools else None

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        prepared_messages = self._prepare_messages(messages)
        model = self.config.model
        
        # 处理tools参数
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools
        
        response = await self.client.chat.completions.create(
            model=model, messages=prepared_messages, temperature=temperature or self.config.temperature, **kwargs
        )

        completion_tokens = response.usage.completion_tokens
        prompt_tokens, _ = CostManager.calculate(prepared_messages, completion_tokens, model)
        self.cost_manager.update_cost(prompt_tokens, completion_tokens, model)

        # 处理可能的工具调用
        if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
            # 如果是工具调用，返回工具调用信息
            return response.choices[0].message.tool_calls
        
        # 正常返回内容
        return response.choices[0].message.content or ""

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        prepared_messages = self._prepare_messages(messages)
        model = self.config.model
        
        # 处理tools参数
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools
        
        stream = await self.client.chat.completions.create(
            model=model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            stream=True,
            **kwargs,
        )

        completion_tokens = 0
        full_content = ""
        tool_calls_chunks = []
        
        async for chunk in stream:
            if chunk.choices:
                # 检查是否有工具调用
                if hasattr(chunk.choices[0].delta, 'tool_calls') and chunk.choices[0].delta.tool_calls:
                    # 处理工具调用流
                    tool_calls_chunks.append(chunk.choices[0].delta.tool_calls)
                    completion_tokens += 1
                    log_llm_stream(f"[Tool Call Chunk]: {chunk.choices[0].delta.tool_calls}")
                
                # 处理常规内容
                elif chunk.choices[0].delta.content is not None:
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

        # 如果有工具调用，返回工具调用
        if tool_calls_chunks:
            # 构建完整的工具调用对象
            # 定义一个简单的类来表示工具调用
            class ToolCall:
                def __init__(self, id, type, function):
                    self.id = id
                    self.type = type
                    self.function = function
            
            class Function:
                def __init__(self, name, arguments):
                    self.name = name
                    self.arguments = arguments
            
            # 根据工具调用的ID对工具调用进行分组和合并
            tool_call_dict = {}
            
            for chunk_list in tool_calls_chunks:
                for tool_chunk in chunk_list:
                    id = tool_chunk.id
                    if id not in tool_call_dict:
                        tool_call_dict[id] = {
                            "id": id,
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        }
                    
                    if hasattr(tool_chunk.function, 'name') and tool_chunk.function.name:
                        tool_call_dict[id]["function"]["name"] = tool_chunk.function.name
                    
                    if hasattr(tool_chunk.function, 'arguments') and tool_chunk.function.arguments:
                        tool_call_dict[id]["function"]["arguments"] += tool_chunk.function.arguments
            
            # 将合并后的工具调用转换为我们自定义的ToolCall对象
            result_tool_calls = []
            for id, tc_data in tool_call_dict.items():
                function = Function(
                    name=tc_data["function"]["name"],
                    arguments=tc_data["function"]["arguments"]
                )
                tool_call = ToolCall(
                    id=id,
                    type=tc_data["type"],
                    function=function
                )
                result_tool_calls.append(tool_call)
            
            return result_tool_calls
            
        return full_content

    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion from messages synchronously"""
        prepared_messages = self._prepare_messages(messages)
        model = self.config.model

        # 处理tools参数
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools

        response = self.client_sync.chat.completions.create(
            model=model, 
            messages=prepared_messages, 
            temperature=temperature or self.config.temperature, 
            **kwargs
        )

        completion_tokens = response.usage.completion_tokens
        prompt_tokens, _ = CostManager.calculate(prepared_messages, completion_tokens, model)
        self.cost_manager.update_cost(prompt_tokens, completion_tokens, model)

        # 处理可能的工具调用
        if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
            # 如果是工具调用，返回工具调用信息
            return response.choices[0].message.tool_calls
            
        # 正常返回内容
        return response.choices[0].message.content or ""


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
