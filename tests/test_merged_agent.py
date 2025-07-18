"""
Test the merged CodeAgent with state tracking functionality
"""

import pytest
import asyncio
from minion.agents.code_agent import CodeAgent
from minion.main.input import Input
from minion.main.brain import Brain

class TestMergedAgent:
    @pytest.mark.asyncio
    async def test_state_tracking_disabled_by_default(self):
        """Test that state tracking is disabled by default"""
        agent = CodeAgent(name="test_agent")
        await agent.setup()
        
        # Verify state tracking is disabled by default
        assert agent.enable_state_tracking is False
        assert agent.get_state() == {}
        assert agent.get_conversation_history() == []
        
    @pytest.mark.asyncio
    async def test_state_tracking_enabled(self):
        """Test that state tracking works when enabled"""
        agent = CodeAgent(name="test_agent", enable_state_tracking=True)
        await agent.setup()
        
        # Verify state tracking is enabled
        assert agent.enable_state_tracking is True
        
        # Mock the run_async to avoid actual execution
        original_run_async = agent.run_async
        async def mock_run_async(task, **kwargs):
            return "Test response"
        agent.run_async = mock_run_async
        
        # Run a test query
        input_obj = Input(query="Test query")
        await agent._record_interaction(input_obj, "Test response", False)
        
        # Verify conversation was recorded
        history = agent.get_conversation_history()
        assert len(history) == 2  # Should have user input and assistant response
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Test query"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Test response"
        
        # Test reset functionality
        agent.reset_state()
        assert len(agent.get_conversation_history()) == 0
        
        # Restore original method
        agent.run_async = original_run_async
        
    @pytest.mark.asyncio
    async def test_add_conversation_context(self):
        """Test that conversation context is added to input when state tracking is enabled"""
        agent = CodeAgent(name="test_agent", enable_state_tracking=True)
        await agent.setup()
        
        # Add some conversation history
        agent.add_to_history("user", "First query")
        agent.add_to_history("assistant", "First response")
        
        # Create a new input
        input_obj = Input(query="Second query")
        
        # Add conversation context
        enhanced_input = agent._add_conversation_context(input_obj)
        
        # Verify context was added
        assert "Conversation Context" in enhanced_input.query
        assert "USER: First query" in enhanced_input.query
        assert "ASSISTANT: First response" in enhanced_input.query
        assert "Second query" in enhanced_input.query