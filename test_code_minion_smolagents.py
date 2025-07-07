#!/usr/bin/env python3

"""
Test script for CodeMinion with smolagents-style functionality
"""

import asyncio
import sys
import os
import pytest

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from minion import config
from minion.main.brain import Brain
from minion.main.local_python_executor import LocalPythonExecutor
from minion.main.worker import CodeMinion
from minion.main.input import Input
from minion.providers import create_llm_provider


@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_code_minion_circle_area():
    """Test CodeMinion with circle area calculation"""
    print("=== Testing CodeMinion with Circle Area Calculation ===")
    
    # Setup LLM and LocalPythonExecutor
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    # Create LocalPythonExecutor
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["math"],
        max_print_outputs_length=50000,
        additional_functions={}
    )
    
    # Create Brain with LocalPythonExecutor
    brain = Brain(python_env=python_executor, llm=llm)
    
    # Create Input
    input_data = Input(query="Calculate the area of a circle with radius 5. Use math.pi for accuracy.")
    
    # Create CodeMinion
    code_minion = CodeMinion(input=input_data, brain=brain)
    
    try:
        result = await code_minion.execute()
        print(f"Problem: {input_data.query}")
        print(f"Result: {result}")
        print("✅ Circle area test passed!")
        return True
    except Exception as e:
        print(f"❌ Circle area test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_code_minion_fibonacci():
    """Test CodeMinion with Fibonacci calculation"""
    print("\n=== Testing CodeMinion with Fibonacci Sequence ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["math"],
        max_print_outputs_length=50000,
        additional_functions={}
    )
    
    brain = Brain(python_env=python_executor, llm=llm)
    input_data = Input(query="Calculate the 10th Fibonacci number. Show the sequence up to the 10th number.")
    
    code_minion = CodeMinion(input=input_data, brain=brain)
    
    try:
        result = await code_minion.execute()
        print(f"Problem: {input_data.query}")
        print(f"Result: {result}")
        print("✅ Fibonacci test passed!")
        return True
    except Exception as e:
        print(f"❌ Fibonacci test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_code_minion_with_error():
    """Test CodeMinion error handling and retry"""
    print("\n=== Testing CodeMinion Error Handling ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["math"],
        max_print_outputs_length=50000,
        additional_functions={}
    )
    
    brain = Brain(python_env=python_executor, llm=llm)
    # This problem might cause an error initially, testing retry logic
    input_data = Input(query="Calculate the square root of -1. If there's an error, explain what happened and provide an alternative solution.")
    
    code_minion = CodeMinion(input=input_data, brain=brain)
    
    try:
        result = await code_minion.execute()
        print(f"Problem: {input_data.query}")
        print(f"Result: {result}")
        print("✅ Error handling test passed!")
        return True
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


@pytest.mark.llm_integration
@pytest.mark.asyncio
async def test_code_minion_data_analysis():
    """Test CodeMinion with data analysis"""
    print("\n=== Testing CodeMinion with Data Analysis ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["math", "json"],
        max_print_outputs_length=50000,
        additional_functions={}
    )
    
    brain = Brain(python_env=python_executor, llm=llm)
    
    # Data analysis problem
    query = """
    I have sales data for 5 months: 
    Jan: 1000, Feb: 1200, Mar: 1500, Apr: 1300, May: 1800
    
    Calculate:
    1. Average monthly sales
    2. Growth rate from Jan to May
    3. Which month had the highest growth compared to the previous month
    """
    
    input_data = Input(query=query)
    code_minion = CodeMinion(input=input_data, brain=brain)
    
    try:
        result = await code_minion.execute()
        print(f"Problem: {query}")
        print(f"Result: {result}")
        print("✅ Data analysis test passed!")
        return True
    except Exception as e:
        print(f"❌ Data analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


@pytest.mark.asyncio
async def test_local_python_executor_interface():
    """Test LocalPythonExecutor interface directly"""
    print("\n=== Testing LocalPythonExecutor Interface ===")
    
    executor = LocalPythonExecutor(
        additional_authorized_imports=["math"],
        max_print_outputs_length=50000
    )
    
    # Initialize executor with tools like smolagents does
    executor.send_variables(variables={})
    executor.send_tools({})  # This will set up BASE_PYTHON_TOOLS
    
    # Test simple calculation
    test_code = """
import math
radius = 5
area = math.pi * radius ** 2
print(f"Area of circle with radius {radius}: {area}")
"""
    
    try:
        output, logs, is_final_answer = executor(test_code)
        print(f"Code executed: {test_code}")
        print(f"Output: {output}")
        print(f"Logs: {logs}")
        print(f"Is final answer: {is_final_answer}")
        print("✅ LocalPythonExecutor interface test passed!")
        return True
    except Exception as e:
        print(f"❌ LocalPythonExecutor interface test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("Testing CodeMinion with smolagents-style functionality")
    print("=" * 60)
    
    test_results = []
    
    # Test LocalPythonExecutor interface first
    test_results.append(await test_local_python_executor_interface())
    
    # Test CodeMinion functionality
    test_results.append(await test_code_minion_circle_area())
    test_results.append(await test_code_minion_fibonacci())
    test_results.append(await test_code_minion_with_error())
    test_results.append(await test_code_minion_data_analysis())
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    print(f"\n{'='*60}")
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! CodeMinion smolagents functionality is working correctly.")
    else:
        print("❌ Some tests failed. Please check the implementation.")
        
    return passed == total


if __name__ == "__main__":
    asyncio.run(main()) 