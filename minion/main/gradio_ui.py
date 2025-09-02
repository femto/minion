#!/usr/bin/env python
# coding=utf-8
# Adapted from HuggingFace smolagents for minion project
import os
import re
import shutil
from pathlib import Path
from typing import Generator, Dict, Any, Optional, Union
from enum import Enum

# Import minion components instead of smolagents
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

# Mock classes for compatibility with smolagents interface
class AgentText:
    def __init__(self, text: str):
        self.text = text
    
    def to_string(self) -> str:
        return self.text

class AgentImage:
    def __init__(self, path: str):
        self.path = path
    
    def to_string(self) -> str:
        return self.path

class AgentAudio:
    def __init__(self, path: str):
        self.path = path
    
    def to_string(self) -> str:
        return self.path

class PlanningStep:
    def __init__(self, plan: str, step_number: int = 0):
        self.plan = plan
        self.step_number = step_number
        self.token_usage = None
        self.timing = type('obj', (object,), {'duration': 0.0})()

class FinalAnswerStep:
    def __init__(self, output: Any):
        self.output = output

class ChatMessageStreamDelta:
    def __init__(self, content: str = "", role: str = "assistant"):
        self.content = content
        self.role = role
    
    def render_as_markdown(self) -> str:
        return self.content

def agglomerate_stream_deltas(deltas) -> ChatMessageStreamDelta:
    """Combine multiple stream deltas into one."""
    content = "".join(delta.content for delta in deltas if hasattr(delta, 'content'))
    return ChatMessageStreamDelta(content=content)


def get_step_footnote_content(step_log: Union[ActionStep, PlanningStep], step_name: str) -> str:
    """Get a footnote string for a step log with duration and token information"""
    step_footnote = f"**{step_name}**"
    
    # Handle token usage if available
    if hasattr(step_log, 'token_usage') and step_log.token_usage is not None:
        if hasattr(step_log.token_usage, 'input_tokens'):
            step_footnote += f" | Input tokens: {step_log.token_usage.input_tokens:,} | Output tokens: {step_log.token_usage.output_tokens:,}"
    
    # Handle timing if available
    if hasattr(step_log, 'timing') and step_log.timing and hasattr(step_log.timing, 'duration'):
        if step_log.timing.duration:
            step_footnote += f" | Duration: {round(float(step_log.timing.duration), 2)}s"
    elif hasattr(step_log, 'duration'):
        step_footnote += f" | Duration: {round(float(step_log.duration), 2)}s"
    
    step_footnote_content = f"""<span style="color: #bbbbc2; font-size: 12px;">{step_footnote}</span> """
    return step_footnote_content


def _clean_model_output(model_output: str) -> str:
    """
    Clean up model output by removing trailing tags and extra backticks.

    Args:
        model_output (`str`): Raw model output.

    Returns:
        `str`: Cleaned model output.
    """
    if not model_output:
        return ""
    model_output = model_output.strip()
    # Remove any trailing <end_code> and extra backticks, handling multiple possible formats
    model_output = re.sub(r"```\s*<end_code>", "```", model_output)  # handles ```<end_code>
    model_output = re.sub(r"<end_code>\s*```", "```", model_output)  # handles <end_code>```
    model_output = re.sub(r"```\s*\n\s*<end_code>", "```", model_output)  # handles ```\n<end_code>
    return model_output.strip()


def _format_code_content(content: str) -> str:
    """
    Format code content as Python code block if it's not already formatted.

    Args:
        content (`str`): Code content to format.

    Returns:
        `str`: Code content formatted as a Python code block.
    """
    content = content.strip()
    # Remove existing code blocks and end_code tags
    content = re.sub(r"```.*?\n", "", content)
    content = re.sub(r"\s*<end_code>\s*", "", content)
    content = content.strip()
    # Add Python code block formatting if not already present
    if not content.startswith("```python"):
        content = f"```python\n{content}\n```"
    return content


def _process_action_step(step_log: ActionStep, skip_model_outputs: bool = False) -> Generator:
    """
    Process an ActionStep and yield appropriate Gradio ChatMessage objects.

    Args:
        step_log (ActionStep): ActionStep to process.
        skip_model_outputs (bool): Whether to skip model outputs.

    Yields:
        gradio.ChatMessage: Gradio ChatMessages representing the action step.
    """
    import gradio as gr

    # Output the step number
    step_number = f"Step {getattr(step_log, 'step_number', 1)}"
    if not skip_model_outputs:
        yield gr.ChatMessage(role=MessageRole.ASSISTANT, content=f"**{step_number}**", metadata={"status": "done"})

    # First yield the thought/reasoning from the LLM
    if not skip_model_outputs:
        # Try to get model output from various possible attributes
        model_output = ""
        if hasattr(step_log, 'model_output') and step_log.model_output:
            model_output = step_log.model_output
        elif hasattr(step_log, 'content') and step_log.content:
            model_output = step_log.content
        elif hasattr(step_log, 'response') and step_log.response:
            model_output = step_log.response
        
        if model_output:
            model_output = _clean_model_output(str(model_output))
            yield gr.ChatMessage(role=MessageRole.ASSISTANT, content=model_output, metadata={"status": "done"})

    # For tool calls, create a parent message
    tool_calls = getattr(step_log, "tool_calls", []) or getattr(step_log, "actions", [])
    if tool_calls:
        first_tool_call = tool_calls[0] if isinstance(tool_calls, list) else tool_calls
        
        # Handle different tool call formats
        tool_name = getattr(first_tool_call, 'name', getattr(first_tool_call, 'tool_name', 'unknown_tool'))
        used_code = tool_name in ["python_interpreter", "code_executor", "python"]

        # Process arguments based on type
        args = getattr(first_tool_call, 'arguments', getattr(first_tool_call, 'args', {}))
        if isinstance(args, dict):
            content = str(args.get("answer", args.get("code", str(args))))
        else:
            content = str(args).strip()

        # Format code content if needed
        if used_code:
            content = _format_code_content(content)

        # Create the tool call message
        parent_message_tool = gr.ChatMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            metadata={
                "title": f"🛠️ Used tool {tool_name}",
                "status": "done",
            },
        )
        yield parent_message_tool

    # Display execution logs if they exist
    observations = getattr(step_log, "observations", "") or getattr(step_log, "logs", "")
    if observations and str(observations).strip():
        log_content = str(observations).strip()
        if log_content:
            log_content = re.sub(r"^Execution logs:\s*", "", log_content)
            yield gr.ChatMessage(
                role=MessageRole.ASSISTANT,
                content=f"```bash\n{log_content}\n```",
                metadata={"title": "📝 Execution Logs", "status": "done"},
            )

    # Display any images in observations
    observations_images = getattr(step_log, "observations_images", []) or getattr(step_log, "images", [])
    if observations_images:
        for image in observations_images:
            path_image = AgentImage(image).to_string()
            yield gr.ChatMessage(
                role=MessageRole.ASSISTANT,
                content={"path": path_image, "mime_type": f"image/{path_image.split('.')[-1]}"},
                metadata={"title": "🖼️ Output Image", "status": "done"},
            )

    # Handle errors
    error = getattr(step_log, "error", None)
    if error:
        yield gr.ChatMessage(
            role=MessageRole.ASSISTANT, content=str(error), metadata={"title": "💥 Error", "status": "done"}
        )

    # Add step footnote and separator
    yield gr.ChatMessage(
        role=MessageRole.ASSISTANT,
        content=get_step_footnote_content(step_log, step_number),
        metadata={"status": "done"},
    )
    yield gr.ChatMessage(role=MessageRole.ASSISTANT, content="-----", metadata={"status": "done"})


def _process_planning_step(step_log: PlanningStep, skip_model_outputs: bool = False) -> Generator:
    """
    Process a PlanningStep and yield appropriate gradio.ChatMessage objects.

    Args:
        step_log (PlanningStep): PlanningStep to process.
        skip_model_outputs (bool): Whether to skip model outputs.

    Yields:
        gradio.ChatMessage: Gradio ChatMessages representing the planning step.
    """
    import gradio as gr

    if not skip_model_outputs:
        yield gr.ChatMessage(role=MessageRole.ASSISTANT, content="**Planning step**", metadata={"status": "done"})
        plan_content = getattr(step_log, 'plan', getattr(step_log, 'content', 'Planning...'))
        yield gr.ChatMessage(role=MessageRole.ASSISTANT, content=str(plan_content), metadata={"status": "done"})
    yield gr.ChatMessage(
        role=MessageRole.ASSISTANT,
        content=get_step_footnote_content(step_log, "Planning step"),
        metadata={"status": "done"},
    )
    yield gr.ChatMessage(role=MessageRole.ASSISTANT, content="-----", metadata={"status": "done"})


def _process_final_answer_step(step_log: FinalAnswerStep) -> Generator:
    """
    Process a FinalAnswerStep and yield appropriate gradio.ChatMessage objects.

    Args:
        step_log (FinalAnswerStep): FinalAnswerStep to process.

    Yields:
        gradio.ChatMessage: Gradio ChatMessages representing the final answer.
    """
    import gradio as gr

    final_answer = getattr(step_log, 'output', getattr(step_log, 'answer', step_log))
    
    if isinstance(final_answer, AgentText):
        yield gr.ChatMessage(
            role=MessageRole.ASSISTANT,
            content=f"**Final answer:**\n{final_answer.to_string()}\n",
            metadata={"status": "done"},
        )
    elif isinstance(final_answer, AgentImage):
        yield gr.ChatMessage(
            role=MessageRole.ASSISTANT,
            content={"path": final_answer.to_string(), "mime_type": "image/png"},
            metadata={"status": "done"},
        )
    elif isinstance(final_answer, AgentAudio):
        yield gr.ChatMessage(
            role=MessageRole.ASSISTANT,
            content={"path": final_answer.to_string(), "mime_type": "audio/wav"},
            metadata={"status": "done"},
        )
    else:
        yield gr.ChatMessage(
            role=MessageRole.ASSISTANT, content=f"**Final answer:** {str(final_answer)}", metadata={"status": "done"}
        )


def pull_messages_from_step(step_log: Union[ActionStep, PlanningStep, FinalAnswerStep, StreamChunk, AgentResponse], skip_model_outputs: bool = False):
    """Extract Gradio ChatMessage objects from agent steps with proper nesting.

    Args:
        step_log: The step log to display as gr.ChatMessage objects.
        skip_model_outputs: If True, skip the model outputs when creating the gr.ChatMessage objects:
            This is used for instance when streaming model outputs have already been displayed.
    """
    if not _is_package_available("gradio"):
        raise ModuleNotFoundError(
            "Please install 'gradio' extra to use the GradioUI: `pip install 'minion[gradio]'`"
        )
    
    import gradio as gr
    
    # Handle StreamChunk objects
    if isinstance(step_log, StreamChunk):
        content = step_log.content
        chunk_type = getattr(step_log, 'chunk_type', 'llm_output')
        
        if chunk_type == 'error':
            yield gr.ChatMessage(
                role=MessageRole.ASSISTANT, 
                content=content, 
                metadata={"title": "💥 Error", "status": "done"}
            )
        elif chunk_type == 'final_answer':
            yield gr.ChatMessage(
                role=MessageRole.ASSISTANT, 
                content=f"**Final answer:** {content}", 
                metadata={"status": "done"}
            )
        else:
            yield gr.ChatMessage(
                role=MessageRole.ASSISTANT, 
                content=content, 
                metadata={"status": "done"}
            )
        return
    
    # Handle AgentResponse objects
    if isinstance(step_log, AgentResponse):
        if step_log.raw_response:
            yield gr.ChatMessage(
                role=MessageRole.ASSISTANT, 
                content=str(step_log.raw_response), 
                metadata={"status": "done"}
            )
        if step_log.final_answer:
            yield gr.ChatMessage(
                role=MessageRole.ASSISTANT, 
                content=f"**Final answer:** {step_log.final_answer}", 
                metadata={"status": "done"}
            )
        if step_log.error:
            yield gr.ChatMessage(
                role=MessageRole.ASSISTANT, 
                content=str(step_log.error), 
                metadata={"title": "💥 Error", "status": "done"}
            )
        return
    
    # Handle traditional step types
    if isinstance(step_log, ActionStep):
        yield from _process_action_step(step_log, skip_model_outputs)
    elif isinstance(step_log, PlanningStep):
        yield from _process_planning_step(step_log, skip_model_outputs)
    elif isinstance(step_log, FinalAnswerStep):
        yield from _process_final_answer_step(step_log)
    else:
        # Fallback for unknown types - try to extract content
        content = str(step_log)
        if hasattr(step_log, 'content'):
            content = str(step_log.content)
        elif hasattr(step_log, 'response'):
            content = str(step_log.response)
        
        yield gr.ChatMessage(
            role=MessageRole.ASSISTANT, 
            content=content, 
            metadata={"status": "done"}
        )


def stream_to_gradio(
    agent: BaseAgent,
    task: str,
    task_images: Optional[list] = None,
    reset_agent_memory: bool = False,
    additional_args: Optional[dict] = None,
) -> Generator:
    """Runs an agent with the given task and streams the messages from the agent as gradio ChatMessages."""

    if not _is_package_available("gradio"):
        raise ModuleNotFoundError(
            "Please install 'gradio' extra to use the GradioUI: `pip install 'minion[gradio]'`"
        )
    
    import gradio as gr
    
    # Convert task to Input object if needed
    if isinstance(task, str):
        input_obj = Input(query=task)
    else:
        input_obj = task
    
    # Handle images if provided (for future extension)
    if task_images:
        # For now, just add them to metadata
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
        
        # Use a thread-based approach to avoid event loop conflicts
        import threading
        import queue
        import time
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def run_agent_in_thread():
            """Run the agent in a separate thread with its own event loop."""
            try:
                import asyncio
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def agent_runner():
                    try:
                        async for event in (await agent.run_async(input_obj, **kwargs)):
                            result_queue.put(('event', event))
                    except Exception as e:
                        result_queue.put(('error', e))
                    finally:
                        result_queue.put(('done', None))
                
                loop.run_until_complete(agent_runner())
                loop.close()
                
            except Exception as e:
                exception_queue.put(e)
                result_queue.put(('error', e))
        
        # Start the agent in a separate thread
        agent_thread = threading.Thread(target=run_agent_in_thread, daemon=True)
        agent_thread.start()
        
        # Process results as they come in
        while True:
            try:
                # Check for exceptions first
                if not exception_queue.empty():
                    raise exception_queue.get_nowait()
                
                # Get the next result with a timeout
                try:
                    result_type, event = result_queue.get(timeout=0.1)
                except queue.Empty:
                    # Check if thread is still alive
                    if not agent_thread.is_alive():
                        break
                    continue
                
                if result_type == 'done':
                    break
                elif result_type == 'error':
                    raise event
                elif result_type == 'event':
                    # Process the event
                    if isinstance(event, (ActionStep, PlanningStep, FinalAnswerStep, StreamChunk, AgentResponse)):
                        for message in pull_messages_from_step(event, skip_model_outputs=getattr(agent, "stream_outputs", False)):
                            yield message
                    elif isinstance(event, str):
                        yield gr.ChatMessage(
                            role=MessageRole.ASSISTANT,
                            content=event,
                            metadata={"status": "pending"}
                        )
                    else:
                        content = str(event)
                        yield gr.ChatMessage(
                            role=MessageRole.ASSISTANT,
                            content=content,
                            metadata={"status": "done"}
                        )
                        
            except queue.Empty:
                continue
        
        # Wait for thread to complete
        agent_thread.join(timeout=1.0)
                
    except Exception as e:
        # Handle any errors in streaming
        yield gr.ChatMessage(
            role=MessageRole.ASSISTANT,
            content=f"Error in agent execution: {str(e)}",
            metadata={"title": "💥 Error", "status": "done"}
        )


class GradioUI:
    """
    Gradio interface for interacting with a BaseAgent (including CodeAgent).

    This class provides a web interface to interact with the agent in real-time, allowing users to submit prompts, upload files, and receive responses in a chat-like format.
    It can reset the agent's memory at the start of each interaction if desired.
    It supports file uploads, which are saved to a specified folder.
    It uses the gradio.Chatbot component to display the conversation history.
    This class requires the `gradio` extra to be installed: `pip install 'minion[gradio]'`.

    Args:
        agent (BaseAgent): The agent to interact with (BaseAgent, CodeAgent, etc.).
        file_upload_folder (str, optional): The folder where uploaded files will be saved.
            If not provided, file uploads are disabled.
        reset_agent_memory (bool, optional, defaults to False): Whether to reset the agent's memory at the start of each interaction.
            If True, the agent will not remember previous interactions.

    Raises:
        ModuleNotFoundError: If the `gradio` extra is not installed.

    Example:
        ```python
        from minion.agents.code_agent import CodeAgent
        from minion.main.gradio_ui import GradioUI
        from minion.main.brain import Brain

        brain = Brain()
        agent = CodeAgent(brain=brain, tools=[])
        gradio_ui = GradioUI(agent, file_upload_folder="uploads", reset_agent_memory=True)
        gradio_ui.launch()
        ```
    """

    def __init__(self, agent: BaseAgent, file_upload_folder: Optional[str] = None, reset_agent_memory: bool = False):
        if not _is_package_available("gradio"):
            raise ModuleNotFoundError(
                "Please install 'gradio' extra to use the GradioUI: `pip install 'minion[gradio]'`"
            )
        self.agent = agent
        self.file_upload_folder = Path(file_upload_folder) if file_upload_folder is not None else None
        self.reset_agent_memory = reset_agent_memory
        self.name = getattr(agent, "name", "Minion Agent Interface")
        self.description = getattr(agent, "description", "A powerful AI agent that can execute code and use tools to solve complex tasks.")
        if self.file_upload_folder is not None:
            if not self.file_upload_folder.exists():
                self.file_upload_folder.mkdir(parents=True, exist_ok=True)

    def interact_with_agent(self, prompt, messages, session_state):
        import gradio as gr
        import asyncio

        # Get the agent from session state or use the default agent
        if "agent" not in session_state:
            session_state["agent"] = self.agent

        try:
            # Add user message
            messages.append(gr.ChatMessage(role="user", content=prompt, metadata={"status": "done"}))
            yield messages

            # Ensure agent is set up
            agent = session_state["agent"]
            if not agent.is_setup:
                # Run setup in a thread to avoid blocking
                try:
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
                    
                    setup_thread = threading.Thread(target=setup_agent, daemon=True)
                    setup_thread.start()
                    setup_thread.join(timeout=30)
                    
                    if not setup_result.empty():
                        result_type, result = setup_result.get()
                        if result_type == 'error':
                            raise result
                    else:
                        raise TimeoutError("Agent setup timed out")
                        
                except Exception as setup_error:
                    messages.append(gr.ChatMessage(
                        role=MessageRole.ASSISTANT, 
                        content=f"Error setting up agent: {setup_error}", 
                        metadata={"title": "💥 Setup Error", "status": "done"}
                    ))
                    yield messages
                    return

            # Stream responses from agent
            for msg in stream_to_gradio(
                agent, task=prompt, reset_agent_memory=self.reset_agent_memory
            ):
                if isinstance(msg, gr.ChatMessage):
                    # Mark previous message as done if it was pending
                    if messages and messages[-1].metadata.get("status") == "pending":
                        messages[-1].metadata["status"] = "done"
                    messages.append(msg)
                elif isinstance(msg, str):  # Then it's only a completion delta
                    msg = msg.replace("<", r"\<").replace(">", r"\>")  # HTML tags seem to break Gradio Chatbot
                    if messages and messages[-1].metadata.get("status") == "pending":
                        messages[-1].content = msg
                    else:
                        messages.append(
                            gr.ChatMessage(role=MessageRole.ASSISTANT, content=msg, metadata={"status": "pending"})
                        )
                yield messages

            # Mark final message as done
            if messages and messages[-1].metadata.get("status") == "pending":
                messages[-1].metadata["status"] = "done"
            yield messages
            
        except Exception as e:
            # Add error message
            messages.append(gr.ChatMessage(
                role=MessageRole.ASSISTANT, 
                content=f"Error in interaction: {str(e)}", 
                metadata={"title": "💥 Error", "status": "done"}
            ))
            yield messages

    def upload_file(self, file, file_uploads_log, allowed_file_types=None):
        """
        Upload a file and add it to the list of uploaded files in the session state.

        The file is saved to the `self.file_upload_folder` folder.
        If the file type is not allowed, it returns a message indicating the disallowed file type.

        Args:
            file (`gradio.File`): The uploaded file.
            file_uploads_log (`list`): A list to log uploaded files.
            allowed_file_types (`list`, *optional*): List of allowed file extensions. Defaults to [".pdf", ".docx", ".txt"].
        """
        import gradio as gr

        if file is None:
            return gr.Textbox(value="No file uploaded", visible=True), file_uploads_log

        if allowed_file_types is None:
            allowed_file_types = [".pdf", ".docx", ".txt"]

        file_ext = os.path.splitext(file.name)[1].lower()
        if file_ext not in allowed_file_types:
            return gr.Textbox("File type disallowed", visible=True), file_uploads_log

        # Sanitize file name
        original_name = os.path.basename(file.name)
        sanitized_name = re.sub(
            r"[^\w\-.]", "_", original_name
        )  # Replace any non-alphanumeric, non-dash, or non-dot characters with underscores

        # Save the uploaded file to the specified folder
        file_path = os.path.join(self.file_upload_folder, os.path.basename(sanitized_name))
        shutil.copy(file.name, file_path)

        return gr.Textbox(f"File uploaded: {file_path}", visible=True), file_uploads_log + [file_path]

    def log_user_message(self, text_input, file_uploads_log):
        import gradio as gr

        return (
            text_input
            + (
                f"\nYou have been provided with these files, which might be helpful or not: {file_uploads_log}"
                if len(file_uploads_log) > 0
                else ""
            ),
            "",
            gr.Button(interactive=False),
        )

    def launch(self, share: bool = False, debug: bool = True, server_port: int = None, **kwargs):
        """
        Launch the Gradio app with the agent interface.

        Args:
            share (bool, defaults to False): Whether to share the app publicly.
            debug (bool, defaults to True): Whether to enable debug mode.
            server_port (int, optional): Port to use. If None, will find an available port.
            **kwargs: Additional keyword arguments to pass to the Gradio launch method.
        """
        import socket
        import time
        
        def find_free_port(start=8000):
            """Find a free port starting from the given port."""
            for port in range(start, start + 100):  # Much larger range
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s.bind(('127.0.0.1', port))
                        return port
                except OSError:
                    continue
            return None
        
        def kill_processes_on_port(port):
            """Kill any processes using the specified port."""
            try:
                import subprocess
                # Find processes using the port
                result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                      capture_output=True, text=True)
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            subprocess.run(['kill', '-9', pid], check=True)
                            print(f"🔄 Killed process {pid} using port {port}")
                        except subprocess.CalledProcessError:
                            pass
                    time.sleep(1)  # Give time for cleanup
            except (subprocess.CalledProcessError, FileNotFoundError):
                # lsof might not be available or other error
                pass
        
        # Handle port selection - use a different range to avoid conflicts
        if server_port is None:
            server_port = find_free_port(8000)  # Start from port 8000
            if server_port is None:
                print("⚠️ Could not find a free port in 8000-8100 range, trying system auto-select...")
                server_port = 0  # Let system choose any available port
        
        # Clean up any processes that might be using our target port
        if server_port and server_port != 0:
            kill_processes_on_port(server_port)
        
        # Build launch arguments with proper settings for Gradio 4.x/5.x
        launch_kwargs = {
            "share": share,
            "prevent_thread_lock": False,
            "show_error": True,
            "quiet": False,
            **kwargs
        }
        
        # Only set server_port if we found a specific one
        if server_port and server_port != 0:
            launch_kwargs["server_port"] = server_port
        # If server_port is 0, don't set it and let Gradio auto-select
        
        # Set default server settings if not provided
        if "server_name" not in launch_kwargs:
            launch_kwargs["server_name"] = "127.0.0.1"
        
        print(f"🌐 Launching Gradio interface...")
        if server_port and server_port != 0:
            print(f"📍 Server will start at: http://{launch_kwargs.get('server_name', '127.0.0.1')}:{server_port}")
        else:
            print(f"📍 Server will start at: http://{launch_kwargs.get('server_name', '127.0.0.1')}:<auto-selected-port>")
        
        try:
            # Create the app and launch it
            app = self.create_app()
            
            print("ℹ️  Note: You may see some warnings about deprecated features - these are normal and don't affect functionality.")
            print("ℹ️  If you encounter port issues, try: GRADIO_SERVER_PORT=8080 python your_script.py")
            
            # If we have port issues, try without specifying a port
            if "server_port" in launch_kwargs:
                try:
                    app.launch(**launch_kwargs)
                except OSError as e:
                    if "port" in str(e).lower():
                        print(f"⚠️ Port issue detected, letting Gradio auto-select port...")
                        # Remove server_port and let Gradio choose
                        launch_kwargs_auto = launch_kwargs.copy()
                        launch_kwargs_auto.pop("server_port", None)
                        app.launch(**launch_kwargs_auto)
                    else:
                        raise
            else:
                app.launch(**launch_kwargs)
                
        except Exception as e:
            print(f"❌ Error launching Gradio: {e}")
            print("💡 Try running with: GRADIO_SERVER_PORT=8080 python your_script.py")
            raise

    def create_app(self):
        import gradio as gr
        
        # Use legacy layout compatible with Gradio 4.x and 5.x
        with gr.Blocks(theme="ocean") as demo:
            # Add session state to store session-specific data
            session_state = gr.State({})
            stored_messages = gr.State([])
            file_uploads_log = gr.State([])
            
            with gr.Row():
                with gr.Column(scale=1, min_width=300):
                    gr.Markdown(
                        f"# {self.name.replace('_', ' ').capitalize()}"
                        "\n> This web ui allows you to interact with a `minion` agent that can use tools and execute steps to complete tasks."
                        + (f"\n\n**Agent description:**\n{self.description}" if self.description else "")
                    )

                    with gr.Group():
                        gr.Markdown("**Your request**")
                        text_input = gr.Textbox(
                            lines=3,
                            label="Chat Message",
                            container=False,
                            placeholder="Enter your prompt here and press Shift+Enter or press the button",
                        )
                        submit_btn = gr.Button("Submit", variant="primary")

                    # If an upload folder is provided, enable the upload feature
                    if self.file_upload_folder is not None:
                        upload_file = gr.File(label="Upload a file")
                        upload_status = gr.Textbox(label="Upload Status", interactive=False, visible=False)
                        upload_file.change(
                            self.upload_file,
                            [upload_file, file_uploads_log],
                            [upload_status, file_uploads_log],
                        )

                    gr.HTML(
                        "<br><br><h4><center>Powered by <a target='_blank' href='https://github.com/femto/minion'><b>minion</b></a></center></h4>"
                    )
                
                with gr.Column(scale=3):
                    # Main chat interface
                    chatbot = gr.Chatbot(
                        label="Agent",
                        type="messages",
                        avatar_images=(
                            None,
                            "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/smolagents/mascot_smol.png",
                        ),
                        height=600,
                        latex_delimiters=[
                            {"left": r"$", "right": r"$", "display": True},
                            {"left": r"$", "right": r"$", "display": False},
                            {"left": r"\[", "right": r"\]", "display": True},
                            {"left": r"\(", "right": r"\)", "display": False},
                        ],
                    )

            # Set up event handlers
            text_input.submit(
                self.log_user_message,
                [text_input, file_uploads_log],
                [stored_messages, text_input, submit_btn],
            ).then(self.interact_with_agent, [stored_messages, chatbot, session_state], [chatbot]).then(
                lambda: (
                    gr.Textbox(
                        interactive=True, placeholder="Enter your prompt here and press Shift+Enter or the button"
                    ),
                    gr.Button(interactive=True),
                ),
                None,
                [text_input, submit_btn],
            )

            submit_btn.click(
                self.log_user_message,
                [text_input, file_uploads_log],
                [stored_messages, text_input, submit_btn],
            ).then(self.interact_with_agent, [stored_messages, chatbot, session_state], [chatbot]).then(
                lambda: (
                    gr.Textbox(
                        interactive=True, placeholder="Enter your prompt here and press Shift+Enter or the button"
                    ),
                    gr.Button(interactive=True),
                ),
                None,
                [text_input, submit_btn],
            )

            # Handle memory reset - different agents may have different reset methods
            def reset_memory():
                if hasattr(self.agent, 'reset_state'):
                    self.agent.reset_state()
                elif hasattr(self.agent, 'memory') and hasattr(self.agent.memory, 'reset'):
                    self.agent.memory.reset()
                elif hasattr(self.agent, 'brain') and hasattr(self.agent.brain, 'reset'):
                    self.agent.brain.reset()
            
            # For Gradio 4.x compatibility, we don't use chatbot.clear()
            # Memory reset will be handled in the interact_with_agent method
        return demo


__all__ = ["stream_to_gradio", "GradioUI"]