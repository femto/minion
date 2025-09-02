#!/usr/bin/env python3
"""
Textual UI Demo using the official TextualUI class

This script demonstrates how to use the TextualUI class from minion.main.textual_ui
to create a terminal interface for interacting with CodeAgent.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from minion.agents.code_agent import CodeAgent
from minion.main.textual_ui import TextualUI
from minion.main.brain import Brain
from minion.tools.default_tools import FinalAnswerTool

def main():
    """Main function to set up and launch the Textual UI using TextualUI class."""
    
    print("🚀 Starting Minion Textual UI Demo...")
    print("📝 This demo uses the official TextualUI class")
    
    # Check if textual is available
    try:
        import textual
        print(f"✅ Textual {textual.__version__} is available")
    except ImportError:
        print("❌ Textual is not installed. Please install it with:")
        print("   pip install textual")
        sys.exit(1)
    
    try:
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
        
        # Set up the agent synchronously to avoid event loop issues
        print("⚙️ Setting up agent...")
        
        # Run agent setup in a separate thread to avoid event loop conflicts
        import threading
        import queue
        
        setup_result = queue.Queue()
        
        def setup_agent():
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(agent.setup())
                loop.close()
                setup_result.put(('success', None))
            except Exception as e:
                setup_result.put(('error', e))
        
        setup_thread = threading.Thread(target=setup_agent)
        setup_thread.start()
        setup_thread.join(timeout=1)
        
        if not setup_result.empty():
            result_type, result = setup_result.get()
            if result_type == 'error':
                raise result
        else:
            raise TimeoutError("Agent setup timed out")
        
        print("✅ Agent setup complete!")
        
        # Create the Textual UI using the official TextualUI class
        print("🎨 Creating TextualUI...")
        textual_ui = TextualUI(
            agent=agent,
            file_upload_folder="uploads",  # Enable file uploads
            reset_agent_memory=True        # Reset memory between conversations
        )
        print("✅ TextualUI created successfully!")
        
        print("🖥️ Launching terminal interface...")
        print("📝 You can ask the agent to:")
        print("   - Solve math problems")
        print("   - Write and execute Python code")
        print("   - Analyze data")
        print("   - Answer questions with reasoning")
        print("   - Upload files for analysis")
        print("   - And much more!")
        print()
        print("💡 Commands:")
        print("   - /help - Show available commands")
        print("   - /clear - Clear chat history")
        print("   - /reset - Reset agent memory")
        print("   - /upload <path> - Upload a file")
        print("   - /quit or /exit - Exit the application")
        print()
        print("🛑 Press Ctrl+C to stop the application")
        print()
        
        # Launch the interface using TextualUI
        textual_ui.run()
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up the agent
        try:
            # Run cleanup in separate thread to avoid event loop issues
            def cleanup_agent():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(agent.close())
                    loop.close()
                except:
                    pass
            
            cleanup_thread = threading.Thread(target=cleanup_agent)
            cleanup_thread.start()
            cleanup_thread.join(timeout=5)
            print("🧹 Agent cleanup completed")
        except:
            pass

def run():
    """Run the main function."""
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Startup error: {e}")

if __name__ == "__main__":
    run()