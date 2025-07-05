#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple test script for CodeMinion functionality
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from minion import config
from minion.agents import CodeMinion
from minion.main.rpyc_python_env import RpycPythonEnv
from minion.main.brain import Brain
from minion.providers import create_llm_provider


async def simple_test():
    """Simple test of CodeMinion functionality"""
    print("Testing CodeMinion...")
    
    try:
        # Setup LLM and environment
        llm_config = config.models.get("gpt-4.1")
        if not llm_config:
            print("Error: LLM config not found. Please check config/config.yaml")
            return
            
        llm = create_llm_provider(llm_config)
        
        # Use the existing Python environment
        python_env = RpycPythonEnv(port=3006)
        brain = Brain(python_env=python_env, llm=llm)
        
        # Create CodeMinion
        code_minion = CodeMinion(brain=brain)
        
        print("CodeMinion created successfully!")
        print(f"- Name: {code_minion.name}")
        print(f"- Tools: {[tool.name for tool in code_minion.tools]}")
        print(f"- Reflection enabled: {code_minion.enable_reflection}")
        print(f"- Thinking engine: {code_minion.thinking_engine is not None}")
        print(f"- Code executor: {code_minion.code_executor is not None}")
        
        # Test a simple problem
        print("\nTesting simple calculation...")
        result = await code_minion.solve_problem("What is 123 + 456?")
        print(f"Result: {result}")
        
        print("\nCodeMinion test completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(simple_test())