#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Code execution worker minions - Python code generation and execution
"""
import asyncio
import os
import re
import uuid
from typing import Any

from jinja2 import Template

from minion.actions.lmp_action_node import LmpActionNode
from minion.exceptions import FinalAnswerException
from minion.logs import logger
from minion.main.async_python_executor import AsyncPythonExecutor
from minion.main.base_workers import WorkerMinion
from minion.main.local_python_executor import LocalPythonExecutor
from minion.main.minion import register_worker_minion
from minion.main.prompt import (
    PYTHON_PROMPT,
    PYTHON_EXECUTE_PROMPT,
    WORKER_PROMPT,
    TASK_INPUT,
)
from minion.types.agent_response import AgentResponse
from minion.utils.answer_extraction import extract_python


def _deduplicate_tools(tools_list):
    """Deduplicate tools by name, keeping first occurrence."""
    seen_names = set()
    result = []
    for tool in tools_list:
        name = getattr(tool, 'name', None) or type(tool).__name__
        if name not in seen_names:
            seen_names.add(name)
            result.append(tool)
    return result


@register_worker_minion
class PythonMinion(WorkerMinion):
    "This problem requires writing code to solve it, write python code to solve it"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.python_env = self.brain.python_env

    async def execute(self):
        # Check post_processing setting, giving precedence to worker_config
        post_processing = None
        if self.worker_config and 'post_processing' in self.worker_config:
            post_processing = self.worker_config['post_processing']
        elif self.input.post_processing:
            post_processing = self.input.post_processing

        if self.input.query_type == "calculate":
            return await self.execute_calculation()
        elif post_processing == "extract_python" or self.input.query_type == "code_solution":
            return await self.execute_code_solution()
        elif self.input.query_type == "generate":
            return await self.execute_generation()
        else:
            return await self.execute_calculation()  # 默认行为

    async def execute_calculation(self):
        error = ""
        for i in range(5):
            node = LmpActionNode(llm=self.brain.llm)

            if not self.task:
                prompt = Template(
                    PYTHON_PROMPT
                    + PYTHON_EXECUTE_PROMPT
                    + WORKER_PROMPT
                    + """

also please check previous error, do the modification according to previous error if there's previous error.
Previous error:
{{error}}
                """
                )
                prompt = prompt.render(input=self.input, error=error)
            else:
                prompt = Template(
                    PYTHON_PROMPT
                    + PYTHON_EXECUTE_PROMPT
                    + WORKER_PROMPT
                    + TASK_INPUT
                    + """

 also please check previous error, do the modification according to previous error if there's previous error.
 Previous error:
 {{error}}"""
                )
                prompt = prompt.render(input=self.input, task=self.task, error=error)

            tools = (self.input.tools or []) + (self.brain.tools or [])
            code = await node.execute(prompt, tools=None)

            code = extract_python(code, self.input.entry_point)
            print(code)

            self.answer_code = self.input.answer_code = code

            self.input.run_id = self.input.run_id or uuid.uuid4()

            # Check if python_env has step or __call__ method
            if hasattr(self.python_env, 'step'):

                result = self.python_env.step(code)
                obs = result[0]  # obs

                if obs["error"]:
                    error = obs["error"]
                    logger.error(error)
                    self.answer = self.input.answer = f"output:{obs['output']}, error:{obs['error']}"
                    continue  # try again?
                output, error = obs["output"], obs["error"]
                self.answer = self.input.answer = output #answer is only output
            else:
                # LocalPythonExecutor or AsyncPythonExecutor with __call__ method
                try:
                    # Check if it's an async executor (AsyncPythonExecutor)
                    if hasattr(self.python_env, '__call__') and asyncio.iscoroutinefunction(self.python_env.__call__):
                        # Async executor - await the call
                        output, logs, is_final_answer = await self.python_env(code)
                    else:
                        # Sync executor - regular call
                        output, logs, is_final_answer = self.python_env(code)

                    if isinstance(output, Exception):
                        error = str(output)
                        logger.error(error)
                        self.answer = self.input.answer = f"error: {error}"
                        continue
                    else:
                        # Use logs as output if available, otherwise use output
                        result_text = logs if logs else str(output)
                        self.answer = self.input.answer = result_text

                        # If this is a final answer, break the loop and return with terminated=True
                        if is_final_answer:
                            print(f"###final_answer###:{self.answer}")
                            return AgentResponse(
                                raw_response=self.answer,
                                answer=self.answer,
                                score=1.0,
                                terminated=True,
                                truncated=False,
                                info={'execution_successful': True, 'is_final_answer': True}
                            )
                except Exception as e:
                    error = str(e)
                    logger.error(error)
                    self.answer = self.input.answer = f"error: {error}"
                    continue

            print(f"###answer###:{self.answer}")
            # Return AgentResponse for successful execution
            return AgentResponse(
                raw_response=self.answer,
                answer=self.answer,
                score=1.0,
                terminated=False,
                truncated=False,
                info={'execution_successful': True}
            )

        # Return AgentResponse even if all attempts failed
        return AgentResponse(
            raw_response=self.answer,
            answer=self.answer,
            score=0.0,
            terminated=False,
            truncated=False,
            info={'execution_failed': True}
        )

    async def execute_code_solution(self):
        error = ""
        for i in range(5):
            node = LmpActionNode(llm=self.brain.llm)

            if self.task:
                # Task mode: use TASK_INPUT template
                prompt = Template(
                    PYTHON_PROMPT
                    + WORKER_PROMPT
                    + TASK_INPUT
                    + """
                    Generate a complete Python solution for the given task.
                    This may include one or more functions, classes, or a full module as needed.
                    Do not include any explanations or comments, just the code.
                    If you define the solution as a function, remember to invoke it

                    Previous error (if any):
                    {{error}}
                    """
                )
                prompt = prompt.render(input=self.input, task=self.task, error=error)
            else:
                # Normal mode: use original prompt
                prompt = Template(
                    PYTHON_PROMPT
                    + WORKER_PROMPT
                    + """
                    Generate a complete Python solution for the given problem.
                    This may include one or more functions, classes, or a full module as needed.
                    Do not include any explanations or comments, just the code.
                    If you define the solution as a function, remember to invoke it

                    Previous error (if any):
                    {{error}}
                    """
                )
                prompt = prompt.render(input=self.input, error=error)

            tools = (self.input.tools or []) + (self.brain.tools or [])
            code = await node.execute(prompt, tools=None)
            code = extract_python(code, self.input.entry_point)
            self.answer = self.input.answer = code

            # Return AgentResponse instead of just the answer
            return AgentResponse(
                raw_response=self.answer,
                answer=self.answer,
                score=1.0,
                terminated=False,
                truncated=False,
                info={'code_generated': True}
            )

    async def execute_generation(self):
        error = ""
        for i in range(5):
            node = LmpActionNode(llm=self.brain.llm)

            if self.task:
                # Task mode: use TASK_INPUT template
                prompt = Template(
                    PYTHON_PROMPT
                    + WORKER_PROMPT
                    + TASK_INPUT
                    + """
                    Create the necessary file structure and contents for the given task.
                    Include file paths and their contents.

                    Previous error (if any):
                    {{error}}
                    """
                )
                prompt = prompt.render(input=self.input, task=self.task, error=error)
            else:
                # Normal mode: use original prompt
                prompt = Template(
                    PYTHON_PROMPT
                    + WORKER_PROMPT
                    + """
                    Create the necessary file structure and contents for the given task.
                    Include file paths and their contents.

                    Previous error (if any):
                    {{error}}
                    """
                )
                prompt = prompt.render(input=self.input, error=error)

            tools = (self.input.tools or []) + (self.brain.tools or [])
            file_structure_text = await node.execute(prompt, tools=tools)
            file_structure = self.extract_file_structure(file_structure_text)
            self.save_files(file_structure)
            self.answer = self.input.answer = file_structure_text

            # Return AgentResponse instead of just the answer
            return AgentResponse(
                raw_response=self.answer,
                answer=self.answer,
                score=1.0,
                terminated=False,
                truncated=False,
                info={'files_generated': True, 'file_count': len(file_structure)}
            )

    def extract_file_structure(self, text):
        # 从LLM输出中提取项目结构和文件内容
        # 这需要根据LLM的出格式进行定
        # 返回一个字典键为文件路，值为文件内容
        structure = {}
        current_file = None
        for line in text.split("\n"):
            if line.startswith("File:"):
                current_file = line.split(":", 1)[1].strip()
                structure[current_file] = ""
            elif current_file:
                structure[current_file] += line + "\n"
        return structure

    def save_files(self, file_structure):
        # 将项目文件保存到磁盘
        for file_path, content in file_structure.items():
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)

    async def execute_stream(self):
        """流式执行方法 - PythonMinion 暂不支持真正的流式输出，回退到普通执行"""
        result = await self.execute()
        if isinstance(result, AgentResponse):
            yield result.answer if result.answer else str(result.raw_response)
        else:
            yield str(result)


@register_worker_minion
class CodeMinion(PythonMinion):
    """
    Code Minion using smolagents-style approach:
    Thought -> Code -> Observation cycle with <end_code> support
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "Solve this problem by writing Python code. Use the 'Thought -> Code -> Observation' approach."
        self.max_iterations = 5

        # Initialize LocalPythonExecutor with tools like smolagents
        if hasattr(self, 'python_env') and isinstance(self.python_env, (LocalPythonExecutor, AsyncPythonExecutor)):
            # Send variables (state) to the python executor
            variables = getattr(self.input, 'symbols', {})
            self.python_env.send_variables(variables=variables)

            # Send tools to the python executor
            brain_tools = getattr(self.brain, 'tools', [])
            input_tools = getattr(self.input, 'tools', [])
            all_tools = {}

            # Convert tools to dict format expected by send_tools
            for tool in (brain_tools + input_tools):
                if hasattr(tool, 'name'):
                    # Tool object with name attribute
                    all_tools[tool.name] = tool
                elif callable(tool) and hasattr(tool, '__name__'):
                    # Function with __name__ attribute
                    all_tools[tool.__name__] = tool
                elif callable(tool):
                    # Generic callable, use str representation as fallback
                    tool_name = getattr(tool, '__name__', str(tool))
                    all_tools[tool_name] = tool

            self.python_env.send_tools(all_tools)

    def _get_last_tool_from_code(self, code: str):
        """
        Extract the last tool called in the code by parsing AST.

        Args:
            code: Python code string to parse

        Returns:
            Tool object if found, None otherwise
        """
        import ast
        try:
            tree = ast.parse(code)
            # Get the last statement
            if not tree.body:
                return None

            last_stmt = tree.body[-1]

            # Handle different types of last statements
            tool_name = None
            if isinstance(last_stmt, ast.Expr) and isinstance(last_stmt.value, ast.Call):
                # Last statement is a direct function call
                call = last_stmt.value
                if isinstance(call.func, ast.Name):
                    tool_name = call.func.id
                elif isinstance(call.func, ast.Attribute):
                    tool_name = call.func.attr
            elif isinstance(last_stmt, (ast.Assign, ast.AnnAssign)):
                # Last statement is an assignment, check the value
                value = last_stmt.value if isinstance(last_stmt, ast.Assign) else last_stmt.value
                if isinstance(value, ast.Call):
                    call = value
                    if isinstance(call.func, ast.Name):
                        tool_name = call.func.id
                    elif isinstance(call.func, ast.Attribute):
                        tool_name = call.func.attr
            elif isinstance(last_stmt, ast.Await):
                # Handle await expressions
                if isinstance(last_stmt.value, ast.Call):
                    call = last_stmt.value
                    if isinstance(call.func, ast.Name):
                        tool_name = call.func.id
                    elif isinstance(call.func, ast.Attribute):
                        tool_name = call.func.attr

            # Look up tool from python_env's custom_tools
            if tool_name and hasattr(self.python_env, 'custom_tools'):
                return self.python_env.custom_tools.get(tool_name)

            return None
        except Exception as e:
            logger.debug(f"Failed to extract tool from code: {e}")
            return None

    def _format_output_for_observation(self, output: Any, code: str) -> str:
        """
        Format output for observation, using tool's format_for_observation if available.

        Args:
            output: The output from code execution
            code: The code that was executed

        Returns:
            Formatted output string
        """
        # Try to get the last tool used
        tool = self._get_last_tool_from_code(code)

        if tool and hasattr(tool, 'format_for_observation'):
            try:
                return tool.format_for_observation(output)
            except Exception as e:
                logger.debug(f"Failed to format output with tool.format_for_observation: {e}")
                # Fall back to default formatting

        # Default formatting
        return str(output) if output is not None else ""

    def construct_current_turn_messages(self, query, tools=[], task=None, error="", current_turn_attempts=[]):
        """Construct OpenAI messages format for current turn execution

        Args:
            query: Can be string, content blocks, or full messages list
            tools: Available tools list
            task: Task information
            error: Error information from previous attempts within current turn
            current_turn_attempts: current_turn_attempts

        Returns:
            List[Dict]: OpenAI messages format for current turn
        """
        # Get available tools description
        available_tools = []
        for tool in tools:
            if hasattr(tool, 'name') and hasattr(tool, 'description'):
                tool_desc = f"- {tool.name}: {tool.description}"

                # Add readonly information if available
                if hasattr(tool, 'readonly') and tool.readonly:
                    tool_desc += " [READONLY - This tool only reads data and does not modify system state]"

                # Add parameter information and usage example for tools
                tool_params = None
                if hasattr(tool, 'parameters') and tool.parameters:
                    if 'properties' in tool.parameters:
                        tool_params = tool.parameters['properties']
                elif hasattr(tool, 'inputs') and tool.inputs:
                    tool_params = tool.inputs

                if tool_params:
                    params = tool_params
                    param_list = []
                    for param_name, param_info in params.items():
                        param_type = param_info.get('type', 'any')
                        param_desc = param_info.get('description', '')
                        param_list.append(f"{param_name} ({param_type}): {param_desc}")
                    tool_desc += f"\n  Parameters: {', '.join(param_list)}"
                available_tools.append(tool_desc)

        tools_description = "\n".join(available_tools) if available_tools else "- print: Output information to the user"

        # Construct system message
        prompt = f"""You are an expert assistant who can solve any task using code blobs. You will be given a task to solve as best you can.
To do so, you have been given access to a list of tools. Each tool is actually a Python function which you can call by writing Python code. You can use the tool by writing Python code that calls the function.

You are provided with the following tools:
{tools_description}

**Important Notes for Asynchronous Operations:**
- You are already in an async context - DON'T use `asyncio.run()`
- Use `await` directly at the top level in your code: `result = await async_function()`
- When calling async tools or functions, always use `await` to get the actual result
- No need to wrap your code in async functions - just use `await` directly

**Important Notes for Tool Usage:**
- ALWAYS use keyword arguments when calling tools, never use positional arguments
- Example: `await tool_name(param1="value1", param2="value2")` ✓
- Never: `await tool_name("value1", "value2")` ✗
- All tool parameters must be explicitly named

You will be given a task to solve as best you can. To solve the task, you must plan and execute Python code step by step until you have solved the task.

Here is the format you should follow:
**Thought:** Your reasoning about what to do next
**Code:**
```python
# Your Python code here
```<end_code>

**Observation:** [This will be filled automatically with the execution result]

Continue this Thought/Code/Observation cycle until you solve the task completely."""

        messages = [{"role": "user", "content": prompt}]

        # Construct user message content
        user_content_parts = []

        # Add task or problem description
        if task:
            task_text = f"""**Task:** {task.get('instruction', '')}
**Description:** {task.get('task_description', '')}"""

            # Add dependent outputs if available
            if task.get("dependent"):
                dependent_info = "\n**Dependent outputs:**\n"
                for dependent in task["dependent"]:
                    dependent_key = dependent.get("dependent_key")
                    if dependent_key in self.input.symbols:
                        symbol = self.input.symbols[dependent_key]
                        dependent_info += f"- {dependent_key}: {symbol.output}\n"
                task_text += dependent_info

            user_content_parts.append({"type": "text", "text": task_text})
        else:
            # Handle different query formats
            if isinstance(query, str):
                user_content_parts.append({"type": "text", "text": f"**Problem:** {query}"})
            elif isinstance(query, list):
                # Add problem header
                user_content_parts.append({"type": "text", "text": "**Problem:**"})
                # Add multimodal content
                for item in query:
                    if isinstance(item, dict):
                        # Already formatted content block
                        user_content_parts.append(item)
                    elif isinstance(item, str):
                        # Plain text
                        user_content_parts.append({"type": "text", "text": item})
                    else:
                        # Convert other types to text
                        user_content_parts.append({"type": "text", "text": str(item)})

        # Add error information if available
        if error:
            error_text = f"""

**Previous Error:**
{error}

Please fix the error and try again."""
            user_content_parts.append({"type": "text", "text": error_text})

        # Add conversation history if available
        if current_turn_attempts:
            history_text = "\n\n**Previous attempts:**\n" + "\n".join(current_turn_attempts)
            user_content_parts.append({"type": "text", "text": history_text})

        # Add final instruction
        user_content_parts.append({"type": "text", "text": "\n\nLet's start! Remember to end your code blocks with <end_code>."})

        # Add user message
        messages.append({
            "role": "user",
            "content": user_content_parts
        })

        return messages

    def construct_messages_with_history(self, query, tools=[], task=None, error="", previous_turns_history=None):
        """Construct messages including previous turns history

        Args:
            query: Can be string, content blocks, or full messages list
            tools: Available tools list
            task: Task information
            error: Error information from previous attempts within current turn
            previous_turns_history: ConversationHistory object containing previous turns (from agent.state.history)

        Returns:
            List[Dict]: OpenAI messages format including previous turns history
        """
        # Construct current turn messages (includes error handling for current turn attempts)
        current_turn_messages = self.construct_current_turn_messages(query, tools, task, error, self.current_turn_attempts)

        # Simple logic: previous_turns_history + current_turn_messages
        if previous_turns_history and len(previous_turns_history) > 0:
            # Convert ConversationHistory to list of dicts
            history_messages = previous_turns_history.to_list()

            # Find system message if exists in current turn
            system_messages = []
            non_system_messages = []

            for msg in current_turn_messages:
                if msg.get("role") == "system":
                    system_messages.append(msg)
                else:
                    non_system_messages.append(msg)

            # Construct final order: system + previous_turns_history + current_turn_messages
            messages = system_messages + history_messages + non_system_messages
        else:
            messages = current_turn_messages

        return messages

    def _extract_query_text(self, query):
        """Extract text content from query (handle both string and messages format)

        Args:
            query: Can be string or messages list (supports both OpenAI messages format and content blocks format)

        Returns:
            str: Extracted text content
        """
        if isinstance(query, str):
            return query
        elif isinstance(query, list):
            text_parts = []
            for msg in query:
                if isinstance(msg, dict):
                    # Check if it's a content block format: {"type": "text", "content": "..."}
                    if msg.get("type") == "text" and "content" in msg:
                        text_parts.append(msg.get("content", ""))
                    # Check if it's a content block format with "text" field: {"type": "text", "text": "..."}
                    elif msg.get("type") == "text" and "text" in msg:
                        text_parts.append(msg.get("text", ""))
                    # Check if it's OpenAI messages format: {"role": "user", "content": "..."}
                    elif "role" in msg and "content" in msg:
                        content = msg["content"]
                        if isinstance(content, str):
                            text_parts.append(f"{msg.get('role', 'user')}: {content}")
                        elif isinstance(content, list):
                            # Extract text from nested content list
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    # Handle both "text" and "content" fields in nested items
                                    text_content = item.get("text") or item.get("content", "")
                                    if text_content:
                                        text_parts.append(f"{msg.get('role', 'user')}: {text_content}")
                    # Handle plain string items in the list
                elif isinstance(msg, str):
                    text_parts.append(msg)
            return "\n".join(text_parts) if text_parts else str(query)
        else:
            return str(query)

    def _get_history(self):
        """Get previous turns history from brain.state if available

        Returns:
            ConversationHistory: Previous conversation turns (from agent.state.history)
        """
        if hasattr(self.brain, 'state') and self.brain.state and hasattr(self.brain.state, 'history'):
            # Return the history (ConversationHistory object)
            return self.brain.state.history

        # Import here to avoid circular imports
        from minion.types.history import History
        return History()

    def _append_history(self, messages):
        """Append new messages to conversation history in brain.state if available

        Args:
            messages: List of OpenAI message format dicts or single message dict
        """
        if hasattr(self.brain, 'state') and self.brain.state and hasattr(self.brain.state, 'history'):
            # Add to agent state history (ConversationHistory object)
            if isinstance(messages, list):
                # Extend with multiple messages
                self.brain.state.history.extend(messages)
            else:
                # Append single message
                self.brain.state.history.append(messages)

    async def execute(self):
        """Execute with smolagents-style Thought -> Code -> Observation cycle"""

        # Determine the query to use
        if self.task:
            query = self.task.get("instruction", "") or self.task.get("task_description", "")
        else:
            query = self.input.query

        self.current_turn_attempts = []

        error = ""
        previous_turns_history = self._get_history()  # From agent.state.history (previous turns)
        tools = _deduplicate_tools(self.brain.tools + self.input.tools)

        for iteration in range(self.max_iterations):
            # Construct messages for this iteration including previous turns history
            messages = self.construct_messages_with_history(query, tools, self.task, error, previous_turns_history)

            # Get LLM response
            node = LmpActionNode(llm=self.brain.llm)
            tools = _deduplicate_tools((self.input.tools or []) + (self.brain.tools or []))

            # Add stop sequences for code execution
            stop_sequences = ["<end_code>"]

            try:
                response = await node.execute(messages, tools=tools, stop=stop_sequences)
                if response and not response.strip().endswith("<end_code>"):
                    response += "<end_code>"
            except FinalAnswerException as e:
                # 收到 final_answer 工具调用，直接返回结果
                # 注意：此时 response 还未赋值（异常在 node.execute 内部抛出）
                final_answer = e.answer
                self.answer = self.input.answer = final_answer
                print(f"Final answer exception detected: {final_answer}")

                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                # 返回 AgentResponse - 此处 raw_response 只能用 final_answer，因为没有 LLM 原始输出
                return AgentResponse(
                    raw_response=str(final_answer),  # 没有 LLM 输出可用，使用 answer
                    answer=final_answer,
                    is_final_answer=True,
                    score=1.0,
                    terminated=True,
                    truncated=False,
                    info={'final_answer_exception': True}
                )

            # Extract and execute code
            code_blocks = self.extract_code_blocks(response)
            self.current_turn_attempts.append(f"**Assistant Response {iteration + 1}:** {response}")
            if not code_blocks:
                # No code found, add LLM response to current turn and return

                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))

                self.answer = self.input.answer = response
                # Return AgentResponse for non-code response
                return AgentResponse(
                    raw_response=response,
                    answer=self.answer,
                    score=0.5,
                    terminated=True,
                    is_final_answer=True,
                    truncated=False,
                    info={'no_code_found': True}
                )

            # Execute the first code block
            code = code_blocks[0]
            print(f"Executing code:\n{code}")

            # Execute the code using python_env
            try:
                # Check if it's an async executor (AsyncPythonExecutor)
                if hasattr(self.python_env, '__call__') and asyncio.iscoroutinefunction(self.python_env.__call__):
                    # Async executor - await the call
                    output, logs, is_final_answer = await self.python_env(code)
                else:
                    # Sync executor - regular call (LocalPythonExecutor)
                    output, logs, is_final_answer = self.python_env(code)

                # Check if there was an error (output could be Exception)
                if isinstance(output, Exception):
                    error = str(output)
                    logger.error(f"Code execution error: {error}")
                    observation = f"**Observation:** Error occurred:\n{error}"
                    self.current_turn_attempts.append(observation)
                    # Try again with error feedback
                    continue
                else:
                    # Success!
                    # Format the observation with both output and logs
                    observation_parts = []
                    if logs:
                        observation_parts.append(f"Logs:\n{logs}")
                    if output is not None:
                        # Use tool's format_for_observation if available
                        formatted_output = self._format_output_for_observation(output, code)
                        observation_parts.append(f"Output: {formatted_output}")

                    observation = f"**Observation:** Code executed successfully:\n" + "\n".join(observation_parts)
                    self.current_turn_attempts.append(observation)

                    # Use the final answer from LocalPythonExecutor if available
                    if is_final_answer:
                        self.answer = self.input.answer = output
                        print(f"Final answer detected: {self.answer}")

                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error,
                                                                                  self.current_turn_attempts))
                        # Return AgentResponse with final answer flag
                        # raw_response = LLM output (thought + code), answer = final result
                        return AgentResponse(
                            raw_response=response,  # LLM 原始输出 (thought + code)
                            answer=output,          # final_answer 的参数
                            is_final_answer=True,
                            score=1.0,
                            terminated=True,
                            truncated=False,
                            info={'final_answer_detected': True}
                        )

                    # Otherwise check if this looks like a final answer
                    result_text = logs if logs else str(output)
                    if self.is_final_answer(result_text):
                        self.answer = self.input.answer = result_text
                        print(f"Final answer: {self.answer}")

                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error,
                                                                                  self.current_turn_attempts))
                        # Return AgentResponse with final answer flag
                        return AgentResponse(
                            raw_response=result_text,
                            answer=result_text,
                            is_final_answer=True,
                            score=1.0,
                            terminated=True,
                            truncated=False,
                            info={'final_answer_heuristic': True}
                        )

                    # If we have a good result, we can return it
                    if iteration == self.max_iterations - 1:
                        self.answer = self.input.answer = result_text

                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error,
                                                                                  self.current_turn_attempts))
                        # Return AgentResponse for final iteration
                        return AgentResponse(
                            raw_response=self.answer,
                            answer=self.answer,
                            score=0.8,
                            terminated=False,
                            is_final_answer=False,
                            truncated=True,
                            info={'max_iterations_reached': True}
                        )

                    # Continue for more iterations if needed
                    error = ""


            except FinalAnswerException as e:
                # 特殊处理 FinalAnswerException
                final_answer = e.answer
                self.answer = self.input.answer = final_answer
                print(f"Final answer exception detected: {final_answer}")

                self._append_history(
                    self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                # 返回 AgentResponse并标记为终止
                # raw_response = LLM output (thought + code), answer = final result
                return AgentResponse(
                    raw_response=response,      # LLM 原始输出 (thought + code)
                    answer=final_answer,        # final_answer 的参数
                    is_final_answer=True,
                    score=1.0,
                    terminated=True,
                    truncated=False,
                    info={'final_answer_exception': True}
                )
            except Exception as e:
                error = str(e)
                logger.error(f"Execution error: {error}")
                observation = f"**Observation:** Execution failed:\n{error}"
                self.current_turn_attempts.append(observation)
                continue

        # If we've exhausted all iterations, return the last response
        self.answer = self.input.answer = response
        # Return AgentResponse for exhausted iterations
        self._append_history(self.construct_current_turn_messages(query,tools,self.task,error,self.current_turn_attempts))
        return AgentResponse(
            raw_response=self.answer,
            answer=self.answer,
            score=0.3,
            terminated=False,
            is_final_answer=False,
            truncated=True,
            info={'all_iterations_failed': True}
        )

    def extract_code_blocks(self, text):
        """Extract Python code blocks from text, supporting <end_code> format"""
        code_blocks = []

        # Simple pattern: look for code blocks ending with <end_code>
        if '<end_code>' in text:
            # Find code blocks that end with <end_code>
            end_code_pattern = r'```(?:python|py)?\s*\n(.*?)<end_code>'
            matches = re.findall(end_code_pattern, text, re.DOTALL)
            for match in matches:
                cleaned = match.strip()
                # Remove trailing ``` if present
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3].strip()
                if cleaned:
                    code_blocks.append(cleaned)

        return code_blocks

    def is_final_answer(self, output):
        """Check if the output looks like a final answer"""
        # Only use explicit final answer indicators, not general numeric output
        final_indicators = [
            "final answer:",
            "final result:",
            "final solution:",
            "the answer is:",
            "result is:",
            "solution is:"
        ]

        output_lower = output.lower()
        for indicator in final_indicators:
            if indicator in output_lower:
                return True

        # Remove the overly broad numeric check that was causing false positives
        # Only rely on explicit final_answer() function calls detected by LocalPythonExecutor

        return False

    async def execute_stream(self):
        """流式执行方法 - 支持真正的流式输出，包括 Thought/Code/Observation 事件"""
        from minion.main.action_step import StreamChunk

        # Determine the query to use
        if self.task:
            query = self.task.get("instruction", "") or self.task.get("task_description", "")
        else:
            query = self.input.query

        self.current_turn_attempts = []

        error = ""
        previous_turns_history = self._get_history()
        tools = _deduplicate_tools(self.brain.tools + self.input.tools)

        for iteration in range(self.max_iterations):
            # Emit step start event
            yield StreamChunk(
                content=f"Step {iteration + 1}/{self.max_iterations}",
                chunk_type="step_start",
                metadata={"iteration": iteration, "max_iterations": self.max_iterations}
            )

            # Construct messages for this iteration
            messages = self.construct_messages_with_history(query, tools, self.task, error, previous_turns_history)

            # Get LLM response with streaming
            node = LmpActionNode(llm=self.brain.llm)
            tools = _deduplicate_tools((self.input.tools or []) + (self.brain.tools or []))
            stop_sequences = ["<end_code>"]

            try:
                # Stream LLM response
                response = ""
                stream_generator = await node.execute(messages, tools=tools, stop=stop_sequences, stream=True)

                async for chunk in stream_generator:
                    if hasattr(chunk, 'content'):
                        chunk_content = chunk.content
                        # 获取原始 chunk 的 usage（如果有）
                        chunk_usage = getattr(chunk, 'usage', None)
                    else:
                        chunk_content = str(chunk)
                        chunk_usage = None

                    response += chunk_content
                    # Yield text chunk as it comes in
                    # partial=True 表示这是增量内容（不是累积的）
                    yield StreamChunk(
                        content=chunk_content,
                        chunk_type="thinking",
                        metadata={"iteration": iteration},
                        partial=True,  # 增量内容，不是累积的
                        usage=chunk_usage  # 传递 usage 信息
                    )

                if response and not response.strip().endswith("<end_code>"):
                    response += "<end_code>"

            except FinalAnswerException as e:
                final_answer = e.answer
                self.answer = self.input.answer = final_answer

                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                # raw_response = LLM output so far, answer = final result
                yield AgentResponse(
                    raw_response=response if response else str(final_answer),  # LLM 输出（可能是部分）
                    answer=final_answer,        # final_answer 的参数
                    is_final_answer=True,
                    score=1.0,
                    terminated=True,
                    truncated=False,
                    info={'final_answer_exception': True}
                )
                return

            # Extract and execute code
            code_blocks = self.extract_code_blocks(response)
            self.current_turn_attempts.append(f"**Assistant Response {iteration + 1}:** {response}")

            if not code_blocks:
                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                self.answer = self.input.answer = response
                yield AgentResponse(
                    raw_response=response,
                    answer=self.answer,
                    score=0.5,
                    terminated=True,
                    is_final_answer=True,
                    truncated=False,
                    info={'no_code_found': True}
                )
                return

            # Execute the first code block
            code = code_blocks[0]

            # Emit code_start event
            yield StreamChunk(
                content=code,
                chunk_type="code_start",
                metadata={"iteration": iteration, "code_preview": code[:100] + "..." if len(code) > 100 else code}
            )

            # Execute the code using python_env
            try:
                if hasattr(self.python_env, '__call__') and asyncio.iscoroutinefunction(self.python_env.__call__):
                    output, logs, is_final_answer = await self.python_env(code)
                else:
                    output, logs, is_final_answer = self.python_env(code)

                if isinstance(output, Exception):
                    error = str(output)
                    # Emit code_result with error
                    yield StreamChunk(
                        content=error,
                        chunk_type="code_result",
                        metadata={"success": False, "error": error, "iteration": iteration}
                    )
                    observation = f"**Observation:** Error occurred:\n{error}"
                    self.current_turn_attempts.append(observation)
                    continue
                else:
                    # Format observation
                    observation_parts = []
                    if logs:
                        observation_parts.append(f"Logs:\n{logs}")
                    if output is not None:
                        formatted_output = self._format_output_for_observation(output, code)
                        observation_parts.append(f"Output: {formatted_output}")

                    observation_content = "\n".join(observation_parts)

                    # Emit code_result with success
                    yield StreamChunk(
                        content=observation_content,
                        chunk_type="code_result",
                        metadata={"success": True, "iteration": iteration, "has_logs": bool(logs)}
                    )

                    observation = f"**Observation:** Code executed successfully:\n{observation_content}"
                    self.current_turn_attempts.append(observation)

                    if is_final_answer:
                        self.answer = self.input.answer = output
                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                        # raw_response = LLM output (thought + code), answer = final result
                        yield AgentResponse(
                            raw_response=response,  # LLM 原始输出 (thought + code)
                            answer=output,          # final_answer 的参数
                            is_final_answer=True,
                            score=1.0,
                            terminated=True,
                            truncated=False,
                            info={'final_answer_detected': True}
                        )
                        return

                    result_text = logs if logs else str(output)
                    if self.is_final_answer(result_text):
                        self.answer = self.input.answer = result_text
                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                        # raw_response = LLM output (thought + code), answer = heuristic result
                        yield AgentResponse(
                            raw_response=response,  # LLM 原始输出 (thought + code)
                            answer=result_text,     # 启发式检测的答案
                            is_final_answer=True,
                            score=1.0,
                            terminated=True,
                            truncated=False,
                            info={'final_answer_heuristic': True}
                        )
                        return

                    if iteration == self.max_iterations - 1:
                        self.answer = self.input.answer = result_text
                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                        yield AgentResponse(
                            raw_response=self.answer,
                            answer=self.answer,
                            score=0.8,
                            terminated=False,
                            is_final_answer=False,
                            truncated=True,
                            info={'max_iterations_reached': True}
                        )
                        return

                    error = ""

            except FinalAnswerException as e:
                final_answer = e.answer
                self.answer = self.input.answer = final_answer
                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                # raw_response = LLM output (thought + code), answer = final result
                yield AgentResponse(
                    raw_response=response,      # LLM 原始输出 (thought + code)
                    answer=final_answer,        # final_answer 的参数
                    is_final_answer=True,
                    score=1.0,
                    terminated=True,
                    truncated=False,
                    info={'final_answer_exception': True}
                )
                return
            except Exception as e:
                error = str(e)
                logger.error(f"Execution error: {error}")
                # Emit code_result with error
                yield StreamChunk(
                    content=error,
                    chunk_type="code_result",
                    metadata={"success": False, "error": error, "iteration": iteration}
                )
                observation = f"**Observation:** Execution failed:\n{error}"
                self.current_turn_attempts.append(observation)
                continue

        # If we've exhausted all iterations
        self.answer = self.input.answer = response
        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
        yield AgentResponse(
            raw_response=self.answer,
            answer=self.answer,
            score=0.3,
            terminated=False,
            is_final_answer=False,
            truncated=True,
            info={'all_iterations_failed': True}
        )
