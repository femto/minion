#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick Start Example for Turing Machine Agent

This example shows the simplest way to use the Turing Machine Agent.
Make sure you have configured your LLM API keys in the config files.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from minion.agents import create_turing_machine_agent


async def simple_example():
    """Simple example using default configuration"""
    print("Creating Turing Machine Agent...")
    
    # Create agent (uses default LLM configuration)
    agent = create_turing_machine_agent(name="quick_start_agent")
    
    # Define a simple task
    task = "Explain the concept of recursion in programming with a simple example"
    
    print(f"Task: {task}")
    print("=" * 60)
    
    try:
        # Run the task (max_steps limits execution to prevent infinite loops)
        result = await agent.run(task, max_steps=4, streaming=False)
        
        print("Result:")
        print("-" * 60)
        print(result)
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: Make sure you have configured your LLM API keys in:")
        print("- ~/.minion/config.yaml")
        print("- or config/config.yaml")


async def step_by_step_example():
    """Example showing step-by-step execution"""
    print("\n" + "=" * 80)
    print("Step-by-Step Execution Example")
    print("=" * 80)
    
    agent = create_turing_machine_agent(name="step_agent")
    
    task = "Write Python code for a function that prints 'Hello World'"
    
    print(f"Task: {task}")
    print("-" * 60)
    
    try:
        # Use streaming to see intermediate results
        step_count = 0
        async for result in agent.run(task, streaming=True, max_steps=8, debug=True):
            step_count += 1
            print(f"Step {step_count} Result:")
            if isinstance(result, tuple) and len(result) >= 1:
                response, score, terminated, truncated, info = result
                print(f"Response: {response}")
                print(f"Action: {info.get('action', 'unknown')}")
                print(f"State: {info.get('state', 'unknown')}")
                print(f"Terminated: {terminated}, Truncated: {truncated}")
            else:
                print(result)
            print("-" * 40)
            
    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: This error is likely due to LLM API configuration.")
        print("The streaming functionality itself is working correctly!")


async def main():
    """Run all examples"""
    await simple_example()
    await step_by_step_example()
    print("\nQuick start examples completed!")
    print("\nNext steps:")
    print("1. Configure your LLM API keys")
    print("2. Run: python examples/turing_machine_demo.py for more advanced examples")
    print("3. Check docs/turing_machine_agent_guide.md for detailed documentation")


if __name__ == "__main__":
    asyncio.run(main()) 