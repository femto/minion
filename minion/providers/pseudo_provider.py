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


CONFIG_MESSAGE = """I'm sorry, but I'm not properly configured yet.

To use minion-code, you need to set up your LLM configuration:

**Option 1: Set environment variables**
```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
# or
export OPENAI_API_KEY=sk-xxx
```

**Option 2: Create a config file**
Create `~/.minion/config.yaml`:
```yaml
models:
  default:
    api_type: openai
    api_key: ${OPENAI_API_KEY}
    model: gpt-4o
```

For more details, see: https://github.com/femto/minion#configuration
"""


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

    async def generate_stream(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> Any:
        """Yield configuration message as a stream."""
        async def stream():
            yield CONFIG_MESSAGE
        return stream()

    async def generate_stream_response(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> Any:
        """Return configuration message as stream response."""
        async def stream_generator():
            yield CONFIG_MESSAGE
        return stream_generator()


# Create a singleton pseudo provider instance
_pseudo_config = LLMConfig(api_type="pseudo", model="pseudo")
PSEUDO_PROVIDER = PseudoProvider(_pseudo_config)


def get_pseudo_provider() -> PseudoProvider:
    """Get the singleton pseudo provider instance."""
    return PSEUDO_PROVIDER
