from typing import List, Optional, Dict, Any, AsyncIterator, Generator
import json

# Try to import aiobotocore with helpful error message
try:
    from aiobotocore.session import get_session
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError as e:
    raise ImportError(
        "aiobotocore is required for BedrockAsyncProvider. "
        "Install it with: pip install aiobotocore\n"
        "Or install the full package with bedrock support: pip install -e .[bedrock]"
    ) from e

from openai.types.chat import ChatCompletion

from minion.configs.config import ContentType, ImageDetail
from minion.logs import logger, log_llm_stream
from minion.schema.message_types import Message, MessageContent, ImageContent
from minion.providers.base_provider import BaseProvider
from minion.providers.llm_provider_registry import llm_registry


@llm_registry.register("bedrock_async")
class BedrockAsyncProvider(BaseProvider):
    """AWS Bedrock Async Provider for Claude models using aiobotocore"""

    def _setup(self) -> None:
        """Setup AWS Bedrock async client configuration"""
        try:
            # 获取 AWS 凭证（使用清晰的字段名）
            self.aws_access_key_id = getattr(self.config, 'access_key_id', None)
            self.aws_secret_access_key = getattr(self.config, 'secret_access_key', None)

            # 向后兼容：如果没有专门的 access_key_id，尝试从 api_key 中获取
            if not self.aws_access_key_id:
                api_key = getattr(self.config, 'api_key', None)
                if api_key and ':' in api_key:
                    self.aws_access_key_id, self.aws_secret_access_key = api_key.split(':', 1)
                elif api_key:
                    self.aws_access_key_id = api_key

            # 设置 AWS region，默认为 us-east-1
            self.region_name = getattr(self.config, 'region', 'us-east-1')

            # 确定模型ID
            self.model_id = getattr(self.config, 'model', 'anthropic.claude-3-5-sonnet-20240620-v1:0')

            # 创建 aiobotocore session
            self.session = get_session()

            logger.info(f"Initialized Bedrock Async provider with model: {self.model_id} in region: {self.region_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Bedrock Async provider: {e}")
            raise

    def _get_client_kwargs(self) -> Dict[str, Any]:
        """Get client kwargs for aiobotocore"""
        client_kwargs = {
            'service_name': 'bedrock-runtime',
            'region_name': self.region_name
        }

        # 只有在提供了凭证时才添加到参数中
        if self.aws_access_key_id:
            client_kwargs['aws_access_key_id'] = self.aws_access_key_id
        if self.aws_secret_access_key:
            client_kwargs['aws_secret_access_key'] = self.aws_secret_access_key

        return client_kwargs

    def _prepare_messages(self, messages: List[Message]) -> List[Dict]:
        """Convert Message objects to Bedrock Claude format"""
        bedrock_messages = []

        for message in messages:
            # Handle both Message objects and dict format
            if isinstance(message, Message):
                role = message.role
                content_str = message.content
            elif isinstance(message, dict):
                role = message.get("role", "")
                content_str = message.get("content", "")
            else:
                continue

            # Skip system messages for now (handled separately)
            if role == "system":
                continue

            # Only process user and assistant messages
            if role not in ["user", "assistant"]:
                continue

            # 处理消息内容
            content = []
            if isinstance(content_str, str):
                if content_str.strip():  # 确保不是完全空的内容
                    content.append({"type": "text", "text": content_str})
            elif isinstance(content_str, list):
                # Handle list content (could be from Message object)
                for item in content_str:
                    if isinstance(item, MessageContent):
                        if item.type == ContentType.TEXT:
                            if item.content.strip():
                                content.append({"type": "text", "text": item.content})
                        elif item.type == ContentType.IMAGE and isinstance(item.content, ImageContent):
                            # 处理图片内容
                            if item.content.image_type == "base64":
                                content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": f"image/{item.content.image_format}",
                                        "data": item.content.data
                                    }
                                })
                    elif isinstance(item, dict):
                        # Handle dict format content
                        if item.get("type") == "text" and item.get("text", "").strip():
                            content.append(item)
                        elif item.get("type") == "image":
                            content.append(item)
                    elif isinstance(item, str) and item.strip():
                        # Handle plain string in list
                        content.append({"type": "text", "text": item})

            # 只有在有内容时才添加消息
            if content:
                bedrock_messages.append({
                    "role": role,
                    "content": content
                })

        return bedrock_messages

    def _extract_system_message(self, messages: List[Message]) -> Optional[str]:
        """Extract system message from messages list"""
        for message in messages:
            # Handle both Message objects and dict format
            if isinstance(message, Message):
                role = message.role
                content = message.content
            elif isinstance(message, dict):
                role = message.get("role", "")
                content = message.get("content", "")
            else:
                continue

            if role == "system":
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # 连接所有文本内容
                    texts = []
                    for item in content:
                        if isinstance(item, MessageContent) and item.type == ContentType.TEXT:
                            texts.append(item.content)
                        elif isinstance(item, dict) and item.get("type") == "text":
                            texts.append(item.get("text", ""))
                        elif isinstance(item, str):
                            texts.append(item)
                    return " ".join(texts)
        return None

    def _create_request_body(self, messages: List[Message], temperature: Optional[float] = None,
                           max_tokens: int = 4096, **kwargs) -> Dict:
        """Create request body for Bedrock Claude API"""
        bedrock_messages = self._prepare_messages(messages)
        system_message = self._extract_system_message(messages)

        # 过滤掉system消息，只保留user和assistant
        filtered_messages = [msg for msg in bedrock_messages if msg["role"] in ["user", "assistant"]]

        # 确保至少有一条消息
        if not filtered_messages:
            raise ValueError("At least one user or assistant message is required")

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": filtered_messages,
            "max_tokens": max_tokens,
        }

        if system_message:
            request_body["system"] = system_message

        if temperature is not None:
            request_body["temperature"] = temperature
        elif hasattr(self.config, 'temperature'):
            request_body["temperature"] = self.config.temperature

        # 添加其他参数
        if "top_p" in kwargs:
            request_body["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            request_body["top_k"] = kwargs["top_k"]

        # 处理stop参数 - Bedrock使用stop_sequences
        if "stop" in kwargs and kwargs["stop"]:
            stop_sequences = kwargs["stop"]
            if isinstance(stop_sequences, str):
                stop_sequences = [stop_sequences]
            request_body["stop_sequences"] = stop_sequences

        return request_body

    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion synchronously - not recommended, use generate() instead"""
        import asyncio

        # 创建新的事件循环来运行async方法
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.generate(messages, temperature, **kwargs))

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion asynchronously"""
        try:
            request_body = self._create_request_body(messages, temperature, **kwargs)

            async with self.session.create_client(**self._get_client_kwargs()) as client:
                response = await client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )

                # 读取响应体
                response_body_bytes = await response['body'].read()
                response_body = json.loads(response_body_bytes)

                # 记录token使用情况
                if 'usage' in response_body:
                    usage = response_body['usage']
                    self.cost_manager.update_cost(
                        prompt_tokens=usage.get('input_tokens', 0),
                        completion_tokens=usage.get('output_tokens', 0),
                        model=self.model_id
                    )

                # 提取文本内容
                content = response_body.get('content', [])
                if content and isinstance(content, list):
                    for item in content:
                        if item.get('type') == 'text':
                            return item.get('text', '')

                return ""

        except ClientError as e:
            logger.error(f"Bedrock async client error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating completion: {e}")
            raise

    async def generate_stream_response(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> ChatCompletion:
        """
        Generate streaming completion from messages, returning a response object

        Args:
            messages: List of Message objects
            temperature: Temperature for generation
            **kwargs: Additional parameters

        Returns:
            ChatCompletion: A ChatCompletion object with choices, usage, etc.
        """
        try:
            request_body = self._create_request_body(messages, temperature, **kwargs)

            # 获取 stop_sequences 用于客户端检测
            # Bedrock 流式 API 可能不会严格遵守 stop_sequences，需要客户端检测
            stop_sequences = request_body.get('stop_sequences', [])

            async with self.session.create_client(**self._get_client_kwargs()) as client:
                # Bedrock支持流式调用
                response = await client.invoke_model_with_response_stream(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )

                full_content = ""
                input_tokens = 0
                output_tokens = 0
                stopped_by_sequence = False
                finish_reason = "stop"
                response_body = response['body']

                async for event in response_body:
                    if 'chunk' in event:
                        chunk = json.loads(event['chunk']['bytes'])

                        if chunk.get('type') == 'content_block_delta':
                            delta = chunk.get('delta', {})
                            if delta.get('type') == 'text_delta':
                                text = delta.get('text', '')
                                full_content += text
                                log_llm_stream(text)

                                # 客户端检测 stop sequence
                                # Bedrock 流式 API 可能不会在 stop sequence 处停止，需要手动检测
                                for stop_seq in stop_sequences:
                                    if stop_seq in full_content:
                                        # 截断到 stop sequence（包含 stop sequence 本身）
                                        idx = full_content.find(stop_seq)
                                        full_content = full_content[:idx + len(stop_seq)]
                                        stopped_by_sequence = True
                                        finish_reason = "stop_sequence"
                                        logger.info(f"[STOP_SEQ] Client-side stop sequence detected: '{stop_seq}', truncating response")
                                        break

                                if stopped_by_sequence:
                                    break

                        elif chunk.get('type') == 'message_stop':
                            # 记录token使用情况
                            usage = chunk.get('amazon-bedrock-invocationMetrics', {})
                            if usage:
                                input_tokens = usage.get('inputTokenCount', 0)
                                output_tokens = usage.get('outputTokenCount', 0)
                                self.cost_manager.update_cost(
                                    prompt_tokens=input_tokens,
                                    completion_tokens=output_tokens,
                                    model=self.model_id
                                )
                            break

                    if stopped_by_sequence:
                        break

                # 如果提前退出循环，需要关闭流以避免 "Unclosed connection" 警告
                if stopped_by_sequence:
                    # AioEventStream._raw_stream 直接是 aiohttp.ClientResponse
                    try:
                        if hasattr(response_body, '_raw_stream'):
                            aiohttp_response = response_body._raw_stream
                            # 先释放连接，再关闭
                            if hasattr(aiohttp_response, 'release'):
                                aiohttp_response.release()
                            if hasattr(aiohttp_response, 'close'):
                                aiohttp_response.close()
                        # 然后调用 AioEventStream.close()
                        if hasattr(response_body, 'close'):
                            response_body.close()
                    except Exception as e:
                        logger.debug(f"Error closing stream: {e}")

                # 返回类似 OpenAI 的响应格式
                import time

                response = {
                    "id": f"chatcmpl-bedrock-{hash(str(messages))}"[:29],  # 生成一个伪 ID
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": self.model_id,
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": full_content
                            },
                            "finish_reason": finish_reason,
                            "index": 0
                        }
                    ],
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens
                    }
                }
                return ChatCompletion(**response)

        except ClientError as e:
            logger.error(f"Bedrock async streaming response error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in async streaming response generation: {e}")
            raise

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> AsyncIterator[str]:
        """Generate streaming completion asynchronously"""
        try:
            request_body = self._create_request_body(messages, temperature, **kwargs)

            # 获取 stop_sequences 用于客户端检测
            stop_sequences = request_body.get('stop_sequences', [])

            async with self.session.create_client(**self._get_client_kwargs()) as client:
                # Bedrock支持流式调用
                response = await client.invoke_model_with_response_stream(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )

                full_content = ""
                stopped_by_sequence = False
                response_body = response['body']

                async for event in response_body:
                    if 'chunk' in event:
                        chunk = json.loads(event['chunk']['bytes'])

                        if chunk.get('type') == 'content_block_delta':
                            delta = chunk.get('delta', {})
                            if delta.get('type') == 'text_delta':
                                text = delta.get('text', '')
                                full_content += text
                                log_llm_stream(text)

                                # 客户端检测 stop sequence
                                for stop_seq in stop_sequences:
                                    if stop_seq in full_content:
                                        # 只 yield 到 stop sequence 位置的内容
                                        idx = full_content.find(stop_seq)
                                        # 计算这次需要 yield 的部分
                                        yield_end = idx + len(stop_seq) - (len(full_content) - len(text))
                                        if yield_end > 0:
                                            yield text[:yield_end]
                                        stopped_by_sequence = True
                                        break

                                if stopped_by_sequence:
                                    break

                                yield text

                        elif chunk.get('type') == 'message_stop':
                            # 记录token使用情况
                            usage = chunk.get('amazon-bedrock-invocationMetrics', {})
                            if usage:
                                self.cost_manager.update_cost(
                                    prompt_tokens=usage.get('inputTokenCount', 0),
                                    completion_tokens=usage.get('outputTokenCount', 0),
                                    model=self.model_id
                                )
                            break

                    if stopped_by_sequence:
                        break

                # 如果提前退出循环，关闭流以避免 "Unclosed connection" 警告
                if stopped_by_sequence:
                    # AioEventStream._raw_stream 直接是 aiohttp.ClientResponse
                    try:
                        if hasattr(response_body, '_raw_stream'):
                            aiohttp_response = response_body._raw_stream
                            if hasattr(aiohttp_response, 'release'):
                                aiohttp_response.release()
                            if hasattr(aiohttp_response, 'close'):
                                aiohttp_response.close()
                        if hasattr(response_body, 'close'):
                            response_body.close()
                    except Exception as e:
                        logger.debug(f"Error closing stream: {e}")

        except ClientError as e:
            logger.error(f"Bedrock async streaming error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in async streaming generation: {e}")
            raise

    def _format_tools_for_bedrock(self, tools: List[Dict]) -> List[Dict]:
        """Format tools for Bedrock Claude API"""
        bedrock_tools = []

        for tool in tools:
            if tool.get("type") == "function":
                function = tool.get("function", {})
                bedrock_tool = {
                    "name": function.get("name"),
                    "description": function.get("description"),
                    "input_schema": function.get("parameters", {})
                }
                bedrock_tools.append(bedrock_tool)

        return bedrock_tools
