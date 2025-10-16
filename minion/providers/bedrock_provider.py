from typing import List, Optional, Dict, Any, AsyncIterator, Generator
import asyncio
import json
import base64
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from openai.types.chat import ChatCompletion

from minion.configs.config import ContentType, ImageDetail
from minion.logs import logger
from minion.schema.message_types import Message, MessageContent, ImageContent
from minion.providers.base_provider import BaseProvider
from minion.providers.llm_provider_registry import llm_registry


@llm_registry.register("bedrock")
class BedrockProvider(BaseProvider):
    """AWS Bedrock Provider for Claude models"""
    
    def _setup(self) -> None:
        """Setup AWS Bedrock client"""
        try:
            # 获取 AWS 凭证（使用清晰的字段名）
            aws_access_key_id = getattr(self.config, 'access_key_id', None)
            aws_secret_access_key = getattr(self.config, 'secret_access_key', None)
            
            # 向后兼容：如果没有专门的 access_key_id，尝试从 api_key 中获取
            if not aws_access_key_id:
                api_key = getattr(self.config, 'api_key', None)
                if api_key and ':' in api_key:
                    aws_access_key_id, aws_secret_access_key = api_key.split(':', 1)
                elif api_key:
                    aws_access_key_id = api_key
            
            # 设置 AWS region，默认为 us-east-1
            region_name = getattr(self.config, 'region', 'us-east-1')
            
            # 创建 Bedrock Runtime 客户端，参数名与 boto3 完全一致
            client_kwargs = {
                'service_name': 'bedrock-runtime',
                'region_name': region_name
            }
            
            # 只有在提供了凭证时才添加到参数中
            if aws_access_key_id:
                client_kwargs['aws_access_key_id'] = aws_access_key_id
            if aws_secret_access_key:
                client_kwargs['aws_secret_access_key'] = aws_secret_access_key
            
            self.client = boto3.client(**client_kwargs)
            
            # 确定模型ID
            self.model_id = getattr(self.config, 'model', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
            
            logger.info(f"Initialized Bedrock provider with model: {self.model_id} in region: {region_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock provider: {e}")
            raise
    
    def _prepare_messages(self, messages: List[Message]) -> List[Dict]:
        """Convert Message objects to Bedrock Claude format and merge consecutive same-role messages"""
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
                            if item.content.type == "image_base64":
                                # 提取图片格式（如果data是data:image/jpeg;base64,xxx格式）
                                data = item.content.data
                                media_type = "image/jpeg"  # 默认格式
                                
                                if data.startswith("data:"):
                                    # 解析data URL格式
                                    header, base64_data = data.split(",", 1)
                                    if "image/" in header:
                                        media_type = header.split(";")[0].replace("data:", "")
                                    data = base64_data
                                
                                content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": data
                                    }
                                })
                            elif item.content.type == "image_url":
                                # Bedrock不直接支持URL图片，需要下载并转换为base64
                                # 这里可以添加URL到base64的转换逻辑
                                logger.warning("Image URLs are not directly supported by Bedrock, consider converting to base64")
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
                # 检查是否需要合并相同角色的连续消息
                if bedrock_messages and bedrock_messages[-1]["role"] == role:
                    # 合并到上一条消息
                    bedrock_messages[-1]["content"].extend(content)
                else:
                    # 添加新消息
                    bedrock_messages.append({
                        "role": role,
                        "content": content
                    })
        
        return self._ensure_alternating_roles(bedrock_messages)
    
    def _ensure_alternating_roles(self, messages: List[Dict]) -> List[Dict]:
        """Ensure messages alternate between user and assistant roles"""
        if not messages:
            return messages
        
        result = []
        
        for message in messages:
            role = message["role"]
            content = message["content"]
            
            # 如果结果为空，直接添加
            if not result:
                result.append(message)
                continue
            
            last_role = result[-1]["role"]
            
            # 如果角色相同，合并内容
            if last_role == role:
                # 合并文本内容，用换行分隔
                text_parts = []
                
                # 提取上一条消息的文本内容
                for item in result[-1]["content"]:
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                
                # 提取当前消息的文本内容
                for item in content:
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                
                # 合并文本并更新上一条消息
                merged_text = "\n\n".join(filter(None, text_parts))
                
                # 保留非文本内容（如图片）
                non_text_content = []
                for item in result[-1]["content"] + content:
                    if item.get("type") != "text":
                        non_text_content.append(item)
                
                # 重新构建内容
                new_content = []
                if merged_text.strip():
                    new_content.append({"type": "text", "text": merged_text})
                new_content.extend(non_text_content)
                
                result[-1]["content"] = new_content
            else:
                # 角色不同，直接添加
                result.append(message)
        
        return result
    
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
        
        return request_body
    
    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion synchronously"""
        try:
            request_body = self._create_request_body(messages, temperature, **kwargs)
            
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response['body'].read())
            
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
            logger.error(f"Bedrock client error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating completion: {e}")
            raise
    
    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion asynchronously"""
        # AWS Bedrock SDK不直接支持async，所以我们在线程池中运行同步调用
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_sync, messages, temperature, **kwargs)
    
    async def generate_stream_response(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> ChatCompletion:
        """
        Generate streaming completion from messages, returning a response object
        
        Args:
            messages: List of Message objects
            temperature: Temperature for generation
            **kwargs: Additional parameters
            
        Returns:
            A response object with choices, usage, etc.
        """
        try:
            request_body = self._create_request_body(messages, temperature, **kwargs)
            
            # Bedrock支持流式调用
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            full_content = ""
            input_tokens = 0
            output_tokens = 0
            
            for event in response['body']:
                if 'chunk' in event:
                    chunk = json.loads(event['chunk']['bytes'])
                    
                    if chunk.get('type') == 'content_block_delta':
                        delta = chunk.get('delta', {})
                        if delta.get('type') == 'text_delta':
                            text = delta.get('text', '')
                            full_content += text
                    
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
                        "finish_reason": "stop",
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
            logger.error(f"Bedrock streaming response error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in streaming response generation: {e}")
            raise
    
    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> Generator[str, None, str]:
        """Generate streaming completion"""
        try:
            request_body = self._create_request_body(messages, temperature, **kwargs)
            
            # Bedrock支持流式调用
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            full_response = ""
            
            for event in response['body']:
                if 'chunk' in event:
                    chunk = json.loads(event['chunk']['bytes'])
                    
                    if chunk.get('type') == 'content_block_delta':
                        delta = chunk.get('delta', {})
                        if delta.get('type') == 'text_delta':
                            text = delta.get('text', '')
                            full_response += text
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
            
            # Generator函数不能用return返回值，只能yield
            # 如果需要返回完整响应，可以在最后yield
            
        except ClientError as e:
            logger.error(f"Bedrock streaming error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
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