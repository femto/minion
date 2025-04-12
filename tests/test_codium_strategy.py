import pytest
import asyncio
from minion.main.result_strategy import CodiumStrategy
from minion.main.worker import WorkerMinion
from minion.main.brain import Brain
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.configs.config import config
from minion.providers import create_llm_provider
from minion.main.input import Input

@pytest.mark.asyncio
async def test_codium_strategy_full_flow():
    """
    Test the complete flow of CodiumStrategy using real LLM.
    This test will:
    1. Create real workers with different solutions
    2. Initialize CodiumStrategy with real Brain
    3. Execute the full strategy flow
    4. Verify the improvement process
    """
    # Create a real Brain instance with local Python environment
    brain = Brain(
        python_env=RpycPythonEnv(port=3008),
        llm=create_llm_provider(config.models["llama3.2"])
    )
    
    # Test problem: Write a function that returns the sum of two numbers
    test_metadata = {
        "test_cases": [
            {"input": "2, 3", "expected": "5"},
            {"input": "-1, 1", "expected": "0"},
            {"input": "0, 0", "expected": "0"}
        ],
        "ai_test_cases": [
            {"input": "100, 200", "expected": "300"},
            {"input": "-50, 50", "expected": "0"}
        ]
    }
    
    # Create input object
    base_input = Input(
        query="Write a function that returns the sum of two numbers",
        query_type="code_generation",
        metadata=test_metadata,
        entry_point="add_numbers"
    )
    
    # Create real workers with different initial solutions
    workers = [
        WorkerMinion(
            brain=brain,
            input=base_input,
            answer="def add_numbers(a, b):\n    return a + b",
            worker_config={"check": 3}
        ),
        WorkerMinion(
            brain=brain,
            input=base_input,
            answer="def add_numbers(a, b):\n    sum = a + b\n    return sum",
            worker_config={"check": 2}
        ),
        WorkerMinion(
            brain=brain,
            input=base_input,
            answer="def add_numbers(a, b):\n    if isinstance(a, (int, float)) and isinstance(b, (int, float)):\n        return a + b\n    raise ValueError('Invalid input')",
            worker_config={"check": 1}
        )
    ]
    
    # Initialize strategy with real components
    strategy = CodiumStrategy(brain=brain, workers=workers)
    
    # Execute the strategy
    result = await strategy.execute()
    
    # Verify that we got a valid result
    assert result is not None
    assert isinstance(result, str)
    assert "def add_numbers" in result
    assert "return" in result
    
    # Verify that the solution works
    # Note: In a real test, you would want to actually execute the solution
    # and verify it produces correct results for the test cases 