#!/usr/bin/env python
# coding=utf-8
"""
Console-based UI for Minion Agent

A simple console interface that doesn't require complex UI frameworks.
This provides a clean terminal-based chat interface using basic input/output.
"""

import os
import sys
import asyncio
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime

# Import minion components
from ..agents.base_agent import BaseAgent
from ..main.input import Input
from ..main.action_step import StreamChunk

class ConsoleUI:
    """
    Simple console-based UI for interacting with a BaseAgent.
    
    This provides a clean terminal chat interface without external UI dependencies.
    """

    def __init__(self, agent: BaseAgent, reset_agent_memory: bool = False):
        self.agent = agent
        self.reset_agent_memory = reset_agent_memory
        self.name = getattr(agent, "name", "Minion Agent")
        self.description = getattr(agent, "description", "AI Agent Console Interface")
        self.chat_history = []

    def print_welcome(self):
        """Print welcome message."""
        print("=" * 60)
        print(f"🤖 {self.name}")
        print("=" * 60)
        print(f"{self.description}")
        print()
        print("💡 Commands:")
        print("  • 'quit' or 'exit' - Exit the application")
        print("  • 'clear' - Clear chat history")
        print("  • 'help' - Show this help")
        print("  • 'reset' - Reset agent memory")
        print()
        print("Type your message and press Enter to chat with the agent.")
        print("=" * 60)
        print()

    def print_help(self):
        """Print help message."""
        print("\n📋 Available Commands:")
        print("  • 'quit' or 'exit' - Exit the application")
        print("  • 'clear' - Clear chat history")
        print("  • 'help' - Show this help")
        print("  • 'reset' - Reset agent memory")
        print()

    def setup_agent(self):
        """Set up the agent synchronously."""
        if not self.agent.is_setup:
            print("⚙️ Setting up agent...")
            
            def setup_worker():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.agent.setup())
                loop.close()
            
            setup_thread = threading.Thread(target=setup_worker)
            setup_thread.start()
            setup_thread.join(timeout=30)
            
            if setup_thread.is_alive():
                print("❌ Agent setup timed out")
                return False
            
            print("✅ Agent setup complete!")
        return True

    def get_agent_response(self, message: str) -> str:
        """Get response from agent."""
        try:
            # Reset memory if requested
            if self.reset_agent_memory and hasattr(self.agent, 'reset_state'):
                self.agent.reset_state()
            
            # Create input object
            input_obj = Input(query=message)
            
            # Run agent in separate thread
            result_container = []
            error_container = []
            
            def run_agent():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def agent_runner():
                        response_parts = []
                        try:
                            # Get the async generator from run_async
                            stream_generator = self.agent.run_async(input_obj, stream=True)
                            
                            # Check if it's actually an async generator
                            if hasattr(stream_generator, '__aiter__'):
                                pass #actually use the following
                            else:
                                # If it's not an async generator, it might be a coroutine
                                # Try to await it directly
                                result = await stream_generator
                                if result:
                                    if hasattr(result, '__aiter__'):
                                        async for event in result:
                                            # Handle StreamChunk objects properly
                                            if isinstance(event, StreamChunk):
                                                if event.chunk_type in ['text', 'llm_output']:
                                                    print(event.content, end='', flush=True)
                                                    response_parts.append(event.content)
                                                elif event.chunk_type == 'final_answer':
                                                    final_answer = f"Final Answer: {event.content}"
                                                    print(final_answer, end='', flush=True)
                                                    response_parts.append(final_answer)
                                                elif event.chunk_type == 'error':
                                                    error_msg = f"Error: {event.content}"
                                                    print(error_msg, end='', flush=True)
                                                    response_parts.append(error_msg)
                                                elif event.chunk_type == 'step_start':
                                                    step_msg = f"\n[STEP START] {event.content}\n"
                                                    print(step_msg, end='', flush=True)
                                                    response_parts.append(step_msg)
                                                elif event.chunk_type == 'step_end':
                                                    step_msg = f"\n[STEP END] {event.content}\n"
                                                    print(step_msg, end='', flush=True)
                                                    response_parts.append(step_msg)
                                                elif event.chunk_type == 'tool_call':
                                                    # Truncate long tool calls
                                                    content = event.content[:200] + "..." if len(event.content) > 200 else event.content
                                                    tool_msg = f"\n[TOOL CALL] {content}\n"
                                                    print(tool_msg, end='', flush=True)
                                                    response_parts.append(tool_msg)
                                                elif event.chunk_type == 'tool_response':
                                                    # Truncate long tool responses
                                                    content = event.content[:300] + "..." if len(event.content) > 300 else event.content
                                                    tool_msg = f"\n[TOOL RESPONSE] {content}\n"
                                                    print(tool_msg, end='', flush=True)
                                                    response_parts.append(tool_msg)
                                                elif event.chunk_type == 'warning':
                                                    warn_msg = f"\n[WARNING] {event.content}\n"
                                                    print(warn_msg, end='', flush=True)
                                                    response_parts.append(warn_msg)
                                                elif event.chunk_type == 'completion':
                                                    comp_msg = f"\n[COMPLETION] {event.content}\n"
                                                    print(comp_msg, end='', flush=True)
                                                    response_parts.append(comp_msg)
                                                else:
                                                    # Show unknown chunk types
                                                    unknown_msg = f"\n[SKIP:{event.chunk_type.upper()}] {event.content[:100]}{'...' if len(event.content) > 100 else ''}\n"
                                                    print(unknown_msg, end='', flush=True)
                                                    response_parts.append(unknown_msg)
                                            # Process other event types (non-StreamChunk)
                                            elif hasattr(event, 'final_answer') and event.final_answer:
                                                final_answer = f"Final Answer: {event.final_answer}"
                                                print(final_answer, end='', flush=True)
                                                response_parts.append(final_answer)
                                            elif hasattr(event, 'raw_response') and event.raw_response:
                                                raw_response = str(event.raw_response)
                                                print(raw_response, end='', flush=True)
                                                response_parts.append(raw_response)
                                            elif hasattr(event, 'error') and event.error:
                                                error_msg = f"Error: {event.error}"
                                                print(error_msg, end='', flush=True)
                                                response_parts.append(error_msg)
                                            elif hasattr(event, 'content') and event.content:
                                                print(str(event.content), end='', flush=True)
                                                response_parts.append(str(event.content))
                                    else:
                                        result_str = str(result)
                                        print(result_str, end='', flush=True)
                                        response_parts.append(result_str)
                        except Exception as e:
                            response_parts.append(f"Error during streaming: {str(e)}")
                        
                        return "".join(response_parts) if response_parts else "No response generated"
                    
                    result = loop.run_until_complete(agent_runner())
                    result_container.append(result)
                    loop.close()
                    
                except Exception as e:
                    error_container.append(e)
            
            # Show thinking indicator and start streaming
            print("🤔 Agent is thinking...")
            print("🤖 Agent: ", end='', flush=True)
            
            # Run in thread
            agent_thread = threading.Thread(target=run_agent)
            agent_thread.start()
            agent_thread.join(timeout=120)  # 2 minute timeout
            
            if error_container:
                return f"❌ Error: {str(error_container[0])}"
            
            if result_container:
                return result_container[0]
            else:
                return "❌ Agent response timed out"
                
        except Exception as e:
            return f"❌ Error getting agent response: {str(e)}"

    def run(self):
        """Run the console UI."""
        try:
            self.print_welcome()
            
            # Setup agent
            if not self.setup_agent():
                print("❌ Failed to setup agent. Exiting.")
                return
            
            print("🚀 Ready to chat! Type your message below.\n")
            
            while True:
                try:
                    # Get user input
                    user_input = input("👤 You: ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.lower() in ['quit', 'exit']:
                        print("\n👋 Goodbye!")
                        break
                    elif user_input.lower() == 'clear':
                        os.system('clear' if os.name == 'posix' else 'cls')
                        self.chat_history.clear()
                        self.print_welcome()
                        print("🧹 Chat history cleared!\n")
                        continue
                    elif user_input.lower() == 'help':
                        self.print_help()
                        continue
                    elif user_input.lower() == 'reset':
                        if hasattr(self.agent, 'reset_state'):
                            self.agent.reset_state()
                            print("🔄 Agent memory reset!\n")
                        else:
                            print("⚠️ Agent doesn't support memory reset\n")
                        continue
                    
                    # Add to chat history
                    self.chat_history.append(('user', user_input))
                    
                    # Get agent response
                    response = self.get_agent_response(user_input)
                    
                    # Display response (streaming content already printed above)
                    print(f"\n\n")
                    print("-" * 60)
                    
                    # Add to chat history
                    self.chat_history.append(('agent', response))
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Goodbye!")
                    break
                except EOFError:
                    print("\n\n👋 Goodbye!")
                    break
                except Exception as e:
                    print(f"\n❌ Error: {str(e)}\n")
                    continue
        
        except Exception as e:
            print(f"❌ Fatal error: {str(e)}")
        finally:
            # Cleanup
            try:
                def cleanup_worker():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.agent.close())
                    loop.close()
                
                cleanup_thread = threading.Thread(target=cleanup_worker)
                cleanup_thread.start()
                cleanup_thread.join(timeout=5)
            except:
                pass


__all__ = ["ConsoleUI"]