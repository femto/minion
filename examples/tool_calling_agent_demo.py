#!/usr/bin/env python3
"""
MinionToolCallingAgent Demo

This example demonstrates how to use the MinionToolCallingAgent,
which properly handles final_answer tool calls and stops execution
when the task is complete.

Key Features:
- Direct tool calling via LLM tool calling capabilities
- Proper final_answer detection that stops agent execution
- Support for both sync and streaming execution
- Adapted from smolagents approach to work with minion project
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from minion.agents.minion_tool_calling_agent import create_tool_calling_agent
from minion.tools.default_tools import FinalAnswerTool
from minion.tools.base_tool import BaseTool


class CalculatorTool(BaseTool):
    """Calculator tool for basic arithmetic"""
    
    name = "calculator"
    description = "Performs basic arithmetic calculations (addition, subtraction, multiplication, division)"
    inputs = {
        "expression": {
            "type": "string", 
            "description": "Mathematical expression like '5 + 3' or '10 * 2'"
        }
    }
    
    def forward(self, expression: str) -> str:
        """Execute the calculation"""
        try:
            expression = expression.strip()
            
            # Handle basic operations
            for op in ['+', '-', '*', '/']:
                if op in expression:
                    parts = expression.split(op)
                    if len(parts) == 2:
                        left = float(parts[0].strip())
                        right = float(parts[1].strip())
                        
                        if op == '+':
                            result = left + right
                        elif op == '-':
                            result = left - right
                        elif op == '*':
                            result = left * right
                        elif op == '/':
                            if right == 0:
                                return "Error: Division by zero"
                            result = left / right
                        
                        return str(int(result) if result == int(result) else result)
            
            return f"Cannot parse expression: {expression}"
            
        except Exception as e:
            return f"Calculation error: {str(e)}"


class WeatherTool(BaseTool):
    """Mock weather tool for demonstration"""
    
    name = "get_weather"
    description = "Get current weather information for a city"
    inputs = {
        "city": {
            "type": "string",
            "description": "Name of the city to get weather for"
        }
    }
    
    def forward(self, city: str) -> str:
        """Get weather (mock implementation)"""
        # Mock weather data
        weather_data = {
            "beijing": "Sunny, 22°C",
            "shanghai": "Cloudy, 18°C", 
            "guangzhou": "Rainy, 25°C",
            "shenzhen": "Partly cloudy, 24°C",
            "new york": "Snow, -2°C",
            "london": "Foggy, 8°C",
            "tokyo": "Clear, 15°C"
        }
        
        city_lower = city.lower()
        if city_lower in weather_data:
            return f"Weather in {city}: {weather_data[city_lower]}"
        else:
            return f"Weather data not available for {city}. Available cities: {', '.join(weather_data.keys())}"


async def demo_basic_usage():
    """Demonstrate basic usage of MinionToolCallingAgent"""
    
    print("🚀 MinionToolCallingAgent Basic Demo")
    print("=" * 50)
    
    # Create tools
    calculator = CalculatorTool()
    weather = WeatherTool()
    final_answer = FinalAnswerTool()
    
    # Create agent
    agent = create_tool_calling_agent(
        tools=[calculator, weather, final_answer],
        name="demo_agent",
        model="gpt-4o-mini"
    )
    
    try:
        # Setup agent
        print("🔧 Setting up agent...")
        await agent.setup()
        print("✅ Agent ready!")
        
        # Test 1: Math calculation
        print("\n📊 Test 1: Math Calculation")
        print("-" * 30)
        
        task1 = "Calculate 15 * 4 and provide the final answer"
        print(f"Task: {task1}")
        
        result1 = await agent.run_async(task=task1, max_steps=3)
        print(f"Result: {result1}")
        
        # Test 2: Weather query
        print("\n🌤️  Test 2: Weather Query")
        print("-" * 30)
        
        task2 = "Get the weather for Beijing and provide the final answer"
        print(f"Task: {task2}")
        
        result2 = await agent.run_async(task=task2, max_steps=3)
        print(f"Result: {result2}")
        
        # Test 3: Multi-step task
        print("\n🔄 Test 3: Multi-step Task")
        print("-" * 30)
        
        task3 = "Calculate 8 + 7, then get weather for Tokyo, and provide a final answer combining both pieces of information"
        print(f"Task: {task3}")
        
        result3 = await agent.run_async(task=task3, max_steps=5)
        print(f"Result: {result3}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.close()
        print("\n🔚 Agent cleanup completed")


async def demo_streaming():
    """Demonstrate streaming execution"""
    
    print("\n🌊 MinionToolCallingAgent Streaming Demo")
    print("=" * 50)
    
    # Create tools
    calculator = CalculatorTool()
    final_answer = FinalAnswerTool()
    
    # Create agent
    agent = create_tool_calling_agent(
        tools=[calculator, final_answer],
        name="streaming_agent",
        model="gpt-4o-mini",
        stream_outputs=True
    )
    
    try:
        await agent.setup()
        print("✅ Streaming agent ready!")
        
        task = "Calculate 25 / 5 and then provide the final answer"
        print(f"\nTask: {task}")
        print("Streaming output:")
        print("-" * 40)
        
        chunk_count = 0
        async for chunk in await agent.run_async(task=task, max_steps=3, stream=True):
            chunk_count += 1
            
            if hasattr(chunk, 'chunk_type'):
                print(f"[{chunk.chunk_type}] {chunk.content.strip()}")
                
                # Stop if we see completion
                if chunk.chunk_type in ["completion", "final_answer"]:
                    print("🎯 Final answer detected - stopping stream")
                    break
            else:
                print(f"[stream] {str(chunk).strip()}")
            
            # Safety break
            if chunk_count > 20:
                print("⚠️  Safety break at 20 chunks")
                break
        
        print(f"\n📊 Total chunks: {chunk_count}")
        
    except Exception as e:
        print(f"❌ Streaming error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.close()


async def demo_without_final_answer():
    """Show what happens without final_answer tool"""
    
    print("\n⚠️  Demo: Agent Without final_answer Tool")
    print("=" * 50)
    
    # Create agent WITHOUT final_answer tool
    calculator = CalculatorTool()
    agent = create_tool_calling_agent(
        tools=[calculator],  # No final_answer tool
        name="no_final_agent",
        model="gpt-4o-mini"
    )
    
    try:
        await agent.setup()
        print("✅ Agent without final_answer ready!")
        
        task = "Calculate 12 + 8"
        print(f"\nTask: {task}")
        print("⚠️  Note: This agent will run until max_steps since it can't call final_answer")
        
        result = await agent.run_async(task=task, max_steps=2)  # Small limit
        print(f"Result: {result}")
        
        if hasattr(result, 'terminated'):
            print(f"Terminated: {result.terminated}")
            if not result.terminated:
                print("ℹ️  Agent did not terminate naturally - reached max_steps")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await agent.close()


async def main():
    """Run all demos"""
    
    print("🎭 MinionToolCallingAgent Complete Demo")
    print("=" * 60)
    print()
    print("This demo shows how the MinionToolCallingAgent:")
    print("✅ Properly detects final_answer tool calls")
    print("✅ Stops execution when task is complete") 
    print("✅ Supports both sync and streaming modes")
    print("✅ Handles multiple tools and multi-step tasks")
    print()
    
    try:
        await demo_basic_usage()
        await demo_streaming()
        await demo_without_final_answer()
        
        print("\n🎉 All demos completed successfully!")
        print("\nKey takeaways:")
        print("- MinionToolCallingAgent properly stops when final_answer is called")
        print("- This solves the issue where agents would continue running after completion")
        print("- The agent uses direct LLM tool calling instead of code execution")
        print("- Based on smolagents approach, adapted for minion project")
        
        
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Note: This demo requires OpenAI API access
    # Set OPENAI_API_KEY environment variable before running
    
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not found in environment")
        print("   This demo requires OpenAI API access to work properly")
        print("   Set your API key: export OPENAI_API_KEY='your-key-here'")
        print()
    
    asyncio.run(main())