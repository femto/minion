import pytest
from unittest.mock import Mock, patch
from minion.main.optillm import (
    OptillmMinion,
    CotReflectionMinion,
    PlanSearchMinion,
    SelfConsistencyMinion
)

# Mock response for OpenAI API calls
@pytest.fixture
def mock_completion():
    return Mock(
        choices=[Mock(message=Mock(content="Test response"))],
        usage=Mock(completion_tokens=10)
    )

@pytest.fixture
def mock_client(mock_completion):
    client = Mock()
    client.chat.completions.create.return_value = mock_completion
    return client

# Basic unit tests with mocked client
def test_cot_reflection_minion_process(mock_client):
    minion = CotReflectionMinion(mock_client, "gpt-4")
    response, tokens = minion.process(
        system_prompt="Test system prompt",
        initial_query="Test query"
    )
    
    assert "<thinking>" in response
    assert "<reflection>" in response
    assert "<output>" in response
    assert tokens == 20  # 10 tokens each for thinking and reflection
    assert mock_client.chat.completions.create.call_count == 2

def test_plan_search_minion_process(mock_client):
    minion = PlanSearchMinion(mock_client, "gpt-4")
    response, tokens = minion.process(
        system_prompt="Test system prompt",
        initial_query="Test query"
    )
    
    assert response == "Test response"
    assert tokens == 10
    assert mock_client.chat.completions.create.call_count == 1

def test_self_consistency_minion_process(mock_client):
    minion = SelfConsistencyMinion(mock_client, "gpt-4", num_samples=3)
    response, tokens = minion.process(
        system_prompt="Test system prompt",
        initial_query="Test query"
    )
    
    assert response == "Test response"
    assert tokens == 30  # 10 tokens * 3 samples
    assert mock_client.chat.completions.create.call_count == 3

# LLM Integration tests
@pytest.mark.llm_integration
def test_cot_reflection_integration():
    from openai import OpenAI
    import os
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=api_key)
    minion = CotReflectionMinion(client, "gpt-3.5-turbo")
    
    response, tokens = minion.process(
        system_prompt="You are a helpful assistant.",
        initial_query="What is the best way to learn programming?"
    )
    
    assert "<thinking>" in response
    assert "<reflection>" in response
    assert "<output>" in response
    assert tokens > 0

@pytest.mark.llm_integration
def test_plan_search_integration():
    from openai import OpenAI
    import os
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=api_key)
    minion = PlanSearchMinion(client, "gpt-3.5-turbo")
    
    response, tokens = minion.process(
        system_prompt="You are a helpful assistant.",
        initial_query="How would you plan a birthday party?"
    )
    
    assert len(response) > 0
    assert tokens > 0

@pytest.mark.llm_integration
def test_self_consistency_integration():
    from openai import OpenAI
    import os
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=api_key)
    minion = SelfConsistencyMinion(client, "gpt-3.5-turbo", num_samples=2)
    
    response, tokens = minion.process(
        system_prompt="You are a helpful assistant.",
        initial_query="What is 15 * 17?"
    )
    
    assert len(response) > 0
    assert tokens > 0

# Error handling tests
def test_optillm_minion_error_handling(mock_client):
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    minion = PlanSearchMinion(mock_client, "gpt-4")
    
    with pytest.raises(Exception) as exc_info:
        minion.process("Test prompt", "Test query")
    
    assert str(exc_info.value) == "API Error" 