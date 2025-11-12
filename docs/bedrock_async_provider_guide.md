# Bedrock Async Provider Guide

## Overview

`BedrockAsyncProvider` is a fully asynchronous AWS Bedrock provider implementation using `aiobotocore`. Unlike the original `BedrockProvider` which uses `boto3` with thread pool executors, this provider offers true async/await support for better performance in async applications.

## Key Differences from BedrockProvider

| Feature | BedrockProvider | BedrockAsyncProvider |
|---------|----------------|---------------------|
| Backend | boto3 (sync) | aiobotocore (async) |
| Async Methods | Uses `loop.run_in_executor()` | Native async/await |
| Performance | Thread pool overhead | True async I/O |
| Registry Name | `bedrock` | `bedrock_async` |

## Installation

Bedrock support requires additional dependencies (`boto3`, `botocore`, `aiobotocore`).

### Option 1: Install with Bedrock support (Recommended)

```bash
pip install -e ".[bedrock]"
```

### Option 2: Install dependencies manually

```bash
pip install boto3 botocore aiobotocore
```

### Option 3: Install all optional dependencies

```bash
pip install -e ".[all]"
```

**Note**: If you try to use `bedrock_async` provider without installing these dependencies, you'll see a helpful error message telling you what to install.

## Configuration

### YAML Configuration (Recommended)

Add to your `config/config.yaml`:

```yaml
models:
  # Async version (recommended for better performance)
  "claude-3-5-sonnet-bedrock-async":
    api_type: "bedrock_async"
    access_key_id: "${AWS_ACCESS_KEY_ID}"
    secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
    region: "us-east-1"
    model: "anthropic.claude-3-5-sonnet-20240620-v1:0"
    temperature: 0.7

  "claude-3-5-haiku-bedrock-async":
    api_type: "bedrock_async"
    access_key_id: "${AWS_ACCESS_KEY_ID}"
    secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
    region: "us-east-1"
    model: "anthropic.claude-3-5-haiku-20241022-v1:0"
    temperature: 0.7

  "claude-3-opus-bedrock-async":
    api_type: "bedrock_async"
    access_key_id: "${AWS_ACCESS_KEY_ID}"
    secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
    region: "us-east-1"
    model: "anthropic.claude-3-opus-20240229-v1:0"
    temperature: 0.7
```

Then use it with:

```python
from minion.providers import create_llm_provider
from minion.configs.config import config

llm_config = config.models.get("claude-3-5-sonnet-bedrock-async")
provider = create_llm_provider(llm_config)
```

### Programmatic Configuration

```python
from minion.configs.config import LLMConfig

config = LLMConfig(
    provider="bedrock_async",  # Note: use "bedrock_async"
    model="anthropic.claude-3-5-sonnet-20240620-v1:0",
    region="us-east-1",
    temperature=0.7
)
```

### With AWS Credentials

```python
config = LLMConfig(
    provider="bedrock_async",
    model="anthropic.claude-3-5-sonnet-20240620-v1:0",
    region="us-east-1",
    access_key_id="YOUR_ACCESS_KEY",
    secret_access_key="YOUR_SECRET_KEY",
    temperature=0.7
)
```

### Legacy Format (backward compatible)

```python
config = LLMConfig(
    provider="bedrock_async",
    model="anthropic.claude-3-5-sonnet-20240620-v1:0",
    region="us-east-1",
    api_key="ACCESS_KEY:SECRET_KEY",  # Format: access_key:secret_key
    temperature=0.7
)
```

## Usage Examples

### 1. Basic Async Generation

```python
import asyncio
from minion.providers.bedrock_async_provider import BedrockAsyncProvider
from minion.schema.message_types import Message

async def main():
    provider = BedrockAsyncProvider(config)

    messages = [
        Message(role="user", content="Hello! How are you?")
    ]

    response = await provider.generate(messages)
    print(response)

asyncio.run(main())
```

### 2. Async Streaming

```python
async def stream_example():
    provider = BedrockAsyncProvider(config)

    messages = [
        Message(role="user", content="Write a short poem about coding.")
    ]

    async for chunk in provider.generate_stream(messages):
        print(chunk, end='', flush=True)

asyncio.run(stream_example())
```

### 3. Stream Response (Full Response Object)

```python
async def stream_response_example():
    provider = BedrockAsyncProvider(config)

    messages = [
        Message(role="user", content="Explain async programming in one sentence.")
    ]

    response = await provider.generate_stream_response(messages)

    print(f"Content: {response['choices'][0]['message']['content']}")
    print(f"Tokens used: {response['usage']['total_tokens']}")

asyncio.run(stream_response_example())
```

### 4. Integration with Minion Agents

```python
from minion.main.brain import Brain
from minion.configs.config import config

async def agent_example():
    # Using config from config.yaml
    # The model name matches the key in config.yaml
    brain = Brain(llm="claude-3-5-sonnet-bedrock-async")

    response = await brain.step(
        query="What is the capital of France?",
        route="code"  # or "react" depending on your needs
    )

    print(response.output)

asyncio.run(agent_example())
```

### 5. Using with create_llm_provider

```python
from minion.providers import create_llm_provider
from minion.configs.config import config
from minion.schema.message_types import Message

async def provider_example():
    # Load from config.yaml
    llm_config = config.models.get("claude-3-5-haiku-bedrock-async")
    provider = create_llm_provider(llm_config)

    messages = [
        Message(role="user", content="Hello!")
    ]

    response = await provider.generate(messages)
    print(response)

asyncio.run(provider_example())
```

## Supported Models

All AWS Bedrock Claude models are supported:

- `anthropic.claude-3-5-sonnet-20240620-v1:0` (recommended)
- `anthropic.claude-3-sonnet-20240229-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`
- `anthropic.claude-3-opus-20240229-v1:0`
- Other Bedrock Claude models

## API Methods

### `generate(messages, temperature=None, **kwargs) -> str`

Generate a complete response asynchronously.

**Parameters:**
- `messages`: List of Message objects
- `temperature`: Optional temperature override
- `**kwargs`: Additional parameters (top_p, top_k, max_tokens)

**Returns:** String response

### `generate_stream(messages, temperature=None, **kwargs) -> AsyncIterator[str]`

Generate streaming response chunks asynchronously.

**Parameters:** Same as `generate()`

**Returns:** AsyncIterator yielding text chunks

### `generate_stream_response(messages, temperature=None, **kwargs) -> dict`

Generate streaming response but return full response object.

**Parameters:** Same as `generate()`

**Returns:** Dictionary with OpenAI-compatible format:
```python
{
    "choices": [{"message": {"role": "assistant", "content": "..."}, ...}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 20, ...},
    "model": "...",
    "object": "chat.completion"
}
```

### `generate_sync(messages, temperature=None, **kwargs) -> str`

Synchronous wrapper (not recommended, creates event loop internally).

## AWS Credentials

The provider looks for credentials in this order:

1. `access_key_id` and `secret_access_key` in config
2. `api_key` in format `ACCESS_KEY:SECRET_KEY`
3. Default AWS credentials chain (environment variables, ~/.aws/credentials, IAM role)

## Error Handling

```python
from botocore.exceptions import ClientError

async def safe_generation():
    provider = BedrockAsyncProvider(config)

    try:
        response = await provider.generate(messages)
    except ClientError as e:
        print(f"AWS error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
```

## Performance Considerations

### When to Use BedrockAsyncProvider

✅ **Use BedrockAsyncProvider when:**
- You have an async application architecture
- You're making multiple concurrent LLM calls
- You need efficient I/O handling
- You're using async frameworks (FastAPI, aiohttp, etc.)

### When to Use BedrockProvider

✅ **Use BedrockProvider when:**
- You have a sync-only application
- You're making single, sequential calls
- You want to avoid async complexity

## Testing

Run the included test script:

```bash
python test_bedrock_async.py
```

Make sure you have valid AWS credentials configured.

## Troubleshooting

### Import Error: No module named 'aiobotocore'

Install the bedrock optional dependencies:

```bash
pip install -e ".[bedrock]"
```

Or install manually:

```bash
pip install aiobotocore boto3 botocore
```

### Authentication Error

- Verify your AWS credentials are correct
- Check your IAM permissions for Bedrock access
- Ensure the region supports Bedrock

### Model Not Found

- Verify the model ID is correct
- Check if the model is available in your region
- Request access to the model in AWS Console

## Cost Tracking

Both providers automatically track token usage and costs:

```python
provider = BedrockAsyncProvider(config)

# After generation
cost_info = provider.get_cost()
print(f"Total cost: ${cost_info.total_cost}")
print(f"Total tokens: {cost_info.total_tokens}")
```

## Migration from BedrockProvider

To migrate from `BedrockProvider` to `BedrockAsyncProvider`:

1. Change provider name in config: `bedrock` → `bedrock_async`
2. Ensure all calling code uses `await` with the provider methods
3. Install `aiobotocore` dependency
4. Test thoroughly with your use cases

**Example migration:**

```python
# Before (BedrockProvider)
provider = BedrockProvider(config)
response = await provider.generate(messages)  # Uses thread pool

# After (BedrockAsyncProvider)
provider = BedrockAsyncProvider(config)
response = await provider.generate(messages)  # True async
```

## Contributing

If you find issues or want to improve the provider:

1. Test your changes with `test_bedrock_async.py`
2. Ensure backward compatibility with existing configs
3. Update this documentation
4. Add tests for new features

## References

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [aiobotocore Documentation](https://aiobotocore.readthedocs.io/)
- [Anthropic Claude API](https://docs.anthropic.com/)
