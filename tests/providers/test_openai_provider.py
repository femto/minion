import inspect
from asyncio import iscoroutinefunction
from unittest.mock import AsyncMock, patch

import pytest

from minion.configs.config import LLMConfig
from minion.message_types import Message
from minion.providers.cost import CostManager
from minion.providers.openai_provider import OpenAIProvider


@pytest.fixture
def mock_openai_client():
    with patch("openai.AsyncOpenAI") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.chat.completions.create = AsyncMock()
        yield mock_instance


@pytest.fixture
def openai_provider(mock_openai_client):
    config = LLMConfig(
        provider="openai", model="gpt-3.5-turbo", api_key="test_key", base_url="https://api.openai.com/v1"
    )
    provider = OpenAIProvider(config)
    provider.client = mock_openai_client
    return provider


@pytest.mark.asyncio
async def test_openai_provider_cost_calculation(openai_provider, mock_openai_client):
    # 模拟 OpenAI API 响应
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="Test response"))]
    mock_response.usage = AsyncMock(completion_tokens=10)
    mock_openai_client.chat.completions.create.return_value = mock_response

    # 模拟 CostManager.calculate 方法
    with patch("minion.providers.cost.CostManager.calculate", return_value=(20, 10)):
        # 模拟消息
        messages = [Message(role="user", content="Hello, AI!")]

        # 调用 generate 方法
        response = await openai_provider.generate(messages)

        # 验证响应内容
        assert response == "Test response"

        # 验证成本计算
        cost_manager = openai_provider.get_cost()
        assert isinstance(cost_manager, CostManager)
        assert cost_manager.total_prompt_tokens == 20
        assert cost_manager.total_completion_tokens == 10

        # 验证 OpenAI API 被正确调用
        mock_openai_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_openai_provider_stream_cost_calculation(openai_provider, mock_openai_client):
    # Create mock chunks as a list of AsyncMock objects
    mock_chunks = [
        AsyncMock(
            choices=[
                AsyncMock(
                    delta=AsyncMock(content="Test "),
                    finish_reason=None
                )
            ],
            usage=None
        ),
        AsyncMock(
            choices=[
                AsyncMock(
                    delta=AsyncMock(content="response "),
                    finish_reason=None
                )
            ],
            usage=None
        ),
        AsyncMock(
            choices=[
                AsyncMock(
                    delta=AsyncMock(content="stream."),
                    finish_reason="stop"
                )
            ],
            usage={
                "prompt_tokens": 15,
                "completion_tokens": 3,
                "total_tokens": 18
            }
        ),
    ]

    # Create an async generator function that will yield our mock chunks
    async def mock_stream():
        for chunk in mock_chunks:
            yield chunk

    # Create the mock response stream
    mock_response = mock_stream()

    # Set up the mock client to return our stream
    mock_openai_client.chat.completions.create.return_value = mock_response

    # 模拟 CostManager.calculate 方法
    with patch("minion.providers.cost.CostManager.calculate", return_value=(15, 3)):
        # 模拟消息
        messages = [Message(role="user", content="Hello, AI!")]

        # 调用 generate_stream 方法并收集结果
        response = await openai_provider.generate_stream(messages)

        # 验证响应内容
        assert response == "Test response stream."

        # 验证成本计算
        cost_manager = openai_provider.get_cost()
        assert isinstance(cost_manager, CostManager)
        assert cost_manager.total_prompt_tokens == 15
        assert cost_manager.total_completion_tokens == 3

        # 验证 OpenAI API 被正确调用
        mock_openai_client.chat.completions.create.assert_called_once()
