import os
import warnings
import time
from typing import AsyncIterator, List, Optional, Dict, Any

from minion.schema.message_types import ContentType, Message

from minion.providers.base_provider import BaseProvider
from minion.providers.cost import CostManager
from minion.providers.llm_provider_registry import llm_registry

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import litellm


@llm_registry.register("litellm")
class LiteLLMProvider(BaseProvider):
    """
    LiteLLM provider that supports 100+ LLM providers through a unified interface.

    Supports OpenAI, Azure, Anthropic, Bedrock, VertexAI, Hugging Face, Ollama, etc.

    Configuration example:
        api_type: litellm
        model: gpt-4  # or anthropic/claude-3, bedrock/anthropic.claude-3, etc.
        api_key: your-api-key
        base_url: optional-custom-endpoint
    """

    def _setup(self) -> None:
        """Setup the LiteLLM provider with configuration"""
        # Set API keys based on model prefix or explicit config
        if self.config.api_key:
            # Determine which provider's key to set based on model prefix
            model = self.config.model.lower()
            if model.startswith("anthropic/") or model.startswith("claude"):
                os.environ["ANTHROPIC_API_KEY"] = self.config.api_key
            elif model.startswith("bedrock/"):
                # For Bedrock, use AWS credentials
                if self.config.access_key_id:
                    os.environ["AWS_ACCESS_KEY_ID"] = self.config.access_key_id
                if self.config.secret_access_key:
                    os.environ["AWS_SECRET_ACCESS_KEY"] = self.config.secret_access_key
                if self.config.region:
                    os.environ["AWS_REGION_NAME"] = self.config.region
            elif model.startswith("vertex_ai/") or model.startswith("gemini/"):
                os.environ["VERTEX_API_KEY"] = self.config.api_key
            elif model.startswith("azure/"):
                os.environ["AZURE_API_KEY"] = self.config.api_key
                if self.config.api_version:
                    os.environ["AZURE_API_VERSION"] = self.config.api_version
            else:
                # Default to OpenAI
                os.environ["OPENAI_API_KEY"] = self.config.api_key

        # Set custom base_url if provided
        if self.config.base_url:
            litellm.api_base = str(self.config.base_url)

        # Initialize token counters
        self.last_input_token_count = 0
        self.last_output_token_count = 0

    def _prepare_messages(self, messages: List[Message] | List[dict]) -> List[dict]:
        """Prepare messages for the API in OpenAI format

        Args:
            messages: List of Message objects or OpenAI format dictionaries
        Returns:
            List[dict]: Messages in OpenAI API format
        """
        # If already in OpenAI API format, return directly
        if isinstance(messages, list) and all(isinstance(msg, dict) for msg in messages):
            return messages

        prepared_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                prepared_messages.append(msg)
            elif isinstance(msg.content, str):
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

    def _prepare_tools(self, tools: List[Dict]) -> List[Dict]:
        """Convert tools to OpenAI API format

        Args:
            tools: Original tool list
        Returns:
            List[Dict]: Formatted tool list for the API
        """
        if not tools:
            return None

        prepared_tools = []
        for tool in tools:
            # If already in OpenAI format (with type and function fields), use directly
            if 'type' in tool and 'function' in tool:
                prepared_tools.append(tool)
            else:
                # Convert minion format to OpenAI format
                function_data = {}
                for key in ["name", "description", "parameters"]:
                    if key in tool:
                        function_data[key] = tool[key]

                if "name" in function_data and "description" in function_data:
                    prepared_tools.append({
                        "type": "function",
                        "function": function_data
                    })

        return prepared_tools if prepared_tools else None

    def _update_cost(self, prompt_tokens: int, completion_tokens: int):
        """Update cost tracking"""
        model = self.config.model
        self.cost_manager.update_cost(prompt_tokens, completion_tokens, model)
        self.last_input_token_count = prompt_tokens
        self.last_output_token_count = completion_tokens

    def generate_sync(self, messages: List[Message] | List[dict], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion from messages synchronously

        Args:
            messages: List of Message objects or OpenAI format message dictionaries
            temperature: Temperature for generation
            **kwargs: Additional parameters to pass to the API

        Returns:
            str: The generated text or tool calls
        """
        prepared_messages = self._prepare_messages(messages)
        model = kwargs.pop('model', self.config.model)

        # Handle tools parameter
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools
                if 'tool_choice' not in kwargs:
                    kwargs['tool_choice'] = "auto"

        response = litellm.completion(
            model=model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            **kwargs,
        )

        # Update cost tracking
        if hasattr(response, 'usage') and response.usage:
            self._update_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

        # Handle tool calls
        if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
            return response.choices[0].message.tool_calls

        return response.choices[0].message.content or ""

    def generate_sync_response(self, messages: List[Message] | List[dict], temperature: Optional[float] = None, **kwargs) -> Any:
        """Generate completion from messages synchronously, returning raw response

        Args:
            messages: List of Message objects or OpenAI format message dictionaries
            temperature: Temperature for generation
            **kwargs: Additional parameters to pass to the API

        Returns:
            Raw API response object
        """
        prepared_messages = self._prepare_messages(messages)
        model = kwargs.pop('model', self.config.model)

        # Handle tools parameter
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools
                if 'tool_choice' not in kwargs:
                    kwargs['tool_choice'] = "auto"

        response = litellm.completion(
            model=model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            **kwargs,
        )

        # Update cost tracking
        if hasattr(response, 'usage') and response.usage:
            self._update_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

        return response

    async def generate(self, messages: List[Message] | List[dict], temperature: Optional[float] = None, **kwargs) -> str:
        """Generate completion from messages asynchronously

        Args:
            messages: List of Message objects or OpenAI format message dictionaries
            temperature: Temperature for generation
            **kwargs: Additional parameters to pass to the API

        Returns:
            str: The generated text or tool calls
        """
        prepared_messages = self._prepare_messages(messages)
        model = kwargs.pop('model', self.config.model)

        # Handle tools parameter
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools
                if 'tool_choice' not in kwargs:
                    kwargs['tool_choice'] = "auto"

        response = await litellm.acompletion(
            model=model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            **kwargs,
        )

        # Update cost tracking
        if hasattr(response, 'usage') and response.usage:
            self._update_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

        # Handle tool calls
        if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
            return response.choices[0].message.tool_calls

        return response.choices[0].message.content or ""

    async def generate_response(self, messages: List[Message] | List[dict], temperature: Optional[float] = None, **kwargs) -> Any:
        """Generate completion from messages asynchronously, returning raw response

        Args:
            messages: List of Message objects or OpenAI format message dictionaries
            temperature: Temperature for generation
            **kwargs: Additional parameters to pass to the API

        Returns:
            Raw API response object
        """
        prepared_messages = self._prepare_messages(messages)
        model = kwargs.pop('model', self.config.model)

        # Handle tools parameter
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools
                if 'tool_choice' not in kwargs:
                    kwargs['tool_choice'] = "auto"

        response = await litellm.acompletion(
            model=model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            **kwargs,
        )

        # Update cost tracking
        if hasattr(response, 'usage') and response.usage:
            self._update_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

        return response

    async def generate_stream(
        self, messages: List[Message] | List[dict], temperature: Optional[float] = None, **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming completion from messages

        Args:
            messages: List of Message objects or OpenAI format message dictionaries
            temperature: Temperature for generation
            **kwargs: Additional parameters to pass to the API

        Yields:
            StreamChunk: Generated text chunks or tool calls with metadata
        """
        from minion.main.action_step import StreamChunk

        prepared_messages = self._prepare_messages(messages)
        model = kwargs.pop('model', self.config.model)

        # Handle tools parameter
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools
                if 'tool_choice' not in kwargs:
                    kwargs['tool_choice'] = "auto"

        full_content = ""
        chunk_counter = 0
        tool_call_map = {}  # index -> tool_call dict
        has_tool_calls = False

        async for chunk in await litellm.acompletion(
            model=model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            stream=True,
            **kwargs,
        ):
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta

                # Handle tool_calls (function calls)
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    has_tool_calls = True
                    for tc in delta.tool_calls:
                        tc_index = getattr(tc, 'index', None)
                        if tc_index is None:
                            continue

                        if tc_index not in tool_call_map:
                            tool_call_map[tc_index] = {
                                'id': getattr(tc, 'id', f'call_{tc_index}'),
                                'type': getattr(tc, 'type', 'function'),
                                'function': {
                                    'name': '',
                                    'arguments': ''
                                }
                            }

                        func = getattr(tc, 'function', None)
                        if func:
                            if hasattr(func, 'name') and func.name:
                                tool_call_map[tc_index]['function']['name'] += func.name
                            if hasattr(func, 'arguments') and func.arguments:
                                tool_call_map[tc_index]['function']['arguments'] += func.arguments

                # Handle normal content
                if hasattr(delta, 'content') and delta.content:
                    content = delta.content
                    full_content += content
                    chunk_counter += 1

                    stream_chunk = StreamChunk(
                        content=content,
                        chunk_type="text",
                        metadata={
                            "provider": "litellm",
                            "model": model,
                            "chunk_number": chunk_counter,
                            "total_length": len(full_content),
                            "chunk_id": getattr(chunk, 'id', None),
                            "finish_reason": getattr(chunk.choices[0], 'finish_reason', None) if chunk.choices else None,
                            "api_type": self.config.api_type
                        }
                    )
                    yield stream_chunk

        # Yield complete tool calls at the end
        if has_tool_calls and tool_call_map:
            tool_calls = list(tool_call_map.values())
            for tool_call in tool_calls:
                tool_call_chunk = StreamChunk(
                    content=f"Tool call: {tool_call['function']['name']}({tool_call['function']['arguments']})",
                    chunk_type="tool_call",
                    metadata={
                        "provider": "litellm",
                        "model": model,
                        "tool_call": tool_call,
                        "api_type": self.config.api_type
                    }
                )
                yield tool_call_chunk

        # Update cost tracking (estimate tokens from content length)
        completion_tokens = len(full_content) // 4
        prompt_tokens, _ = CostManager.calculate(messages, completion_tokens, model)
        self._update_cost(prompt_tokens, completion_tokens)

    async def generate_stream_response(self, messages: List[Message] | List[dict], temperature: Optional[float] = None, **kwargs) -> Any:
        """Generate streaming completion from messages, returning aggregated response

        Args:
            messages: List of Message objects or OpenAI format message dictionaries
            temperature: Temperature for generation
            **kwargs: Additional parameters to pass to the API

        Returns:
            An OpenAI-style response object (dict) with choices, usage, etc.
        """
        from openai.types.chat import ChatCompletion

        prepared_messages = self._prepare_messages(messages)
        model = kwargs.pop('model', self.config.model)

        # Handle tools parameter
        if 'tools' in kwargs:
            prepared_tools = self._prepare_tools(kwargs.pop('tools'))
            if prepared_tools:
                kwargs['tools'] = prepared_tools
                if 'tool_choice' not in kwargs:
                    kwargs['tool_choice'] = "auto"

        full_content = ""
        tool_call_map = {}
        has_tool_calls = False
        finish_reason = None
        role = "assistant"

        async for chunk in await litellm.acompletion(
            model=model,
            messages=prepared_messages,
            temperature=temperature or self.config.temperature,
            stream=True,
            **kwargs,
        ):
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta

                # Handle tool_calls
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    has_tool_calls = True
                    for tc in delta.tool_calls:
                        tc_index = getattr(tc, 'index', None)
                        if tc_index is None:
                            continue

                        if tc_index not in tool_call_map:
                            tool_call_map[tc_index] = {
                                'id': getattr(tc, 'id', f'call_{tc_index}'),
                                'type': getattr(tc, 'type', 'function'),
                                'function': {
                                    'name': '',
                                    'arguments': ''
                                }
                            }

                        func = getattr(tc, 'function', None)
                        if func:
                            if hasattr(func, 'name') and func.name:
                                tool_call_map[tc_index]['function']['name'] += func.name
                            if hasattr(func, 'arguments') and func.arguments:
                                tool_call_map[tc_index]['function']['arguments'] += func.arguments

                # Handle normal content
                if hasattr(delta, 'content') and delta.content:
                    full_content += delta.content

                # Track finish_reason and role
                if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'role') and chunk.choices[0].delta.role:
                    role = chunk.choices[0].delta.role

        # Update cost tracking
        completion_tokens = len(full_content) // 4
        prompt_tokens, _ = CostManager.calculate(messages, completion_tokens, model)
        self._update_cost(prompt_tokens, completion_tokens)

        # Build OpenAI-compatible response
        response = {
            "id": f"chatcmpl-litellm-{hash(str(messages))}"[:29],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": role,
                        **({"content": full_content} if not has_tool_calls else {}),
                        **({"tool_calls": list(tool_call_map.values())} if has_tool_calls else {})
                    },
                    "finish_reason": finish_reason or ("tool_calls" if has_tool_calls else "stop")
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }

        return ChatCompletion(**response)


# Usage example
async def main():
    from minion.configs.config import config

    # Example with OpenAI model via LiteLLM
    llm_config = config.models.get("gpt-4o-mini")
    if llm_config:
        llm = LiteLLMProvider(config=llm_config)

        messages = [
            {"role": "user", "content": "What is 2 + 2?"}
        ]

        # Async generation
        response = await llm.generate(messages)
        print(f"Response: {response}")
        print(f"Cost: ${llm.get_cost().total_cost:.6f}")

        # Streaming generation
        print("\nStreaming response:")
        async for chunk in llm.generate_stream(messages):
            print(chunk.content, end="", flush=True)
        print(f"\nFinal cost: ${llm.get_cost().total_cost:.6f}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
