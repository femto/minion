from minion.actions.lmp_action_node import LmpActionNode
from unittest.mock import AsyncMock, MagicMock
import asyncio

async def test():
    # Create a mock LLM provider
    mock_llm = MagicMock()
    mock_llm.generate_stream = AsyncMock(return_value="Hello from the mock LLM!")
    mock_llm.config = MagicMock()
    mock_llm.config.temperature = 0.7
    mock_llm.config.model = "mock-model"

    # Create the LmpActionNode with our mock
    node = LmpActionNode(mock_llm)

    # Test with dictionary format
    messages = {"role": "user", "content": "Hello, world!"}
    print(f"Input message: {messages}")

    # This should convert the message to the right format without errors
    try:
        # We don't actually need to await the result since we're just testing the format conversion
        await node.execute(messages)
        print("✅ Dictionary message format works!")
    except Exception as e:
        print(f"❌ Error with dictionary format: {e}")

if __name__ == "__main__":
    asyncio.run(test())
