from typing import List, Optional, Dict, Any, AsyncIterator
import json

from openai.types.chat import ChatCompletion

from minion.configs.config import ContentType, ImageDetail
from minion.logs import logger, log_llm_stream
from minion.schema.message_types import Message, MessageContent, ImageContent
from minion.providers.base_provider import BaseProvider
from minion.providers.llm_provider_registry import llm_registry


@llm_registry.register("azure_anthropic")
class AzureAnthropicProvider(BaseProvider):
    """Azure Anthropic Provider for Claude models using AnthropicFoundry client"""

    def _setup(self) -> None:
        """Setup Azure Anthropic client configuration"""
        try:
            from anthropic import AnthropicFoundry, AsyncAnthropicFoundry
        except ImportError as e:
            raise ImportError(
                "anthropic is required for AzureAnthropicProvider. "
                "Install it with: pip install anthropic"
            ) from e

        try:
            self.api_key = self.config.api_key
            self.base_url = self.config.base_url
            self.model = self.config.model

            # Create sync and async clients
            self.client_sync = AnthropicFoundry(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.client = AsyncAnthropicFoundry(
                api_key=self.api_key,
                base_url=self.base_url
            )

            logger.info(f"Initialized Azure Anthropic provider with model: {self.model}")

        except Exception as e:
            logger.error(f"Failed to initialize Azure Anthropic provider: {e}")
            raise

    def _prepare_messages(self, messages: List[Message]) -> List[Dict]:
        """Convert Message objects to Anthropic format"""
        anthropic_messages = []

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

            # Skip system messages (handled separately)
            if role == "system":
                continue

            # Only process user and assistant messages
            if role not in ["user", "assistant"]:
                continue

            # Process message content
            content = []
            if isinstance(content_str, str):
                if content_str.strip():
                    content.append({"type": "text", "text": content_str})
            elif isinstance(content_str, list):
                for item in content_str:
                    if isinstance(item, MessageContent):
                        if item.type == ContentType.TEXT:
                            if item.content.strip():
                                content.append({"type": "text", "text": item.content})
                        elif item.type == ContentType.IMAGE and isinstance(item.content, ImageContent):
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
                        if item.get("type") == "text" and item.get("text", "").strip():
                            content.append(item)
                        elif item.get("type") == "image":
                            content.append(item)
                    elif isinstance(item, str) and item.strip():
                        content.append({"type": "text", "text": item})

            # Only add message if it has content
            if content:
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })

        return anthropic_messages

    def _extract_system_message(self, messages: List[Message]) -> Optional[str]:
        """Extract system message from messages list"""
        for message in messages:
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

    def _create_request_params(self, messages: List[Message], temperature: Optional[float] = None,
                               max_tokens: int = 4096, **kwargs) -> Dict:
        """Create request parameters for Anthropic API"""
        anthropic_messages = self._prepare_messages(messages)
        system_message = self._extract_system_message(messages)

        # Ensure at least one message
        if not anthropic_messages:
            raise ValueError("At least one user or assistant message is required")

        params = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
        }

        if system_message:
            params["system"] = system_message

        if temperature is not None:
            params["temperature"] = temperature
        elif hasattr(self.config, 'temperature'):
            params["temperature"] = self.config.temperature

        # Add optional parameters
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            params["top_k"] = kwargs["top_k"]

        # Handle stop parameter
        if "stop" in kwargs and kwargs["stop"]:
            stop_sequences = kwargs["stop"]
            if isinstance(stop_sequences, str):
                stop_sequences = [stop_sequences]
            params["stop_sequences"] = stop_sequences

        return params

    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion synchronously"""
        try:
            params = self._create_request_params(messages, temperature, **kwargs)

            response = self.client_sync.messages.create(**params)

            # Track token usage
            if hasattr(response, 'usage'):
                self.cost_manager.update_cost(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    model=self.model
                )

            # Extract text content
            if response.content:
                for block in response.content:
                    if hasattr(block, 'type') and block.type == 'text':
                        return block.text

            return ""

        except Exception as e:
            logger.error(f"Azure Anthropic sync generation error: {e}")
            raise

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion asynchronously"""
        try:
            params = self._create_request_params(messages, temperature, **kwargs)

            response = await self.client.messages.create(**params)

            # Track token usage
            if hasattr(response, 'usage'):
                self.cost_manager.update_cost(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    model=self.model
                )

            # Extract text content
            if response.content:
                for block in response.content:
                    if hasattr(block, 'type') and block.type == 'text':
                        return block.text

            return ""

        except Exception as e:
            logger.error(f"Azure Anthropic async generation error: {e}")
            raise

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> AsyncIterator[str]:
        """Generate streaming completion asynchronously"""
        try:
            params = self._create_request_params(messages, temperature, **kwargs)

            # Get stop sequences for client-side detection
            stop_sequences = params.get('stop_sequences', [])

            full_content = ""
            stopped_by_sequence = False

            async with self.client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    full_content += text
                    # log_llm_stream(text)  # Disabled: causes duplicate output in streaming mode

                    # Client-side stop sequence detection
                    for stop_seq in stop_sequences:
                        if stop_seq in full_content:
                            idx = full_content.find(stop_seq)
                            yield_end = idx + len(stop_seq) - (len(full_content) - len(text))
                            if yield_end > 0:
                                yield text[:yield_end]
                            stopped_by_sequence = True
                            break

                    if stopped_by_sequence:
                        break

                    yield text

                # Get final message for usage tracking
                if not stopped_by_sequence:
                    final_message = await stream.get_final_message()
                    if hasattr(final_message, 'usage'):
                        self.cost_manager.update_cost(
                            prompt_tokens=final_message.usage.input_tokens,
                            completion_tokens=final_message.usage.output_tokens,
                            model=self.model
                        )

        except Exception as e:
            logger.error(f"Azure Anthropic streaming error: {e}")
            raise

    async def generate_stream_response(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> ChatCompletion:
        """Generate streaming completion, returning a response object"""
        try:
            params = self._create_request_params(messages, temperature, **kwargs)

            stop_sequences = params.get('stop_sequences', [])

            full_content = ""
            input_tokens = 0
            output_tokens = 0
            stopped_by_sequence = False
            finish_reason = "stop"

            async with self.client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    full_content += text
                    # log_llm_stream(text)  # Disabled: causes duplicate output in streaming mode

                    # Client-side stop sequence detection
                    for stop_seq in stop_sequences:
                        if stop_seq in full_content:
                            idx = full_content.find(stop_seq)
                            full_content = full_content[:idx + len(stop_seq)]
                            stopped_by_sequence = True
                            finish_reason = "stop_sequence"
                            logger.info(f"[STOP_SEQ] Client-side stop sequence detected: '{stop_seq}'")
                            break

                    if stopped_by_sequence:
                        break

                # Get final message for usage tracking
                if not stopped_by_sequence:
                    final_message = await stream.get_final_message()
                    if hasattr(final_message, 'usage'):
                        input_tokens = final_message.usage.input_tokens
                        output_tokens = final_message.usage.output_tokens
                        self.cost_manager.update_cost(
                            prompt_tokens=input_tokens,
                            completion_tokens=output_tokens,
                            model=self.model
                        )

            # Return OpenAI-compatible response format
            import time

            response = {
                "id": f"chatcmpl-azure-anthropic-{hash(str(messages))}"[:29],
                "object": "chat.completion",
                "created": int(time.time()),
                "model": self.model,
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

        except Exception as e:
            logger.error(f"Azure Anthropic streaming response error: {e}")
            raise
