#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CodeMinion Example: Demonstrating "think in code" functionality

This example shows how to use the CodeMinion agent for various tasks:
- Mathematical problem solving
- Data analysis
- Complex reasoning with self-reflection
"""

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minion import config
from minion.agents import CodeMinion
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.main.brain import Brain
from minion.providers import create_llm_provider


async def basic_math_example():
    """Example 1: Basic mathematical problem solving"""
    print("=== Basic Math Example ===")
    
    # Setup LLM and environment
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    # Use the existing Python environment
    python_env = RpycPythonEnv(port=3006)
    brain = Brain(python_env=python_env, llm=llm)
    
    # Create CodeMinion
    code_minion = CodeMinion(brain=brain)
    
    # Solve a math problem
    result = await code_minion.solve_problem(
        "Calculate the area of a circle with radius 5, and then find what radius would give double that area."
    )
    print(f"Result: {result}")
    print()


async def data_analysis_example():
    """Example 2: Data analysis with reflection"""
    print("=== Data Analysis Example ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    python_env = RpycPythonEnv(port=3006)
    brain = Brain(python_env=python_env, llm=llm)
    
    # Create CodeMinion with reflection enabled
    code_minion = CodeMinion(brain=brain, enable_reflection=True)
    
    # Sample data
    sales_data = [
        {"month": "Jan", "sales": 1000, "costs": 800},
        {"month": "Feb", "sales": 1200, "costs": 900},
        {"month": "Mar", "sales": 1500, "costs": 1100},
        {"month": "Apr", "sales": 1300, "costs": 1000},
        {"month": "May", "sales": 1800, "costs": 1200},
    ]
    
    # Analyze the data
    result = await code_minion.analyze_data(
        sales_data, 
        "What are the trends in profit margin over these months? Which month had the best performance?"
    )
    print(f"Analysis Result: {result}")
    print()


async def complex_reasoning_example():
    """Example 3: Complex reasoning with multiple steps"""
    print("=== Complex Reasoning Example ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    python_env = RpycPythonEnv(port=3006)
    brain = Brain(python_env=python_env, llm=llm)
    
    # Create CodeMinion with lower reflection threshold
    code_minion = CodeMinion(brain=brain, enable_reflection=True)
    if code_minion.thinking_engine:
        code_minion.thinking_engine.reflection_triggers['step_count'] = 3
    
    # Complex problem that requires multiple steps
    problem = """
    A company has the following situation:
    - They have 100 employees
    - Each employee works 40 hours per week
    - The company pays $25 per hour on average
    - They want to increase productivity by 20%
    - They're considering either hiring more people or increasing hours
    
    Calculate:
    1. Current weekly labor cost
    2. If they hire 20% more people, what's the new cost?
    3. If they increase hours by 20% instead, what's the new cost?
    4. Which option is more cost-effective?
    5. What would be the hourly productivity gain needed to justify the hiring option?
    """
    
    result = await code_minion.solve_problem(problem)
    print(f"Complex Analysis Result: {result}")
    print()


async def fibonacci_optimization_example():
    """Example 4: Iterative problem solving with optimization"""
    print("=== Fibonacci Optimization Example ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    python_env = RpycPythonEnv(port=3006)
    brain = Brain(python_env=python_env, llm=llm)
    
    # Create CodeMinion
    code_minion = CodeMinion(brain=brain)
    
    # Problem that can be optimized
    problem = """
    Write a function to calculate the 50th Fibonacci number.
    Start with a basic recursive approach, then optimize it.
    Compare the performance of different approaches.
    """
    
    result = await code_minion.solve_problem(problem)
    print(f"Fibonacci Optimization Result: {result}")
    print()


async def streaming_example():
    """Example 5: Streaming results to see thinking process"""
    print("=== Streaming Example ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    python_env = RpycPythonEnv(port=3006)
    brain = Brain(python_env=python_env, llm=llm)
    
    # Create CodeMinion
    code_minion = CodeMinion(brain=brain)
    
    # Use streaming to see the thinking process
    problem = "Calculate the compound interest on $1000 at 5% annual rate for 10 years, compounded monthly."
    
    print("Streaming thinking process:")
    try:
        result = await code_minion.run(problem, streaming=True)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error during execution: {e}")
        # Run normally without streaming
        final_result = await code_minion.run(problem)
        print(f"Final result: {final_result}")
    
    print()


async def main():
    """Run all examples"""
    print("CodeMinion 'Think in Code' Examples")
    print("=" * 50)
    
    try:
        await basic_math_example()
        await data_analysis_example()
        await complex_reasoning_example()
        await fibonacci_optimization_example()
        await streaming_example()
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())