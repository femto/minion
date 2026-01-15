#!/usr/bin/env python3
"""
Console UI Demo

This script demonstrates the ConsoleUI for simple terminal-based interaction.
"""

import sys
import os
import asyncio

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from minion.agents.code_agent import CodeAgent
from minion.main.console_ui import ConsoleUI
from minion.main.brain import Brain
from minion.tools.default_tools import FinalAnswerTool

async def main():
    """Main function to set up and launch the Console UI."""

    print("🚀 Starting Minion Console UI Demo...")

    try:
        # Create a brain instance
        brain = Brain()

        # Create a CodeAgent with basic tools
        agent = CodeAgent(
            name="Minion Code Assistant",
            brain=brain,
            tools=[],
            max_steps=10,
            enable_reflection=True,
            use_async_executor=True
        )
        await agent.setup()

        print("✅ Agent created successfully!")

        # Create the Console UI
        print("🎨 Creating ConsoleUI...")
        console_ui = ConsoleUI(
            agent=agent,
            reset_agent_memory=True  # Reset memory between conversations
        )
        print("✅ ConsoleUI created successfully!")

        print("🖥️ Launching console interface...")
        print()

        # Launch the interface
        console_ui.run()

    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())