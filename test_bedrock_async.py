"""
Simple test script for BedrockAsyncProvider
"""
import asyncio
from minion.providers.bedrock_async_provider import BedrockAsyncProvider
from minion.schema.message_types import Message
from minion.configs.config import LLMConfig


async def test_bedrock_async():
    """Test basic async generation"""
    # 创建配置
    config = LLMConfig(
        provider="bedrock_async",
        model="anthropic.claude-3-5-sonnet-20240620-v1:0",
        region="us-east-1",
        temperature=0.7
    )

    # 创建provider
    provider = BedrockAsyncProvider(config)

    # 创建测试消息
    messages = [
        Message(role="user", content="Hello! Please respond with 'Hello, World!'")
    ]

    print("Testing async generation...")
    try:
        # 测试异步生成
        response = await provider.generate(messages, temperature=0.7)
        print(f"✓ Async generation successful!")
        print(f"Response: {response[:100]}..." if len(response) > 100 else f"Response: {response}")
    except Exception as e:
        print(f"✗ Async generation failed: {e}")
        return

    print("\nTesting async streaming...")
    try:
        # 测试异步流式生成
        messages = [
            Message(role="user", content="Count from 1 to 5, each number on a new line.")
        ]

        chunks = []
        async for chunk in provider.generate_stream(messages, temperature=0.7):
            chunks.append(chunk)
            print(chunk, end='', flush=True)

        print(f"\n✓ Async streaming successful! Received {len(chunks)} chunks")
    except Exception as e:
        print(f"\n✗ Async streaming failed: {e}")
        return

    print("\n✓ All tests passed!")


async def test_bedrock_async_stream_response():
    """Test async stream response (full response format)"""
    config = LLMConfig(
        provider="bedrock_async",
        model="anthropic.claude-3-5-sonnet-20240620-v1:0",
        region="us-east-1",
        temperature=0.7
    )

    provider = BedrockAsyncProvider(config)

    messages = [
        Message(role="user", content="Say hello in 3 words.")
    ]

    print("Testing async stream response...")
    try:
        response = await provider.generate_stream_response(messages, temperature=0.7)
        print(f"✓ Stream response successful!")
        print(f"Response type: {type(response)}")
        print(f"Model: {response.model}")
        print(f"Content: {response.choices[0].message.content}")
        print(f"Tokens: {response.usage.total_tokens}")
    except Exception as e:
        print(f"✗ Stream response failed: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("BedrockAsyncProvider Test Suite")
    print("=" * 60)
    print("\nNote: This test requires valid AWS credentials.")
    print("Set them in your config or environment variables.\n")

    # 运行测试
    asyncio.run(test_bedrock_async())
    print("\n" + "=" * 60)
    asyncio.run(test_bedrock_async_stream_response())
