#!/usr/bin/env python
# coding=utf-8
"""
Textual-based Terminal UI for Minion Agent

This module provides a terminal-based user interface using Textual for interacting
with Minion agents. It offers a rich, interactive console experience with real-time
chat, syntax highlighting, and file upload capabilities.
"""

import os
import re
import shutil
import asyncio
import threading
from pathlib import Path
from typing import Generator, Dict, Any, Optional, Union, List, AsyncIterator
from enum import Enum
from datetime import datetime

# Import minion components
from ..agents.base_agent import BaseAgent
from ..agents.code_agent import CodeAgent
from ..main.input import Input
from ..main.action_step import ActionStep, StreamChunk
from minion.types.agent_response import AgentResponse

def _is_package_available(package_name: str) -> bool:
    """Check if a package is available for import."""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

# Define message roles for compatibility
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatMessage:
    """Simple chat message class for textual UI."""
    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None, is_streaming: bool = False):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.is_streaming = is_streaming
    
    def __str__(self):
        return f"[{self.role}] {self.content}"

def _clean_model_output(model_output: str) -> str:
    """Clean up model output by removing trailing tags and extra backticks."""
    if not model_output:
        return ""
    model_output = model_output.strip()
    # Remove any trailing <end_code> and extra backticks
    model_output = re.sub(r"```\s*<end_code>", "```", model_output)
    model_output = re.sub(r"<end_code>\s*```", "```", model_output)
    model_output = re.sub(r"```\s*\n\s*<end_code>", "```", model_output)
    return model_output.strip()

def _format_code_content(content: str) -> str:
    """Format code content as Python code block if it's not already formatted."""
    content = content.strip()
    # Remove existing code blocks and end_code tags
    content = re.sub(r"```.*?\n", "", content)
    content = re.sub(r"\s*<end_code>\s*", "", content)
    content = content.strip()
    # Add Python code block formatting if not already present
    if not content.startswith("```python"):
        content = f"```python\n{content}\n```"
    return content

async def stream_to_textual(
    agent: BaseAgent,
    task: str,
    task_images: Optional[list] = None,
    reset_agent_memory: bool = False,
    additional_args: Optional[dict] = None,
) -> AsyncIterator[ChatMessage]:
    """Runs an agent with the given task and streams the messages as ChatMessage objects."""
    
    # Convert task to Input object if needed
    if isinstance(task, str):
        input_obj = Input(query=task)
    else:
        input_obj = task
    
    # Handle images if provided
    if task_images:
        if not hasattr(input_obj, 'metadata'):
            input_obj.metadata = {}
        input_obj.metadata['images'] = task_images
    
    try:
        # Reset memory if requested
        if reset_agent_memory and hasattr(agent, 'reset_state'):
            agent.reset_state()
        
        # Prepare additional arguments
        kwargs = additional_args or {}
        kwargs['stream'] = True
        
        # Direct async streaming without threads
        streaming_content = []  # Buffer for accumulating streaming content
        
        async for event in (await agent.run_async(input_obj, **kwargs)):
            # Handle StreamChunk differently - accumulate content
            if isinstance(event, StreamChunk):
                content = event.content
                chunk_type = getattr(event, 'chunk_type', 'llm_output')
                
                if chunk_type == 'error':
                    # Flush accumulated content first
                    if streaming_content:
                        yield ChatMessage(MessageRole.ASSISTANT, "".join(streaming_content), is_streaming=False)
                        streaming_content = []
                    # Then yield error
                    yield ChatMessage(MessageRole.ASSISTANT, f"💥 Error: {content}")
                elif chunk_type == 'final_answer':
                    # Flush accumulated content first
                    if streaming_content:
                        yield ChatMessage(MessageRole.ASSISTANT, "".join(streaming_content), is_streaming=False)
                        streaming_content = []
                    # Then yield final answer
                    yield ChatMessage(MessageRole.ASSISTANT, f"✅ Final answer: {content}")
                else:
                    # Accumulate streaming content
                    streaming_content.append(content)
                    # Yield accumulated content so far with streaming status
                    yield ChatMessage(MessageRole.ASSISTANT, "".join(streaming_content), is_streaming=True)
            else:
                # For non-StreamChunk events, flush accumulated content first
                if streaming_content:
                    yield ChatMessage(MessageRole.ASSISTANT, "".join(streaming_content), is_streaming=False)
                    streaming_content = []
                
                # Process other event types normally
                if isinstance(event, (ActionStep, AgentResponse)):
                    content = _process_agent_event(event, skip_model_outputs=getattr(agent, "stream_outputs", False))
                    if content:
                        yield ChatMessage(MessageRole.ASSISTANT, content)
                elif isinstance(event, str):
                    yield ChatMessage(MessageRole.ASSISTANT, event)
                else:
                    yield ChatMessage(MessageRole.ASSISTANT, str(event))
        
        # Yield any remaining accumulated streaming content as final message
        if streaming_content:
            yield ChatMessage(MessageRole.ASSISTANT, "".join(streaming_content), is_streaming=False)
                
    except Exception as e:
        # Handle any errors in streaming
        yield ChatMessage(MessageRole.ASSISTANT, f"❌ Error in agent execution: {str(e)}")

def _process_agent_event(event, skip_model_outputs: bool = False) -> str:
    """Process an agent event and return formatted content."""
    if isinstance(event, StreamChunk):
        content = event.content
        chunk_type = getattr(event, 'chunk_type', 'llm_output')
        
        if chunk_type == 'error':
            return f"💥 Error: {content}"
        elif chunk_type == 'final_answer':
            return f"✅ Final answer: {content}"
        else:
            return content
    
    elif isinstance(event, AgentResponse):
        parts = []
        if event.raw_response:
            parts.append(str(event.raw_response))
        if event.final_answer:
            parts.append(f"✅ Final answer: {event.final_answer}")
        if event.error:
            parts.append(f"💥 Error: {str(event.error)}")
        return "\n".join(parts) if parts else ""
    
    elif isinstance(event, ActionStep):
        parts = []
        
        # Add step number
        step_number = getattr(event, 'step_number', 1)
        parts.append(f"🔄 Step {step_number}")
        
        # Add model output (skip if skip_model_outputs is True)
        if not skip_model_outputs:
            model_output = ""
            if hasattr(event, 'model_output') and event.model_output:
                model_output = event.model_output
            elif hasattr(event, 'content') and event.content:
                model_output = event.content
            elif hasattr(event, 'response') and event.response:
                model_output = event.response
            
            if model_output:
                model_output = _clean_model_output(str(model_output))
                parts.append(model_output)
        
        # Add tool calls
        tool_calls = getattr(event, "tool_calls", []) or getattr(event, "actions", [])
        if tool_calls:
            first_tool_call = tool_calls[0] if isinstance(tool_calls, list) else tool_calls
            tool_name = getattr(first_tool_call, 'name', getattr(first_tool_call, 'tool_name', 'unknown_tool'))
            
            args = getattr(first_tool_call, 'arguments', getattr(first_tool_call, 'args', {}))
            if isinstance(args, dict):
                content = str(args.get("answer", args.get("code", str(args))))
            else:
                content = str(args).strip()
            
            # Format code content if needed
            if tool_name in ["python_interpreter", "code_executor", "python"]:
                content = _format_code_content(content)
            
            parts.append(f"🛠️ Used tool {tool_name}:\n{content}")
        
        # Add execution logs
        observations = getattr(event, "observations", "") or getattr(event, "logs", "")
        if observations and str(observations).strip():
            log_content = str(observations).strip()
            log_content = re.sub(r"^Execution logs:\s*", "", log_content)
            parts.append(f"📝 Execution Logs:\n```\n{log_content}\n```")
        
        # Add errors
        error = getattr(event, "error", None)
        if error:
            parts.append(f"💥 Error: {str(error)}")
        
        return "\n\n".join(parts)
    
    else:
        return str(event)


class TextualUI:
    """
    Textual-based Terminal UI for interacting with a BaseAgent.

    This class provides a rich terminal interface to interact with the agent in real-time,
    allowing users to submit prompts, upload files, and receive responses in a chat-like format.
    It uses Textual for a modern terminal UI experience with syntax highlighting and scrolling.

    Args:
        agent (BaseAgent): The agent to interact with (BaseAgent, CodeAgent, etc.).
        file_upload_folder (str, optional): The folder where uploaded files will be saved.
            If not provided, file uploads are disabled.
        reset_agent_memory (bool, optional, defaults to False): Whether to reset the agent's memory at the start of each interaction.

    Raises:
        ModuleNotFoundError: If the `textual` package is not installed.

    Example:
        ```python
        from minion.agents.code_agent import CodeAgent
        from minion.main.textual_ui import TextualUI
        from minion.main.brain import Brain

        brain = Brain()
        agent = CodeAgent(brain=brain, tools=[])
        textual_ui = TextualUI(agent, file_upload_folder="uploads", reset_agent_memory=True)
        textual_ui.run()
        ```
    """

    def __init__(self, agent: BaseAgent, file_upload_folder: Optional[str] = None, reset_agent_memory: bool = False):
        if not _is_package_available("textual"):
            raise ModuleNotFoundError(
                "Please install 'textual' to use the TextualUI: `pip install textual`"
            )
        
        self.agent = agent
        self.file_upload_folder = Path(file_upload_folder) if file_upload_folder is not None else None
        self.reset_agent_memory = reset_agent_memory
        self.name = getattr(agent, "name", "Minion Agent Interface")
        self.description = getattr(agent, "description", "A powerful AI agent that can execute code and use tools to solve complex tasks.")
        
        if self.file_upload_folder is not None:
            if not self.file_upload_folder.exists():
                self.file_upload_folder.mkdir(parents=True, exist_ok=True)
        
        self.chat_history: List[ChatMessage] = []

    def upload_file(self, file_path: str, allowed_file_types: Optional[List[str]] = None) -> str:
        """
        Upload a file and add it to the upload folder.

        Args:
            file_path (str): Path to the file to upload.
            allowed_file_types (List[str], optional): List of allowed file extensions.

        Returns:
            str: Status message about the upload.
        """
        if not os.path.exists(file_path):
            return f"❌ File not found: {file_path}"

        if allowed_file_types is None:
            allowed_file_types = [".pdf", ".docx", ".txt", ".py", ".md", ".json", ".csv"]

        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in allowed_file_types:
            return f"❌ File type {file_ext} not allowed. Allowed types: {', '.join(allowed_file_types)}"

        if self.file_upload_folder is None:
            return "❌ File uploads are disabled"

        # Sanitize file name
        original_name = os.path.basename(file_path)
        sanitized_name = re.sub(r"[^\w\-.]", "_", original_name)

        # Copy the file to the upload folder
        dest_path = self.file_upload_folder / sanitized_name
        try:
            shutil.copy2(file_path, dest_path)
            return f"✅ File uploaded: {dest_path}"
        except Exception as e:
            return f"❌ Error uploading file: {str(e)}"

    async def setup_agent(self):
        """Set up the agent asynchronously."""
        if not self.agent.is_setup:
            try:
                await self.agent.setup()
                return "✅ Agent setup complete!"
            except Exception as e:
                return f"❌ Error setting up agent: {str(e)}"
        return "✅ Agent already set up!"

    def create_app(self):
        """Create and return the Textual app."""
        from textual.app import App, ComposeResult
        from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
        from textual.widgets import (
            Header, Footer, Input, Button, Static, RichLog, 
            Markdown, DirectoryTree
        )
        from textual.widget import Widget
        from textual.reactive import reactive
        from textual.message import Message
        from textual import events
        from rich.console import Console
        from rich.markdown import Markdown as RichMarkdown
        from rich.syntax import Syntax
        from rich.text import Text
        from rich.panel import Panel

        # Remove StreamingWidget - use a simpler approach

        class MinionApp(App):
            """Main Textual application for Minion Agent UI."""
            
            # Reactive variable for streaming content
            streaming_content = reactive("")
            
            CSS = """
            #sidebar {
                width: 30%;
                background: $surface;
                border-right: solid $primary;
            }
            
            #chat-container {
                width: 70%;
            }
            
            #chat-log {
                height: 1fr;
                border: solid $primary;
                margin: 1;
            }
            
            #input-container {
                height: auto;
                margin: 1;
            }
            
            #user-input {
                margin-bottom: 1;
            }
            
            .agent-message {
                background: $surface-lighten-1;
                margin: 1 0;
                padding: 1;
            }
            
            .user-message {
                background: $primary-lighten-3;
                margin: 1 0;
                padding: 1;
            }
            
            .error-message {
                background: $error;
                margin: 1 0;
                padding: 1;
            }
            """

            def __init__(self, ui_instance):
                super().__init__()
                self.ui = ui_instance
                self.processing = False

            def compose(self) -> ComposeResult:
                """Create child widgets for the app."""
                yield Header()
                
                with Horizontal():
                    # Sidebar
                    with Vertical(id="sidebar"):
                        yield Static(f"# {self.ui.name}", id="title")
                        yield Static(
                            f"{self.ui.description}\n\n"
                            "💡 **Tips:**\n"
                            "• Type your message and press Enter\n"
                            "• Use Ctrl+C to exit\n"
                            "• Upload files with /upload <path>\n"
                            "• Clear chat with /clear\n"
                            "• Reset agent with /reset",
                            id="description"
                        )
                        
                        if self.ui.file_upload_folder:
                            yield Static("📁 **Upload Folder:**", id="upload-title")
                            yield Static(f"{self.ui.file_upload_folder}", id="upload-path")
                    
                    # Main chat area
                    with Vertical(id="chat-container"):
                        yield RichLog(id="chat-log", highlight=True, markup=True)
                        yield Static("", id="streaming-response")
                        
                        with Container(id="input-container"):
                            yield Input(
                                placeholder="Type your message here... (or /help for commands)",
                                id="user-input"
                            )
                            yield Button("Send", id="send-button", variant="primary")

                yield Footer()

            def __init__(self, ui):
                super().__init__()
                self.ui = ui
                self.processing = False

            def watch_streaming_content(self, content: str) -> None:
                """Update streaming display when content changes."""
                try:
                    streaming_static = self.query_one("#streaming-response", Static)
                    if content:
                        # Show streaming content with cursor
                        agent_text = Text()
                        agent_text.append("🤖 Agent: ", style="bold green")
                        agent_text.append(content)
                        agent_text.append(" ▋", style="dim")  # Streaming cursor
                        
                        streaming_static.update(Panel(
                            agent_text, 
                            border_style="green",
                            title="Streaming..."
                        ))
                    else:
                        # No content, hide the widget
                        streaming_static.update("")
                except:
                    pass

            def on_mount(self) -> None:
                """Called when app starts."""
                chat_log = self.query_one("#chat-log", RichLog)
                
                # Welcome message
                welcome_text = Text()
                welcome_text.append("🚀 Welcome to Minion Agent Terminal UI!\n", style="bold green")
                welcome_text.append(f"Agent: {self.ui.name}\n", style="cyan")
                welcome_text.append("Type your message below to start chatting.\n", style="dim")
                
                chat_log.write(Panel(welcome_text, title="Welcome", border_style="green"))
                
                # Setup agent synchronously
                if not self.ui.agent.is_setup:
                    chat_log.write(Text("⚙️ Setting up agent...", style="yellow"))
                    # We'll handle setup in a worker thread
                    self.run_worker(self.setup_agent_worker, exclusive=True)
                else:
                    chat_log.write(Text("✅ Agent ready!", style="green"))
            
            async def setup_agent_worker(self):
                """Worker to set up the agent."""
                try:
                    await self.ui.setup_agent()
                    chat_log = self.query_one("#chat-log", RichLog)
                    chat_log.write(Text("✅ Agent setup complete!", style="green"))
                except Exception as e:
                    chat_log = self.query_one("#chat-log", RichLog)
                    chat_log.write(Text(f"❌ Agent setup failed: {e}", style="red"))

            def on_input_submitted(self, event: Input.Submitted) -> None:
                """Called when user submits input."""
                if event.input.id == "user-input":
                    self.run_worker(self.handle_user_input(event.value), exclusive=True)
                    event.input.value = ""

            def on_button_pressed(self, event: Button.Pressed) -> None:
                """Called when button is pressed."""
                if event.button.id == "send-button":
                    user_input = self.query_one("#user-input", Input)
                    if user_input.value.strip():
                        self.run_worker(self.handle_user_input(user_input.value), exclusive=True)
                        user_input.value = ""

            async def handle_user_input(self, message: str) -> None:
                """Handle user input message."""
                if self.processing:
                    return
                
                chat_log = self.query_one("#chat-log", RichLog)
                
                # Handle commands
                if message.startswith("/"):
                    await self.handle_command(message)
                    return
                
                # Add user message to chat
                user_text = Text()
                user_text.append("👤 You: ", style="bold blue")
                user_text.append(message)
                chat_log.write(Panel(user_text, border_style="blue"))
                
                # Add to chat history
                self.ui.chat_history.append(ChatMessage(MessageRole.USER, message))
                
                # Process with agent
                self.processing = True
                try:
                    # Show thinking indicator
                    thinking_text = Text("🤔 Agent is thinking...", style="dim yellow")
                    chat_log.write(thinking_text)
                    
                    # Stream response from agent
                    accumulated_response = ""
                    
                    def update_streaming_content(content: str):
                        """Update streaming content using timer to avoid threading issues."""
                        self.streaming_content = content
                    
                    def finalize_streaming_content(content: str):
                        """Move streaming content to chat log and clear streaming widget."""
                        if content:
                            # Add to chat log
                            agent_text = Text()
                            agent_text.append("🤖 Agent: ", style="bold green")
                            agent_text.append(content)
                            chat_log.write(Panel(agent_text, border_style="green"))
                            
                            # Add to chat history
                            self.ui.chat_history.append(ChatMessage(MessageRole.ASSISTANT, content))
                            
                            # Clear streaming widget
                            self.streaming_content = ""
                    
                    async for chat_message in self.stream_agent_response(message):
                        if chat_message.content.strip():
                            if chat_message.is_streaming:
                                # This is streaming content, accumulate and update display
                                accumulated_response = chat_message.content
                                # Use set_timer to update reactive variable safely
                                self.set_timer(0.01, lambda content=accumulated_response: update_streaming_content(content))
                            else:
                                # This is a complete message (like ActionStep)
                                if accumulated_response:
                                    # Finalize current streaming content first
                                    self.set_timer(0.01, lambda content=accumulated_response: finalize_streaming_content(content))
                                    accumulated_response = ""
                                
                                # Add the complete message directly to chat log
                                agent_text = Text()
                                agent_text.append("🤖 Agent: ", style="bold green")
                                agent_text.append(chat_message.content)
                                chat_log.write(Panel(agent_text, border_style="green"))
                                
                                # Add to chat history
                                self.ui.chat_history.append(ChatMessage(MessageRole.ASSISTANT, chat_message.content))
                    
                    # Finalize any remaining streaming content
                    if accumulated_response:
                        self.set_timer(0.01, lambda content=accumulated_response: finalize_streaming_content(content))
                
                except Exception as e:
                    error_text = Text(f"❌ Error: {str(e)}", style="bold red")
                    chat_log.write(Panel(error_text, border_style="red"))
                
                finally:
                    self.processing = False

            async def stream_agent_response(self, message: str):
                """Stream response from agent asynchronously."""
                try:
                    async for chat_msg in stream_to_textual(
                        self.ui.agent, 
                        message, 
                        reset_agent_memory=self.ui.reset_agent_memory
                    ):
                        yield chat_msg
                except Exception as e:
                    yield ChatMessage(MessageRole.ASSISTANT, f"❌ Error: {str(e)}")

            def handle_command(self, command: str) -> None:
                """Handle special commands."""
                chat_log = self.query_one("#chat-log", RichLog)
                
                if command == "/help":
                    help_text = Text()
                    help_text.append("📋 Available Commands:\n", style="bold cyan")
                    help_text.append("/help - Show this help message\n")
                    help_text.append("/clear - Clear chat history\n")
                    help_text.append("/reset - Reset agent memory\n")
                    help_text.append("/upload <path> - Upload a file\n")
                    help_text.append("/quit or /exit - Exit the application\n")
                    chat_log.write(Panel(help_text, title="Help", border_style="cyan"))
                
                elif command == "/clear":
                    chat_log.clear()
                    self.ui.chat_history.clear()
                    chat_log.write(Text("🧹 Chat history cleared!", style="green"))
                
                elif command == "/reset":
                    if hasattr(self.ui.agent, 'reset_state'):
                        self.ui.agent.reset_state()
                        chat_log.write(Text("🔄 Agent memory reset!", style="green"))
                    else:
                        chat_log.write(Text("⚠️ Agent doesn't support memory reset", style="yellow"))
                
                elif command.startswith("/upload "):
                    file_path = command[8:].strip()
                    if file_path:
                        result = self.ui.upload_file(file_path)
                        style = "green" if "✅" in result else "red"
                        chat_log.write(Text(result, style=style))
                    else:
                        chat_log.write(Text("❌ Please provide a file path: /upload <path>", style="red"))
                
                elif command in ["/quit", "/exit"]:
                    self.exit()
                
                else:
                    chat_log.write(Text(f"❌ Unknown command: {command}. Type /help for available commands.", style="red"))

        return MinionApp(self)

    def run(self):
        """Run the Textual UI application."""
        try:
            app = self.create_app()
            # Now we can use asyncio.run normally since we don't globally replace sys.modules["asyncio"]
            #asyncio.run(app.run_async())
            app.run()
        except KeyboardInterrupt:
            print("\n👋 Exiting Textual UI...")
        except Exception as e:
            print(f"❌ Error running Textual UI: {e}")
            raise

    async def run_async(self):
        """Run the Textual UI application asynchronously."""
        app = self.create_app()
        await app.run_async()


__all__ = ["TextualUI", "stream_to_textual", "ChatMessage"]