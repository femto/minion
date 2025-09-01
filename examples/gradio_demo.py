#!/usr/bin/env python3
"""
Final, most reliable Gradio launcher
"""

import sys
import os
import socket
import threading
import time

def find_free_port(start=7860):
    """Find a free port."""
    for port in range(start, start + 10):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return None

def main():
    """Main function - completely synchronous approach."""
    print("🚀 Starting Minion Gradio UI (Final Version)...")
    
    # Check dependencies
    try:
        import gradio as gr
        print(f"✅ Gradio {gr.__version__} available")
    except ImportError:
        print("❌ Please install gradio: pip install gradio")
        return
    
    # Find port
    port = find_free_port()
    if not port:
        print("❌ No free ports available")
        return
    
    print(f"✅ Using port {port}")
    
    try:
        from minion.agents.code_agent import CodeAgent
        from minion.main.brain import Brain
        from minion.tools.default_tools import FinalAnswerTool
        
        # Create agent synchronously
        print("⚙️ Creating agent...")
        brain = Brain()
        agent = CodeAgent(
            name="Minion Assistant",
            brain=brain,
            tools=[FinalAnswerTool()],
            max_steps=10,
            enable_reflection=False,  # Disable for stability
            use_async_executor=False  # Use sync executor for stability
        )
        
        # Setup agent in a separate thread to avoid blocking
        setup_complete = threading.Event()
        setup_error = []
        
        def setup_agent():
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(agent.setup())
                loop.close()
                setup_complete.set()
            except Exception as e:
                setup_error.append(e)
                setup_complete.set()
        
        setup_thread = threading.Thread(target=setup_agent)
        setup_thread.start()
        setup_thread.join(timeout=30)
        
        if setup_error:
            raise setup_error[0]
        
        if not setup_complete.is_set():
            raise TimeoutError("Agent setup timed out")
        
        print("✅ Agent ready!")
        
        # Create a simple chat interface
        def chat_with_agent(message, history):
            """Simple chat function that works with the agent."""
            try:
                # Create a simple sync wrapper
                import asyncio
                
                def run_agent_sync():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        from minion.main.input import Input
                        input_obj = Input(query=message)
                        result = loop.run_until_complete(agent.run_async(input_obj, stream=False))
                        return str(result)
                    finally:
                        loop.close()
                
                # Run in thread to avoid blocking
                result_container = []
                error_container = []
                
                def worker():
                    try:
                        result = run_agent_sync()
                        result_container.append(result)
                    except Exception as e:
                        error_container.append(str(e))
                
                worker_thread = threading.Thread(target=worker)
                worker_thread.start()
                worker_thread.join(timeout=60)
                
                if error_container:
                    return f"❌ Error: {error_container[0]}"
                elif result_container:
                    return result_container[0]
                else:
                    return "⏰ Request timed out"
                    
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        # Create Gradio interface
        print("🎨 Creating interface...")
        demo = gr.ChatInterface(
            fn=chat_with_agent,
            title="🤖 Minion Code Assistant",
            description="Ask me to solve problems, write code, or answer questions!",
            examples=[
                "Calculate the area of a circle with radius 5",
                "Write a Python function to sort a list",
                "What is 15 * 23 + 7?",
                "Explain how recursion works"
            ]
        )
        
        print(f"🌐 Starting server at http://127.0.0.1:{port}")
        print("📝 You can now chat with the Minion agent!")
        print("🛑 Press Ctrl+C to stop")
        
        # Launch
        demo.launch(
            server_name="127.0.0.1",
            server_port=port,
            share=False,
            debug=False,
            show_error=True,
            quiet=True
        )
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()