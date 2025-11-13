#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Demo showing how BaseAgent automatically converts raw functions to tools.

This example demonstrates:
1. Passing raw sync/async functions directly to BaseAgent
2. Automatic conversion to BaseTool/AsyncBaseTool during setup
3. Mixed usage with pre-converted tools
"""

import asyncio
import math
from minion.agents.base_agent import BaseAgent
from minion.tools import tool


# Raw sync functions - will be auto-converted to BaseTool
def calculate_circle_area(radius: float) -> float:
    """
    Calculate the area of a circle.
    
    Args:
        radius: The radius of the circle
    """
    return math.pi * radius ** 2


def fibonacci(n: int) -> int:
    """
    Calculate the nth Fibonacci number.
    
    Args:
        n: The position in the Fibonacci sequence
    """
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


# Raw async functions - will be auto-converted to AsyncBaseTool
async def simulate_api_call(endpoint: str, delay: float = 0.5) -> str:
    """
    Simulate an API call with delay.
    
    Args:
        endpoint: The API endpoint to call
        delay: Delay in seconds to simulate network latency
    """
    await asyncio.sleep(delay)
    return f"Response from {endpoint}: {{\"status\": \"success\", \"data\": \"mock_data\"}}"


async def async_file_processor(filename: str) -> str:
    """
    Simulate async file processing.
    
    Args:
        filename: Name of the file to process
    """
    await asyncio.sleep(0.2)  # Simulate I/O
    return f"Processed file: {filename} (size: 1024 bytes, lines: 42)"


# Pre-converted tool using @tool decorator
@tool
def string_reverser(text: str) -> str:
    """
    Reverse a string.
    
    Args:
        text: The text to reverse
    """
    return text[::-1]


async def main():
    """Demonstrate BaseAgent auto-conversion feature"""
    print("=== BaseAgent Auto-Conversion Demo ===\n")
    
    # Create agent with mix of raw functions and pre-converted tools
    agent = BaseAgent(
        name="demo_agent",
        tools=[
            # Raw sync functions (will be auto-converted)
            calculate_circle_area,
            fibonacci,
            
            # Raw async functions (will be auto-converted)  
            simulate_api_call,
            async_file_processor,
            
            # Pre-converted tool
            string_reverser,
        ]
    )
    
    print("🔧 Setting up agent (auto-converting raw functions)...")
    await agent.setup()
    
    print(f"✅ Agent setup complete! Total tools: {len(agent.tools)}\n")
    
    # Display converted tools
    print("📋 Available Tools:")
    for i, tool in enumerate(agent.tools, 1):
        tool_type = "🔄 AsyncBaseTool" if hasattr(tool, 'forward') and asyncio.iscoroutinefunction(tool.forward) else "⚡ BaseTool"
        print(f"  {i}. {tool_type} - {tool.name}")
        print(f"     📝 {tool.description}")
    
    print(f"\n" + "="*60)
    print("🧪 Testing Tool Execution")
    print("="*60)
    
    # Test sync tools
    print("\n⚡ Testing Sync Tools:")
    
    area_tool = next(t for t in agent.tools if t.name == "calculate_circle_area")
    area = area_tool(5.0)
    print(f"  🔵 Circle area (radius=5): {area:.2f}")
    
    fib_tool = next(t for t in agent.tools if t.name == "fibonacci")
    fib = fib_tool(10)
    print(f"  🔢 Fibonacci(10): {fib}")
    
    reverse_tool = next(t for t in agent.tools if t.name == "string_reverser")
    reversed_text = reverse_tool("Hello, World!")
    print(f"  🔄 Reversed text: '{reversed_text}'")
    
    # Test async tools
    print(f"\n🔄 Testing Async Tools:")
    
    api_tool = next(t for t in agent.tools if t.name == "simulate_api_call")
    api_response = await api_tool("/users/123", 0.1)
    print(f"  🌐 API call result: {api_response}")
    
    file_tool = next(t for t in agent.tools if t.name == "async_file_processor")
    file_result = await file_tool("document.txt")
    print(f"  📄 File processing result: {file_result}")
    
    print(f"\n" + "="*60)
    print("✨ Key Benefits of Auto-Conversion:")
    print("="*60)
    print("  • 🎯 No need to manually decorate every function")
    print("  • 🔄 Automatic sync/async detection")
    print("  • 🛠️  Seamless integration with existing tools")
    print("  • 📊 Proper type hints and schema extraction")
    print("  • 🧹 Clean, readable agent initialization")
    
    print(f"\n🎉 Demo completed successfully!")
    
    # Clean up
    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())