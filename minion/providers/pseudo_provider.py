"""
Pseudo LLM Provider - Returns configuration instructions when no real model is configured.

This provider is used as a fallback when the user hasn't configured any LLM models.
Instead of crashing, it returns a helpful message directing users to the configuration docs.
"""

from typing import AsyncIterator, List, Optional, Any, Generator

from minion.configs.config import LLMConfig
from minion.schema.message_types import Message
from minion.providers.base_provider import BaseProvider
from minion.providers.llm_provider_registry import llm_registry


# Plain text message for non-CodeAgent use
CONFIG_MESSAGE_TEXT = """Welcome to minion-code! To get started, please configure your LLM.

**Setup Instructions:**

Create a config file at `~/.minion/config.yaml`:
```yaml
models:
  "default":
    api_type: "openai"
    base_url: "${DEFAULT_BASE_URL}"
    api_key: "${DEFAULT_API_KEY}"
    model: "gpt-4o"
    temperature: 0
```

Or set environment variables:
- `OPENAI_API_KEY` for OpenAI models
- `ANTHROPIC_API_KEY` for Claude models

For more details, see: https://github.com/femto/minion#configuration
"""

# CodeAgent-compatible format with final_answer() and <end_code>
# Note: Avoid nested ``` blocks which cause parsing issues
CONFIG_MESSAGE = '''**Thought:** I need to inform the user that the LLM is not configured yet.

**Code:**
```python
final_answer("""Welcome to minion-code! To get started, please configure your LLM.

Setup Instructions:

1. Create a config file at ~/.minion/config.yaml with:

   models:
     "default":
       api_type: "openai"
       base_url: "your-base-url"
       api_key: "your-api-key"
       model: "gpt-4o"
       temperature: 0

2. Or set environment variables:
   - OPENAI_API_KEY for OpenAI models
   - ANTHROPIC_API_KEY for Claude models

For more details, see: https://github.com/femto/minion#configuration
""")
```<end_code>'''


@llm_registry.register("pseudo")
class PseudoProvider(BaseProvider):
    """
    A pseudo LLM provider that returns configuration instructions.

    Used when no real LLM is configured, to provide a helpful message
    instead of crashing with cryptic errors.
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        # Don't call super().__init__ to avoid retry decorator setup
        # which requires openai package
        self.config = config

    def _setup(self) -> None:
        """No setup needed for pseudo provider."""
        pass

    def generate_sync(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Return configuration message."""
        return CONFIG_MESSAGE

    async def generate(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> str:
        """Return configuration message."""
        return CONFIG_MESSAGE

    async def generate_sync_response(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> Any:
        """Return configuration message."""
        return CONFIG_MESSAGE

    async def generate_response(self, messages: List[Message] | List[dict], temperature: Optional[float] = None, **kwargs) -> Any:
        """Return configuration message."""
        return CONFIG_MESSAGE

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs):
        """Yield configuration message as a stream."""
        # Import StreamChunk to match other providers' format
        from minion.main.action_step import StreamChunk
        yield StreamChunk(content=CONFIG_MESSAGE, chunk_type="text")

    async def generate_stream_response(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> Any:
        """Return configuration message as a complete response (not streaming)."""
        from openai.types.chat import ChatCompletion

        # Return OpenAI ChatCompletion format
        response = {
            "id": "pseudo-response",
            "object": "chat.completion",
            "created": 0,
            "model": "pseudo",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": CONFIG_MESSAGE
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        return ChatCompletion(**response)


# Create a singleton pseudo provider instance
_pseudo_config = LLMConfig(api_type="pseudo", model="pseudo")
PSEUDO_PROVIDER = PseudoProvider(_pseudo_config)


def get_pseudo_provider() -> PseudoProvider:
    """Get the singleton pseudo provider instance."""
    return PSEUDO_PROVIDER
