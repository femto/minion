#!/usr/bin/env python3
"""
Simple demo of StateCodeAgent with State Management

This demonstrates the key features:
1. Code-based reasoning (smolagents-style)
2. State persistence with reset functionality
3. Conversation context
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from minion.agents.state_code_agent import StateCodeAgent
from minion.main.input import Input

async def demo_simple_state_management():
    """Simple demo of state management."""
    print("🚀 StateCodeAgent Demo - State Management like smolagents")
    print("=" * 60)
    
    # Create agent
    agent = StateCodeAgent(name="demo_agent")
    await agent.setup()  # Setup the agent before use
    
    print("\n📝 First calculation (no reset):")
    print("Creating variable 'x = 10' and calculating x * 2")
    
    result1 = await agent.run_async(
        Input(query="Set x = 10 and calculate x * 2. Store the result in variable 'result1'"),
        reset=False
    )
    print(f"✅ Result: {result1}")
    print(f"📊 Variables stored: {len(agent.persistent_state.get('variables', {}))}")
    print(f"💬 Conversation entries: {len(agent.conversation_history)}")
    
    print("\n📝 Second calculation (continuing with state):")
    print("Use the previous result to calculate result1 + 5")
    
    result2 = await agent.run_async(
        Input(query="Take the result1 we calculated before and add 5 to it"),
        reset=False
    )
    print(f"✅ Result: {result2}")
    print(f"📊 Variables stored: {len(agent.persistent_state.get('variables', {}))}")
    print(f"💬 Conversation entries: {len(agent.conversation_history)}")
    
    print("\n🔄 Reset and start fresh:")
    print("Reset state and create new variable 'y = 100'")
    
    result3 = await agent.run_async(
        Input(query="Set y = 100 and calculate y / 4"),
        reset=True  # This resets the state
    )
    print(f"✅ Result: {result3}")
    print(f"📊 Variables after reset: {len(agent.persistent_state.get('variables', {}))}")
    print(f"💬 Conversation entries after reset: {len(agent.conversation_history)}")
    
    print("\n📈 Final Statistics:")
    stats = agent.get_statistics()
    for key, value in stats.items():
        print(f"  - {key}: {value}")
    
    print("\n🎯 Key Features Demonstrated:")
    print("- ✅ Code-based reasoning (smolagents-style)")
    print("- ✅ State persistence across conversations") 
    print("- ✅ Reset functionality (reset=True/False)")
    print("- ✅ Variable storage and context management")
    print("- ✅ Conversation history tracking")

async def demo_state_save_load():
    """Demo saving and loading state between agents."""
    print("\n\n💾 Demo: State Save/Load")
    print("=" * 40)
    
    # Agent 1 - create some state
    agent1 = StateCodeAgent(name="agent1")
    await agent1.setup()  # Setup the agent before use
    
    print("📝 Agent 1 - Creating data:")
    await agent1.run_async(
        Input(query="Create a list fibonacci = [1, 1, 2, 3, 5, 8, 13] and calculate its sum"),
        reset=False
    )
    
    # Save state
    saved_state = agent1.get_state()
    print(f"💾 Saved state from Agent 1")
    
    # Agent 2 - load the state
    agent2 = StateCodeAgent(name="agent2")
    await agent2.setup()  # Setup the agent before use
    agent2.load_state(saved_state)
    
    print("🔄 Agent 2 - Using loaded state:")
    result = await agent2.run_async(
        Input(query="Calculate the average of the fibonacci list we created"),
        reset=False
    )
    print(f"✅ Result: {result}")

if __name__ == "__main__":
    print("🔥 Running StateCodeAgent Demo...")
    try:
        asyncio.run(demo_simple_state_management())
        asyncio.run(demo_state_save_load())
        print("\n\n🎉 Demo completed successfully!")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)