from typing import List, Optional, Dict, Any, AsyncIterator
import json
import time

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function

from minion.configs.config import ContentType, ImageDetail
from minion.logs import logger, log_llm_stream
from minion.schema.message_types import Message, MessageContent, ImageContent
from minion.providers.base_provider import BaseProvider
from minion.providers.llm_provider_registry import llm_registry


@llm_registry.register("azure_anthropic")
class AzureAnthropicProvider(BaseProvider):
    """Azure Anthropic Provider for Claude models using AnthropicFoundry client.

    Supports tool calling via Anthropic's native tool use format, converted to/from
    OpenAI-compatible format for seamless integration.
    """

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
        """Convert Message objects to Anthropic format.

        Handles:
        - user/assistant messages with text/image content
        - assistant messages with tool_calls (converted to tool_use blocks)
        - tool messages (converted to user messages with tool_result blocks)
        """
        anthropic_messages = []
        pending_tool_results = []  # Collect tool results to batch into one user message

        for message in messages:
            # Handle both Message objects and dict format
            if isinstance(message, Message):
                role = message.role
                content_str = message.content
                tool_calls = getattr(message, 'tool_calls', None)
                tool_call_id = getattr(message, 'tool_call_id', None)
            elif isinstance(message, dict):
                role = message.get("role", "")
                content_str = message.get("content", "")
                tool_calls = message.get("tool_calls")
                tool_call_id = message.get("tool_call_id")
            else:
                continue

            # Skip system messages (handled separately)
            if role == "system":
                continue

            # Handle tool messages (OpenAI format) - convert to tool_result
            if role == "tool":
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id or message.get("tool_call_id", ""),
                    "content": content_str if isinstance(content_str, str) else str(content_str)
                }
                pending_tool_results.append(tool_result)
                continue

            # If we have pending tool results, add them as a user message first
            if pending_tool_results:
                anthropic_messages.append({
                    "role": "user",
                    "content": pending_tool_results
                })
                pending_tool_results = []

            # Handle assistant messages with tool_calls
            if role == "assistant" and tool_calls:
                content = []
                # Add text content if present
                if content_str and isinstance(content_str, str) and content_str.strip():
                    content.append({"type": "text", "text": content_str})

                # Add tool_use blocks for each tool call
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        tool_use = {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": tc.get("function", {}).get("name", ""),
                            "input": json.loads(tc.get("function", {}).get("arguments", "{}"))
                        }
                        content.append(tool_use)

                if content:
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": content
                    })
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
                        elif item.get("type") == "tool_result":
                            # Already in Anthropic format
                            content.append(item)
                    elif isinstance(item, str) and item.strip():
                        content.append({"type": "text", "text": item})

            # Only add message if it has content
            if content:
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })

        # Handle any remaining tool results
        if pending_tool_results:
            anthropic_messages.append({
                "role": "user",
                "content": pending_tool_results
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

    def _convert_tools_to_anthropic(self, tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI-format tools to Anthropic format.

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "desc",
                "parameters": {...}
            }
        }

        Anthropic format:
        {
            "name": "tool_name",
            "description": "desc",
            "input_schema": {...}
        }
        """
        anthropic_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                if tool.get("type") == "function" and "function" in tool:
                    func = tool["function"]
                    anthropic_tool = {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {"type": "object", "properties": {}})
                    }
                    anthropic_tools.append(anthropic_tool)
                elif "name" in tool and "input_schema" in tool:
                    # Already in Anthropic format
                    anthropic_tools.append(tool)
                elif "name" in tool and "description" in tool:
                    # Simple format with name/description/parameters
                    anthropic_tool = {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("parameters", tool.get("input_schema", {"type": "object", "properties": {}}))
                    }
                    anthropic_tools.append(anthropic_tool)
        return anthropic_tools

    def _convert_tool_choice_to_anthropic(self, tool_choice: Any) -> Dict:
        """Convert OpenAI tool_choice to Anthropic format.

        OpenAI: "auto", "none", "required", or {"type": "function", "function": {"name": "xxx"}}
        Anthropic: {"type": "auto"}, {"type": "any"}, {"type": "tool", "name": "xxx"}
        """
        if tool_choice is None or tool_choice == "auto":
            return {"type": "auto"}
        elif tool_choice == "none":
            # Anthropic doesn't have "none", we just don't pass tools
            return None
        elif tool_choice == "required":
            return {"type": "any"}
        elif isinstance(tool_choice, dict):
            if "function" in tool_choice:
                return {"type": "tool", "name": tool_choice["function"].get("name", "")}
            elif "name" in tool_choice:
                return {"type": "tool", "name": tool_choice["name"]}
        return {"type": "auto"}

    def _create_openai_tool_calls(self, tool_use_blocks: List[Dict]) -> List[ChatCompletionMessageToolCall]:
        """Convert Anthropic tool_use blocks to OpenAI tool_calls format."""
        tool_calls = []
        for block in tool_use_blocks:
            tool_call = ChatCompletionMessageToolCall(
                id=block.get("id", ""),
                type="function",
                function=Function(
                    name=block.get("name", ""),
                    arguments=json.dumps(block.get("input", {}))
                )
            )
            tool_calls.append(tool_call)
        return tool_calls

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

        # Handle tools parameter - convert from OpenAI format to Anthropic format
        if "tools" in kwargs and kwargs["tools"]:
            tools = kwargs["tools"]
            anthropic_tools = self._convert_tools_to_anthropic(tools)
            if anthropic_tools:
                params["tools"] = anthropic_tools
                logger.debug(f"Added {len(anthropic_tools)} tools to Anthropic request")

                # Handle tool_choice
                tool_choice = kwargs.get("tool_choice")
                anthropic_tool_choice = self._convert_tool_choice_to_anthropic(tool_choice)
                if anthropic_tool_choice:
                    params["tool_choice"] = anthropic_tool_choice

        return params

    def _parse_anthropic_response(self, response) -> tuple:
        """Parse Anthropic response and extract text content and tool_use blocks.

        Returns:
            tuple: (text_content, tool_use_blocks, stop_reason)
        """
        text_content = ""
        tool_use_blocks = []
        stop_reason = getattr(response, 'stop_reason', 'end_turn')

        if response.content:
            for block in response.content:
                if hasattr(block, 'type'):
                    if block.type == 'text':
                        text_content += block.text
                    elif block.type == 'tool_use':
                        tool_use_blocks.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })

        return text_content, tool_use_blocks, stop_reason

    def _create_chat_completion(self, text_content: str, tool_use_blocks: List[Dict],
                                 stop_reason: str, input_tokens: int, output_tokens: int) -> ChatCompletion:
        """Create OpenAI-compatible ChatCompletion response."""
        # Convert stop_reason to OpenAI finish_reason
        if stop_reason == "tool_use":
            finish_reason = "tool_calls"
        elif stop_reason == "end_turn":
            finish_reason = "stop"
        elif stop_reason == "stop_sequence":
            finish_reason = "stop"
        else:
            finish_reason = stop_reason

        # Build message
        message_dict = {
            "role": "assistant",
            "content": text_content if text_content else None
        }

        # Add tool_calls if present
        if tool_use_blocks:
            tool_calls = self._create_openai_tool_calls(tool_use_blocks)
            message_dict["tool_calls"] = [tc.model_dump() for tc in tool_calls]

        response_dict = {
            "id": f"chatcmpl-azure-anthropic-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model,
            "choices": [
                {
                    "message": message_dict,
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
        return ChatCompletion(**response_dict)

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

            # Parse response
            text_content, tool_use_blocks, stop_reason = self._parse_anthropic_response(response)

            # If there are tool calls, return ChatCompletion object
            if tool_use_blocks:
                input_tokens = response.usage.input_tokens if hasattr(response, 'usage') else 0
                output_tokens = response.usage.output_tokens if hasattr(response, 'usage') else 0
                return self._create_chat_completion(text_content, tool_use_blocks, stop_reason,
                                                    input_tokens, output_tokens)

            return text_content

        except Exception as e:
            logger.error(f"Azure Anthropic sync generation error: {e}")
            raise

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion asynchronously.

        Returns:
            str or ChatCompletion: Returns str for text-only responses,
                                   ChatCompletion for responses with tool calls.
        """
        try:
            params = self._create_request_params(messages, temperature, **kwargs)

            response = await self.client.messages.create(**params)

            # Track token usage
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, 'usage'):
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self.cost_manager.update_cost(
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    model=self.model
                )

            # Parse response
            text_content, tool_use_blocks, stop_reason = self._parse_anthropic_response(response)

            # If there are tool calls, return ChatCompletion object for proper handling
            if tool_use_blocks:
                logger.debug(f"Tool use detected: {len(tool_use_blocks)} tool calls")
                return self._create_chat_completion(text_content, tool_use_blocks, stop_reason,
                                                    input_tokens, output_tokens)

            return text_content

        except Exception as e:
            logger.error(f"Azure Anthropic async generation error: {e}")
            raise

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> AsyncIterator[Any]:
        """Generate streaming completion asynchronously.

        Yields StreamChunk objects for text and tool_call content to enable proper
        tool handling in the LmpActionNode streaming pipeline.
        """
        from minion.main.action_step import StreamChunk

        try:
            params = self._create_request_params(messages, temperature, **kwargs)

            # Get stop sequences for client-side detection
            stop_sequences = params.get('stop_sequences', [])

            full_content = ""
            stopped_by_sequence = False

            async with self.client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    full_content += text

                    # Client-side stop sequence detection
                    for stop_seq in stop_sequences:
                        if stop_seq in full_content:
                            idx = full_content.find(stop_seq)
                            yield_end = idx + len(stop_seq) - (len(full_content) - len(text))
                            if yield_end > 0:
                                yield StreamChunk(content=text[:yield_end], chunk_type="text")
                            stopped_by_sequence = True
                            break

                    if stopped_by_sequence:
                        break

                    # Yield StreamChunk with text type
                    yield StreamChunk(content=text, chunk_type="text")

                # Get final message for usage and tool calls
                if not stopped_by_sequence:
                    final_message = await stream.get_final_message()

                    # Track usage
                    if hasattr(final_message, 'usage'):
                        self.cost_manager.update_cost(
                            prompt_tokens=final_message.usage.input_tokens,
                            completion_tokens=final_message.usage.output_tokens,
                            model=self.model
                        )

                    # Check for tool_use blocks and yield them as tool_call chunks
                    if hasattr(final_message, 'content'):
                        for block in final_message.content:
                            if hasattr(block, 'type') and block.type == 'tool_use':
                                # Convert to OpenAI-compatible tool_call format
                                tool_call = {
                                    "id": block.id,
                                    "type": "function",
                                    "function": {
                                        "name": block.name,
                                        "arguments": json.dumps(block.input)
                                    }
                                }
                                yield StreamChunk(
                                    content=f"[Tool call: {block.name}]",
                                    chunk_type="tool_call",
                                    metadata={"tool_call": tool_call}
                                )

        except Exception as e:
            logger.error(f"Azure Anthropic streaming error: {e}")
            raise

    async def generate_stream_response(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> ChatCompletion:
        """Generate streaming completion, returning a response object.

        Handles both text responses and tool calls.
        """
        try:
            params = self._create_request_params(messages, temperature, **kwargs)

            stop_sequences = params.get('stop_sequences', [])

            full_content = ""
            input_tokens = 0
            output_tokens = 0
            stopped_by_sequence = False
            finish_reason = "stop"
            tool_use_blocks = []

            async with self.client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    full_content += text

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

                # Get final message for usage tracking and tool calls
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

                    # Check for tool_use blocks in final message
                    if hasattr(final_message, 'content'):
                        for block in final_message.content:
                            if hasattr(block, 'type') and block.type == 'tool_use':
                                tool_use_blocks.append({
                                    "id": block.id,
                                    "name": block.name,
                                    "input": block.input
                                })

                    # Update finish_reason based on stop_reason
                    if hasattr(final_message, 'stop_reason'):
                        if final_message.stop_reason == "tool_use":
                            finish_reason = "tool_calls"

            # If there are tool calls, return ChatCompletion with tool_calls
            if tool_use_blocks:
                return self._create_chat_completion(full_content, tool_use_blocks, finish_reason,
                                                    input_tokens, output_tokens)

            # Return OpenAI-compatible response format
            response = {
                "id": f"chatcmpl-azure-anthropic-{int(time.time())}",
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
