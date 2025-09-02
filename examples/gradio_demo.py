#!/usr/bin/env python3
"""
Gradio UI Demo using the official GradioUI class

This script demonstrates how to use the GradioUI class from minion.main.gradio_ui
to create a web interface for interacting with CodeAgent.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from minion.agents.code_agent import CodeAgent
from minion.main.gradio_ui import GradioUI
from minion.main.brain import Brain
from minion.tools.default_tools import FinalAnswerTool

def setup():
    """Set up the Gradio UI and return the UI instance and agent."""
    
    print("🚀 Starting Minion Gradio UI Demo...")
    print("📝 This demo uses the official GradioUI class")
    
    # Check if gradio is available
    try:
        import gradio
        print(f"✅ Gradio {gradio.__version__} is available")
    except ImportError:
        print("❌ Gradio is not installed. Please install it with:")
        print("   pip install gradio")
        print("   or")
        print("   pip install 'minion[gradio]'")
        sys.exit(1)
    
    # Create a brain instance
    brain = Brain()
    
    # Create a CodeAgent with basic tools
    agent = CodeAgent(
        name="Minion Code Assistant",
        brain=brain,
        tools=[FinalAnswerTool()],
        max_steps=10,
        enable_reflection=True,
        use_async_executor=True
    )
    
    # Create the Gradio UI using the official GradioUI class
    print("🎨 Creating GradioUI...")
    gradio_ui = GradioUI(
        agent=agent,
        file_upload_folder="uploads",  # Enable file uploads
        reset_agent_memory=True        # Reset memory between conversations
    )
    print("✅ GradioUI created successfully!")
    
    return gradio_ui, agent

# Main function is now handled by main_async

def run():
    """Run the application using asyncio.run to properly handle async operations.
    
    This function serves as the entry point for the application and ensures that
    the async main_async function is executed correctly within an asyncio event loop.
    It also provides error handling for graceful shutdown.
    """
    try:
        # Use asyncio.run to properly handle async operations
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Startup error: {e}")
        import traceback
        traceback.print_exc()

async def main_async():
    """Async implementation of the main function to properly handle asyncio operations.
    
    This function ensures that the asyncio event loop is properly set up before launching
    the Gradio interface, which is important for the Uvicorn server's lifespan management.
    """
    agent = None
    try:
        # Set up the UI and agent
        gradio_ui, agent = setup()
        
        # Set up the agent asynchronously
        print("⚙️ Setting up agent...")
        await agent.setup()
        print("✅ Agent setup complete!")
        
        print("🌐 Launching web interface...")
        print("📝 You can ask the agent to:")
        print("   - Solve math problems")
        print("   - Write and execute Python code")
        print("   - Analyze data")
        print("   - Answer questions with reasoning")
        print("   - Upload files for analysis")
        print("   - And much more!")
        print()
        print("🛑 Press Ctrl+C to stop the server")
        
        # Launch the interface using GradioUI
        # The launch method is blocking, which is what we want in this case
        # It will keep the server running until interrupted
        gradio_ui.launch(
            share=False,        # Set to True to create a public link
            debug=False,        # Set to True for debug mode
            server_port=None    # Let Gradio auto-select an available port
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up the agent if it was created
        if agent is not None:
            try:
                print("🧹 Cleaning up agent resources...")
                await agent.close()
                print("✅ Agent cleanup completed")
            except Exception as e:
                print(f"⚠️ Error during agent cleanup: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    run()