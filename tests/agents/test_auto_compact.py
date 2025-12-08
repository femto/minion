"""Tests for auto compact feature in BaseAgent."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass, field

from minion.agents.base_agent import BaseAgent
from minion.providers.base_provider import BaseProvider
from minion.types.agent_state import AgentState
from minion.types.history import History
from minion.utils.model_price import get_model_context_window, DEFAULT_CONTEXT_WINDOW


def create_mock_llm(model_name="gpt-4o"):
    """Create a mock LLM that passes isinstance check."""
    mock_llm = Mock(spec=BaseProvider)
    mock_llm.config = Mock()
    mock_llm.config.model = model_name
    return mock_llm


def create_async_mock_llm(model_name="gpt-4o"):
    """Create an async mock LLM that passes isinstance check."""
    mock_llm = Mock(spec=BaseProvider)
    mock_llm.config = Mock()
    mock_llm.config.model = model_name
    mock_llm.generate = AsyncMock(return_value={"content": "Summary of conversation"})
    mock_llm.chat = AsyncMock(return_value={"content": "Summary of conversation"})
    return mock_llm


class TestGetModelContextWindow:
    """Tests for get_model_context_window function."""

    def test_known_model_returns_context_info(self):
        """Test that known models return correct context window info."""
        # GPT-4o should have context window info
        result = get_model_context_window("gpt-4o")
        assert "max_input_tokens" in result
        assert "max_output_tokens" in result
        assert result["max_input_tokens"] > 0

    def test_unknown_model_returns_defaults(self):
        """Test that unknown models return default values."""
        result = get_model_context_window("unknown-model-xyz")
        assert result["max_input_tokens"] == DEFAULT_CONTEXT_WINDOW
        assert result["max_output_tokens"] == 4096

    def test_returns_dict_structure(self):
        """Test that result has expected dictionary structure."""
        result = get_model_context_window("gpt-4o-mini")
        assert isinstance(result, dict)
        assert "max_input_tokens" in result
        assert "max_output_tokens" in result
        assert "max_tokens" in result


class TestBaseAgentAutoCompactConfig:
    """Tests for auto compact configuration in BaseAgent."""

    def test_default_config_values(self):
        """Test that default config values are set correctly."""
        agent = BaseAgent()
        assert agent.auto_compact_enabled is True
        assert agent.auto_compact_threshold == 0.92
        assert agent.auto_compact_keep_recent == 10
        assert agent.default_context_window == 128000
        assert agent.compact_model is None

    def test_custom_config_values(self):
        """Test that custom config values can be set."""
        agent = BaseAgent(
            auto_compact_enabled=False,
            auto_compact_threshold=0.80,
            auto_compact_keep_recent=5,
            default_context_window=64000,
            compact_model="gpt-4o-mini"
        )
        assert agent.auto_compact_enabled is False
        assert agent.auto_compact_threshold == 0.80
        assert agent.auto_compact_keep_recent == 5
        assert agent.default_context_window == 64000
        assert agent.compact_model == "gpt-4o-mini"


class TestBaseAgentCompactMethods:
    """Tests for compact methods in BaseAgent."""

    def test_get_context_window_limit_without_llm(self):
        """Test _get_context_window_limit returns default when no LLM."""
        agent = BaseAgent()
        limit = agent._get_context_window_limit()
        assert limit == agent.default_context_window

    def test_get_context_window_limit_with_llm(self):
        """Test _get_context_window_limit uses model from LLM config."""
        mock_llm = create_mock_llm("gpt-4o")
        agent = BaseAgent()
        agent.llm = mock_llm  # Set after construction to avoid conversion
        limit = agent._get_context_window_limit()
        # Should get actual context window from model info
        assert limit > 0

    def test_calculate_current_tokens_empty_history(self):
        """Test _calculate_current_tokens returns 0 for empty history."""
        agent = BaseAgent()
        history = History()
        tokens = agent._calculate_current_tokens(history)
        assert tokens == 0

    def test_calculate_current_tokens_with_messages(self):
        """Test _calculate_current_tokens counts tokens correctly."""
        agent = BaseAgent()
        history = History()
        history.append({"role": "user", "content": "Hello, world!"})
        history.append({"role": "assistant", "content": "Hi there!"})
        tokens = agent._calculate_current_tokens(history)
        assert tokens > 0

    def test_should_compact_disabled(self):
        """Test _should_compact returns False when disabled."""
        agent = BaseAgent(auto_compact_enabled=False)
        history = History()
        for i in range(20):
            history.append({"role": "user", "content": "x" * 10000})
        assert agent._should_compact(history) is False

    def test_should_compact_not_enough_messages(self):
        """Test _should_compact returns False when not enough messages."""
        agent = BaseAgent(auto_compact_keep_recent=10)
        history = History()
        for i in range(5):
            history.append({"role": "user", "content": "Hello"})
        assert agent._should_compact(history) is False

    def test_should_compact_below_threshold(self):
        """Test _should_compact returns False when below threshold."""
        agent = BaseAgent(
            auto_compact_threshold=0.92,
            default_context_window=128000
        )
        history = History()
        # Add small messages that won't exceed threshold
        for i in range(15):
            history.append({"role": "user", "content": "Hello"})
        assert agent._should_compact(history) is False

    def test_get_compact_llm_uses_agent_llm(self):
        """Test _get_compact_llm returns agent's LLM when no compact_model."""
        mock_llm = create_mock_llm()
        agent = BaseAgent()
        agent.llm = mock_llm  # Set after construction to avoid conversion
        result = agent._get_compact_llm()
        assert result is mock_llm

    @patch('minion.agents.base_agent.create_llm_from_model')
    def test_get_compact_llm_uses_compact_model(self, mock_create):
        """Test _get_compact_llm creates LLM from compact_model."""
        mock_compact_llm = Mock()
        mock_create.return_value = mock_compact_llm
        agent = BaseAgent(compact_model="gpt-4o-mini")
        result = agent._get_compact_llm()
        mock_create.assert_called_once_with("gpt-4o-mini")
        assert result is mock_compact_llm


class TestBaseAgentCompactHistory:
    """Tests for _compact_history method."""

    @pytest.mark.asyncio
    async def test_compact_history_not_enough_messages(self):
        """Test _compact_history returns unchanged history if not enough messages."""
        agent = BaseAgent(auto_compact_keep_recent=10)
        history = History()
        for i in range(5):
            history.append({"role": "user", "content": "Hello"})
        result = await agent._compact_history(history)
        assert len(result) == len(history)

    @pytest.mark.asyncio
    async def test_compact_history_no_llm(self):
        """Test _compact_history returns unchanged history if no LLM."""
        agent = BaseAgent(auto_compact_keep_recent=2)
        history = History()
        for i in range(10):
            history.append({"role": "user", "content": f"Message {i}"})
        result = await agent._compact_history(history)
        # Without LLM, should return original history
        assert len(result) == len(history)

    @pytest.mark.asyncio
    async def test_compact_history_preserves_system_messages(self):
        """Test _compact_history preserves system messages."""
        mock_llm = create_async_mock_llm()

        agent = BaseAgent(auto_compact_keep_recent=2)
        agent.llm = mock_llm  # Set after construction to avoid conversion
        history = History()
        history.append({"role": "system", "content": "You are a helpful assistant."})
        for i in range(10):
            history.append({"role": "user", "content": f"Message {i}"})

        result = await agent._compact_history(history)

        # Should preserve original system message
        system_msgs = [m for m in result if m.get("role") == "system"]
        assert len(system_msgs) >= 1
        # First system message should be original
        assert "You are a helpful assistant." in system_msgs[0]["content"]

    @pytest.mark.asyncio
    async def test_compact_history_keeps_recent_messages(self):
        """Test _compact_history keeps recent messages intact."""
        mock_llm = create_async_mock_llm()

        agent = BaseAgent(auto_compact_keep_recent=3)
        agent.llm = mock_llm  # Set after construction to avoid conversion
        history = History()
        for i in range(10):
            history.append({"role": "user", "content": f"Message {i}"})

        result = await agent._compact_history(history)

        # Last 3 messages should be preserved
        recent_contents = [m.get("content") for m in list(result)[-3:]]
        assert "Message 7" in recent_contents
        assert "Message 8" in recent_contents
        assert "Message 9" in recent_contents


class TestBaseAgentCompactNow:
    """Tests for compact_now method."""

    @pytest.mark.asyncio
    async def test_compact_now_uses_self_state(self):
        """Test compact_now uses self.state when no state provided."""
        mock_llm = create_async_mock_llm()

        agent = BaseAgent(auto_compact_keep_recent=2)
        agent.llm = mock_llm  # Set after construction to avoid conversion
        agent.state = AgentState()
        for i in range(10):
            agent.state.history.append({"role": "user", "content": f"Message {i}"})

        await agent.compact_now()

        # State history should be compacted
        assert len(agent.state.history) < 10

    @pytest.mark.asyncio
    async def test_compact_now_uses_provided_state(self):
        """Test compact_now uses provided state."""
        mock_llm = create_async_mock_llm()

        agent = BaseAgent(auto_compact_keep_recent=2)
        agent.llm = mock_llm  # Set after construction to avoid conversion
        state = AgentState()
        for i in range(10):
            state.history.append({"role": "user", "content": f"Message {i}"})

        await agent.compact_now(state)

        # Provided state history should be compacted
        assert len(state.history) < 10


class TestBuildCompactPrompt:
    """Tests for _build_compact_prompt method."""

    def test_build_compact_prompt_formats_messages(self):
        """Test _build_compact_prompt formats messages correctly."""
        agent = BaseAgent()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        prompt = agent._build_compact_prompt(messages)

        assert "[USER]: Hello" in prompt
        assert "[ASSISTANT]: Hi there!" in prompt
        assert "summarize" in prompt.lower()

    def test_build_compact_prompt_truncates_long_content(self):
        """Test _build_compact_prompt truncates very long messages."""
        agent = BaseAgent()
        long_content = "x" * 3000
        messages = [{"role": "user", "content": long_content}]
        prompt = agent._build_compact_prompt(messages)

        assert "[truncated]" in prompt
        assert len(prompt) < len(long_content)
