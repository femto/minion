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
    
    @pytest.mark.asyncio
    async def test_memory_persistence(self):
        """Test that memory persists between interactions when state tracking is enabled"""
        agent = CodeAgent(name="test_agent", enable_state_tracking=True)
        await agent.setup()
        
        # Mock the run_async to avoid actual execution
        original_run_async = agent.run_async
        mock_responses = ["First response", "Second response"]
        response_index = 0
        
        async def mock_run_async(*args, **kwargs):
            nonlocal response_index
            response = mock_responses[response_index]
            response_index += 1
            return response
            
        agent.run_async = mock_run_async
        
        # First interaction
        input1 = Input(query="What is the capital of France?")
        await agent._record_interaction(input1, "Paris is the capital of France.", False)
        
        # Second interaction with follow-up question
        input2 = Input(query="What is its population?")
        await agent._record_interaction(input2, "Paris has a population of about 2.2 million people.", False)
        
        # Verify history contains both interactions
        history = agent.get_conversation_history()
        assert len(history) == 4  # 2 questions + 2 answers
        assert history[0]["role"] == "user"
        assert "France" in history[0]["content"]
        assert history[1]["role"] == "assistant" 
        assert "Paris" in history[1]["content"]
        assert history[2]["role"] == "user"
        assert "population" in history[2]["content"]
        assert history[3]["role"] == "assistant"
        assert "2.2 million" in history[3]["content"]
        
        # Restore original method
        agent.run_async = original_run_async
    
    @pytest.mark.asyncio
    async def test_state_save_and_load(self):
        """Test that state can be saved and loaded"""
        agent = CodeAgent(name="test_agent", enable_state_tracking=True)
        await agent.setup()
        
        # Add some data to the state
        agent.add_to_history("user", "Test query")
        agent.add_to_history("assistant", "Test response")
        agent.persistent_state["test_variable"] = "test_value"
        agent.persistent_state["learned_patterns"] = ["pattern1", "pattern2"]
        
        # Save the state
        state = agent.get_state()
        
        # Create a new agent
        new_agent = CodeAgent(name="new_agent", enable_state_tracking=True)
        await new_agent.setup()
        
        # Load the state into the new agent
        new_agent.load_state(state)
        
        # Verify the state was loaded correctly
        assert len(new_agent.get_conversation_history()) == 2
        assert new_agent.persistent_state["test_variable"] == "test_value"
        assert len(new_agent.persistent_state["learned_patterns"]) == 2
        assert "pattern1" in new_agent.persistent_state["learned_patterns"]
        
    @pytest.mark.asyncio
    async def test_reset_state(self):
        """Test that reset_state clears conversation history but preserves patterns"""
        agent = CodeAgent(name="test_agent", enable_state_tracking=True)
        await agent.setup()
        
        # Add some data to the state
        agent.add_to_history("user", "Test query")
        agent.add_to_history("assistant", "Test response")
        agent.persistent_state["variables"] = {"var1": 10, "var2": 20}
        agent.persistent_state["learned_patterns"] = ["important_pattern"]
        
        # Reset the state
        agent.reset_state()
        
        # Verify conversation history is cleared
        assert len(agent.get_conversation_history()) == 0
        
        # Verify variables are cleared
        assert len(agent.persistent_state["variables"]) == 0
        
        # Verify learned patterns are preserved
        assert len(agent.persistent_state["learned_patterns"]) == 1
        assert "important_pattern" in agent.persistent_state["learned_patterns"]