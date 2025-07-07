#!/usr/bin/env python3
"""
Test script for the improved CodeAgent (code minion)
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from minion.agents.code_agent import CodeAgent
from minion.main.input import Input

async def test_simple_calculation():
    """Test simple mathematical calculation"""
    print("=== Testing Simple Calculation ===")
    
    agent = CodeAgent()
    
    # Test simple math problem
    problem = "Calculate the area of a circle with radius 5"
    
    try:
        result = await agent.solve_problem(problem)
        print(f"Problem: {problem}")
        print(f"Result: {result}")
        print("✅ Simple calculation test passed!")
        return True
    except Exception as e:
        print(f"❌ Simple calculation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_data_analysis():
    """Test data analysis capabilities"""
    print("\n=== Testing Data Analysis ===")
    
    agent = CodeAgent()
    
    # Test data analysis
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    question = "What is the mean and standard deviation of this data?"
    
    try:
        result = await agent.analyze_data(data, question)
        print(f"Data: {data}")
        print(f"Question: {question}")
        print(f"Result: {result}")
        print("✅ Data analysis test passed!")
        return True
    except Exception as e:
        print(f"❌ Data analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_multi_step_problem():
    """Test multi-step problem solving"""
    print("\n=== Testing Multi-Step Problem ===")
    
    agent = CodeAgent()
    
    # Test multi-step problem
    problem = """
    A company has the following sales data for 6 months:
    Month 1: $10,000
    Month 2: $12,000
    Month 3: $15,000
    Month 4: $11,000
    Month 5: $18,000
    Month 6: $14,000
    
    Calculate:
    1. Total sales for the 6 months
    2. Average monthly sales
    3. Which month had the highest sales
    4. What is the growth rate from month 1 to month 6
    """
    
    try:
        result = await agent.solve_problem(problem)
        print(f"Problem: {problem}")
        print(f"Result: {result}")
        print("✅ Multi-step problem test passed!")
        return True
    except Exception as e:
        print(f"❌ Multi-step problem test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_code_execution():
    """Test direct code execution through Input"""
    print("\n=== Testing Direct Code Execution ===")
    
    agent = CodeAgent()
    
    # Test direct code execution
    input_obj = Input(query="Write Python code to find the first 10 Fibonacci numbers", route='python')
    
    try:
        result = await agent.run_async(input_obj)
        print(f"Query: {input_obj.query}")
        print(f"Result: {result}")
        print("✅ Direct code execution test passed!")
        return True
    except Exception as e:
        print(f"❌ Direct code execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting CodeAgent (Code Minion) Tests")
    print("=" * 50)
    
    tests = [
        test_simple_calculation,
        test_data_analysis,
        test_multi_step_problem,
        test_code_execution
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if await test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! CodeAgent is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    asyncio.run(main()) 