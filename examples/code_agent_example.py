#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CodeAgent Example: Demonstrating "think in code" functionality

This example shows how to use the CodeAgent for various tasks:
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
from minion.agents import CodeAgent
from minion.main.local_python_executor import LocalPythonExecutor
from minion.main.brain import Brain
from minion.providers import create_llm_provider


async def basic_math_example():
    """Example 1: Basic mathematical problem solving"""
    print("=== Basic Math Example ===")
    
    # Setup LLM and LocalPythonExecutor
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    # Use LocalPythonExecutor for Brain
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn", "requests", "json", "csv"],
        max_print_outputs_length=50000,
        additional_functions={}
    )
    
    # Create Brain with python_env
    brain = Brain(python_env=python_executor, llm=llm)
    
    # Create CodeAgent
    code_agent = CodeAgent(brain=brain)
    
    # Solve a math problem
    problem = "Calculate the area of a circle with radius 5, and then find what radius would give double that area."
    
    try:
        result = await code_agent.solve_problem(problem)
        print(f"Problem: {problem}")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    print()


async def data_analysis_example():
    """Example 2: Data analysis with reflection"""
    print("=== Data Analysis Example ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn", "json"],
        max_print_outputs_length=50000
    )
    brain = Brain(python_env=python_executor, llm=llm)
    
    # Create CodeAgent
    code_agent = CodeAgent(brain=brain)
    
    # Sample data
    sales_data = [
        {"month": "Jan", "sales": 1000, "costs": 800},
        {"month": "Feb", "sales": 1200, "costs": 900},
        {"month": "Mar", "sales": 1500, "costs": 1100},
        {"month": "Apr", "sales": 1300, "costs": 1000},
        {"month": "May", "sales": 1800, "costs": 1200},
    ]
    
    # Analyze the data
    problem = f"""
    I have sales data: {sales_data}
    
    Analyze this data and answer:
    1. What are the trends in profit margin over these months? 
    2. Which month had the best performance?
    3. Calculate the total profit for all months.
    """
    
    try:
        result = await code_agent.solve_problem(problem)
        print(f"Analysis Problem: {problem}")
        print(f"Analysis Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    print()


async def complex_reasoning_example():
    """Example 3: Complex reasoning with multiple steps"""
    print("=== Complex Reasoning Example ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["numpy", "math"],
        max_print_outputs_length=50000
    )
    brain = Brain(python_env=python_executor, llm=llm)
    
    # Create CodeAgent
    code_agent = CodeAgent(brain=brain)
    
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
    
    try:
        result = await code_agent.solve_problem(problem)
        print(f"Complex Problem: {problem}")
        print(f"Complex Analysis Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    print()


async def fibonacci_optimization_example():
    """Example 4: Iterative problem solving with optimization"""
    print("=== Fibonacci Optimization Example ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["time", "functools"],
        max_print_outputs_length=50000
    )
    brain = Brain(python_env=python_executor, llm=llm)
    
    # Create CodeAgent
    code_agent = CodeAgent(brain=brain)
    
    # Problem that can be optimized
    problem = """
    Write a function to calculate the 50th Fibonacci number.
    Start with a basic recursive approach, then optimize it.
    Compare the performance of different approaches and show the results.
    """
    
    try:
        result = await code_agent.solve_problem(problem)
        print(f"Fibonacci Problem: {problem}")
        print(f"Fibonacci Optimization Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    print()


async def circle_area_example():
    """Example 5: Simple circle area calculation with smolagents-style code execution"""
    print("=== Circle Area Example (smolagents style) ===")
    
    # Setup
    llm_config = config.models.get("gpt-4.1")
    llm = create_llm_provider(llm_config)
    
    python_executor = LocalPythonExecutor(
        additional_authorized_imports=["math"],
        max_print_outputs_length=50000
    )
    brain = Brain(python_env=python_executor, llm=llm)
    
    # Create CodeAgent
    code_agent = CodeAgent(brain=brain)
    
    # Simple problem to test <end_code> functionality
    problem = "Calculate the area of a circle with radius 5. Use the math.pi constant for accuracy."
    
    try:
        result = await code_agent.solve_problem(problem)
        print(f"Circle Problem: {problem}")
        print(f"Circle Area Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    print()

async def main():
    """Run all examples"""
    print("CodeAgent Examples with LocalPythonExecutor")
    print("=" * 50)
    
    try:
        await basic_math_example()
        await circle_area_example()
        await data_analysis_example()
        await complex_reasoning_example()
        await fibonacci_optimization_example()
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())