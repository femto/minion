"""
CodeMinion: A "think in code" agent that uses Python code for reasoning and actions.

This agent extends the BaseAgent to provide:
- Python code-based reasoning instead of JSON
- Self-reflection capabilities with the "think" tool
- ReAct (Reason-Act-Observe) cycles
- Safe code execution with sandboxing
- Memory integration for learning
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import re
import traceback
import logging
import uuid
from datetime import datetime

from .base_agent import BaseAgent
from minion.types.agent_response import AgentResponse
from ..tools.agent_state_aware_tool import AgentStateAwareTool
from ..tools.base_tool import BaseTool
from ..main.input import Input
from ..main.local_python_executor import LocalPythonExecutor
from ..main.async_python_executor import AsyncPythonExecutor
from ..tools.default_tools import FinalAnswerTool

logger = logging.getLogger(__name__)

class ThinkingEngine:
    """Engine for managing different thinking strategies."""
    
    def __init__(self, agent: 'CodeAgent'):
        self.agent = agent
        self.reflection_triggers = {
            'error_count': 3,  # Trigger reflection after 3 errors
            'step_count': 5,   # Trigger reflection every 5 steps
            'low_confidence': 0.3,  # Trigger reflection when confidence < 0.3
        }
    
    def should_reflect(self, state: Dict[str, Any]) -> bool:
        """Determine if the agent should reflect based on current state."""
        error_count = state.get('error_count', 0)
        step_count = state.get('step_count', 0)
        last_confidence = state.get('last_confidence', 1.0)
        
        # Check triggers
        if error_count >= self.reflection_triggers['error_count']:
            return True
        if step_count > 0 and step_count % self.reflection_triggers['step_count'] == 0:
            return True
        if last_confidence < self.reflection_triggers['low_confidence']:
            return True
        
        return False
    
    async def generate_reflection(self, state: Dict[str, Any]) -> str:
        """Generate a reflection prompt based on current state."""
        history = state.get('history', [])
        task = state.get('task', '')
        error_count = state.get('error_count', 0)
        
        reflection_prompt = f"""
Let me think about the current situation:

**Task**: {task}

**Progress so far**: {len(history)} steps completed
**Errors encountered**: {error_count}

**Recent actions**:
{self._format_recent_history(history[-3:] if history else [])}

**Reflection questions**:
1. Am I making progress toward the goal?
2. Are there any patterns in my errors?
3. Should I try a different approach?
4. What have I learned so far?
5. What should I do next?

Let me analyze this step by step using code...
"""
        return reflection_prompt
    
    def _format_recent_history(self, history: List[Any]) -> str:
        """Format recent history for reflection."""
        if not history:
            return "No recent actions"
        
        formatted = []
        for i, step in enumerate(history[-3:], 1):
            if isinstance(step, tuple) and len(step) > 0:
                action = step[0]
                formatted.append(f"{i}. {action}")
        
        return '\n'.join(formatted) if formatted else "No recent actions"


@dataclass
class CodeAgent(BaseAgent):
    """
    A "think in code" agent that uses Python code for reasoning and actions.
    
    This agent extends BaseAgent with:
    - Code-based reasoning instead of JSON
    - Self-reflection capabilities
    - ReAct (Reason-Act-Observe) cycles
    - Safe code execution
    - Async tool support
    - Optional state management and conversation tracking
    """
    
    name: str = "code_agent"
    thinking_engine: Optional[ThinkingEngine] = None
    python_executor: Optional[Union[LocalPythonExecutor, AsyncPythonExecutor]] = None
    enable_reflection: bool = True
    max_code_length: int = 2000
    use_async_executor: bool = True  # Parameter to control async support
    
    # State tracking and conversation history (optional)
    enable_state_tracking: bool = False  # Whether to enable persistent state tracking functionality
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    persistent_state: Dict[str, Any] = field(default_factory=dict)
    auto_save_state: bool = True
    conversation_context_limit: int = 10  # Limit conversation history for context
    
    def __post_init__(self):
        """Initialize the CodeAgent with thinking capabilities and optional state tracking."""
        super().__post_init__()
        
        # Initialize thinking engine
        self.thinking_engine = ThinkingEngine(self)
        
        # Initialize code executor based on use_async_executor flag
        if self.use_async_executor:
            self.python_executor = self.brain.python_env = AsyncPythonExecutor(
                additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn", "requests", "json", "csv", "asyncio"],
                max_print_outputs_length=50000,
                additional_functions={}
            )
        else:
            self.python_executor = self.brain.python_env = LocalPythonExecutor(
                additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn", "requests", "json", "csv"],
                max_print_outputs_length=50000,
                additional_functions={}
            )
        
        # Set brain.python_env to the executor
        if self.brain:
            self.brain.python_env = self.python_executor
        
        # Add the think tool and final answer tool
        self.add_tool(FinalAnswerTool())
        
        # Send tools to the python executor
        self._update_executor_tools()
        
        # Initialize state tracking if enabled
        if self.enable_state_tracking:
            self._initialize_state()
    
    def _initialize_state(self):
        """Initialize persistent state if state tracking is enabled."""
        if not self.persistent_state:
            self.persistent_state = {
                'initialized_at': str(uuid.uuid4()),
                'conversation_count': 0,
                'variables': {},
                'memory_store': {},
                'learned_patterns': []
            }
        logger.info("State tracking initialized")

    async def execute_step(self, state: Dict[str, Any], **kwargs) -> AgentResponse:
        """
        Execute a step with enhanced code-based reasoning.
        
        This method overrides the parent's execute_step to add:
        - Code-based reasoning
        - Self-reflection triggers
        - Enhanced error handling
        
        Args:
            state: State dictionary containing input and other data
            **kwargs: Additional arguments
        
        Returns:
            AgentResponse: Structured response instead of 5-tuple
        """
        # Extract input_data from state
        input_data = state.get("input")
        if not input_data:
            raise ValueError("No input found in state")
        
        # Check if we should reflect first
        if self.enable_reflection and self.thinking_engine and self.thinking_engine.should_reflect(state):
            await self._perform_reflection(state)
        
        # Enhance the input with code-thinking instructions
        enhanced_input = self._enhance_input_for_code_thinking(input_data)
        
        # Execute the step
        try:
            if not self.brain:
                raise ValueError("Brain is not initialized")
            
            # Call brain.step with proper state format - brain expects state dict with 'input' key
            brain_state = state.copy()
            brain_state["input"] = enhanced_input
            result = await self.brain.step(brain_state, **kwargs)
            
            # Convert result to AgentResponse
            agent_response = AgentResponse.from_tuple(result)
            
            # Check if this is already a processed result (from CodeMinion with final_answer detection)
            # If brain already handled code execution and final_answer detection, don't re-process
            if hasattr(result, '__len__') and len(result) >= 5:
                response, score, terminated, truncated, info = result
                
                # Check if final_answer was already detected by the underlying system
                if isinstance(info, dict) and (
                    info.get('is_final_answer', False) or 
                    'final_answer' in info or
                    terminated
                ):
                    # Already processed by CodeMinion, use as-is
                    return agent_response
            
            return agent_response
            
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            error_msg = f"Step execution failed: {e}"
            return AgentResponse(
                raw_response=error_msg,
                score=0.0,
                terminated=False,
                truncated=False,
                error=str(e)
            )
    
    def _enhance_input_for_code_thinking(self, input_data: Input) -> Input:
        """Enhance input with code-thinking instructions based on smolagents approach."""
        
        # 获取可用的工具列表
        available_tools = []
        if self.tools:
            for tool in self.tools:
                if hasattr(tool, 'name') and hasattr(tool, 'description'):
                    tool_desc = f"- {tool.name}: {tool.description}"
                    # Add async indicator if using async executor
                    if self.use_async_executor and hasattr(tool, 'forward'):
                        import asyncio
                        if asyncio.iscoroutinefunction(tool.forward):
                            tool_desc += " (async)"
                    available_tools.append(tool_desc)
        
        tools_description = "\n".join(available_tools) if available_tools else "- final_answer: Provide the final answer to complete the task"
        
        # Add async-specific instructions if using async executor
        async_instructions = ""
        if self.use_async_executor:
            async_instructions = """
**Async Tool Support:**
- You can use async tools with `await` syntax: `result = await async_tool_name(args)`
- For concurrent execution, use `asyncio.gather()`: `results = await asyncio.gather(task1, task2, task3)`
- Regular (sync) tools can be used normally without `await`
- The `asyncio` module is available for advanced async operations
"""
        
        enhanced_query = f"""You are an expert assistant who can solve any task using code blobs. You will be given a task to solve as best you can.
To do so, you have been given access to a list of tools: these tools are basically Python functions which you can call with code.
To solve the task, you must plan forward to proceed in a series of steps, in a cycle of 'Thought:', 'Code:', and 'Observation:' sequences.

At each step, in the 'Thought:' sequence, you should first explain your reasoning towards solving the task and the tools that you want to use.
Then in the 'Code:' sequence, you should write the code in simple Python. The code sequence must end with '<end_code>' sequence.
During each intermediate step, you can use 'print()' to save whatever important information you will then need.
These print outputs will then appear in the 'Observation:' field, which will be available as input for the next step.
In the end you have to return a final answer using the `final_answer` tool.

**Available Tools:**
{tools_description}
{async_instructions}
**Your Task:**
{input_data.query}

**Rules you must follow:**
1. Always provide a 'Thought:' sequence, and a 'Code:\\n```py' sequence ending with '```<end_code>' sequence, else you will fail.
2. Use only variables that you have defined!
3. Always use the right arguments for the tools. DO NOT pass the arguments as a dict, but use the arguments directly.
4. Take care to not chain too many sequential tool calls in the same code block, especially when the output format is unpredictable. Use print() to output results for use in the next block.
5. Call a tool only when needed, and never re-do a tool call that you previously did with the exact same parameters.
6. Don't name any new variable with the same name as a tool: for instance don't name a variable 'final_answer'.
7. Never create any notional variables in your code, as having these in your logs will derail you from the true variables.
8. You can use imports in your code, but only from standard Python libraries (math, datetime, json, etc.) and common data science libraries (numpy, pandas, matplotlib, seaborn).
9. The state persists between code executions: so if in one step you've created variables or imported modules, these will all persist.
10. Don't give up! You're in charge of solving the task, not providing directions to solve it.
11. **CRUCIAL**: Make sure your code is well-defined and complete. Include all necessary imports, define all variables, and ensure the code can run independently.
12. **IMPORTANT**: When you have the final answer, call `final_answer(your_result)` to complete the task.
13. **ASYNC TOOLS**: For async tools, use `await` syntax and consider using `asyncio.gather()` for concurrent execution.

**Example Pattern:**
Task: "What is the result of the following operation: 5 + 3 + 1294.678?"

Thought: I will use python code to compute the result of the operation and then return the final answer using the `final_answer` tool.
Code:
```py
result = 5 + 3 + 1294.678
print(f"The calculation result is: {{result}}")
final_answer(result)
```<end_code>

**Remember:**
- Always start with "Thought:" to explain your reasoning
- Write complete, well-defined code in "Code:" blocks
- End code blocks with ```<end_code>
- Use print() to output intermediate results
- Call final_answer() when you have the solution
- Use `await` for async tools and `asyncio.gather()` for concurrent execution

Now Begin!
"""
        
        # Create a new Input with enhanced query
        enhanced_input = Input(
            query=enhanced_query,
            route=getattr(input_data, 'route', None) or 'code',
            check=getattr(input_data, 'check', False),
            dataset=getattr(input_data, 'dataset', None),
            metadata=getattr(input_data, 'metadata', {})
        )
        
        return enhanced_input
    
    # step方法现在由BaseAgent处理，无需覆盖
    # BaseAgent.step已经返回AgentResponse，并且支持tuple解包向后兼容性
    
    async def _process_code_response(self, response: str, state: Dict[str, Any]) -> str:
        """Process and execute any code found in the response, supporting Thought-Code-Observation cycle."""
        # Extract Python code blocks from the response
        code_blocks = self._extract_code_blocks(response)
        
        if not code_blocks:
            # No code blocks found, return original response
            return response
        
        processed_parts = []
        processed_parts.append(response)
        
        # Process all code blocks, but check for final answer after each
        for i, code in enumerate(code_blocks):
            if len(code) > self.max_code_length:
                observation = f"\n**Observation:** Code block {i+1} too long to execute safely (max {self.max_code_length} characters)."
                processed_parts.append(observation)
                continue
            
            if not self.python_executor:
                observation = f"\n**Observation:** Python executor not available for code block {i+1}."
                processed_parts.append(observation)
                continue
                
            try:
                # Use AsyncPythonExecutor or LocalPythonExecutor to execute code
                if self.use_async_executor:
                    output, logs, is_final_answer = await self.python_executor(code)
                else:
                    output, logs, is_final_answer = self.python_executor(code)
                
                # Build observation feedback
                observation_parts = [f"\n**Observation:** Code block {i+1} executed successfully."]
                
                if logs:
                    # Clean and format log output
                    cleaned_logs = logs.strip()
                    if cleaned_logs:
                        observation_parts.append(f"```\n{cleaned_logs}\n```")
                
                if output is not None and not is_final_answer:
                    observation_parts.append(f"Return value: {output}")
                
                processed_parts.extend(observation_parts)
                
                # Store result in state for future reference
                state[f'code_result_{i}'] = output
                state[f'code_logs_{i}'] = logs
                state[f'is_final_answer_{i}'] = is_final_answer
                
                # If this is the final answer, set global flag and return immediately
                if is_final_answer:
                    state['is_final_answer'] = True
                    state['final_answer_value'] = output
                    final_observation = f"\n**Final Answer Found:** {output}"
                    final_observation += f"\n**Task Status:** COMPLETED"
                    processed_parts.append(final_observation)
                    return '\n'.join(processed_parts)
                    
            except Exception as e:
                # Provide detailed error observation
                error_observation = f"\n**Observation:** Code block {i+1} execution failed."
                error_observation += f"\n**Error:** {str(e)}"
                
                # If there is traceback information, provide simplified version
                if hasattr(e, '__traceback__'):
                    try:
                        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
                        # Only take the last few lines of key information
                        key_lines = [line.strip() for line in tb_lines[-3:] if line.strip()]
                        if key_lines:
                            error_observation += f"\n**Traceback:** {' | '.join(key_lines)}"
                    except:
                        pass
                
                processed_parts.append(error_observation)
                
                # Increment error count
                state['error_count'] = state.get('error_count', 0) + 1
                
                # Provide error recovery suggestions
                if state['error_count'] <= 2:
                    recovery_suggestion = f"\n**Suggestion:** Review the error and try a different approach in the next step."
                    processed_parts.append(recovery_suggestion)
        
        return '\n'.join(processed_parts)
    
    def _contains_code_blocks(self, text: str) -> bool:
        """Check if text contains code blocks that need processing."""
        if not isinstance(text, str):
            return False
        return '<end_code>' in text and '```' in text
    
    def _extract_code_blocks(self, text: str) -> List[str]:
        """Extract Python code blocks from text, supporting both standard and <end_code> formats."""
        # Type safety check - only process strings
        if not isinstance(text, str):
            logger.warning(f"_extract_code_blocks received non-string input: {type(text)}")
            return []
        
        code_blocks = []
        
        # Pattern 2: Code blocks ending with <end_code>
        end_code_pattern = r'```(?:python|py)?\s*\n(.*?)\n```<end_code>'
        matches = re.findall(end_code_pattern, text, re.DOTALL)
        for match in matches:
            cleaned = match.strip()
            if cleaned:
                code_blocks.append(cleaned)
        
        # Pattern 3: Code blocks with just <end_code> at the end (no closing ```)
        loose_end_code_pattern = r'```(?:python|py)?\s*\n(.*?)<end_code>'
        matches = re.findall(loose_end_code_pattern, text, re.DOTALL)
        for match in matches:
            cleaned = match.strip()
            if cleaned:
                code_blocks.append(cleaned)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_blocks = []
        for block in code_blocks:
            if block not in seen:
                seen.add(block)
                unique_blocks.append(block)
        
        return unique_blocks
    
    async def _perform_reflection(self, state: Dict[str, Any]) -> None:
        """Perform self-reflection using the think tool."""
        if not self.thinking_engine:
            return
        
        reflection_prompt = await self.thinking_engine.generate_reflection(state)
        
        # Use the think tool
        think_tool = self.get_tool('think')
        if think_tool:
            think_tool.forward(reflection_prompt)
            
            # Add reflection to memory if available
            if hasattr(self, 'add_memory'):
                self.add_memory(
                    f"Reflection: {reflection_prompt}",
                    metadata={'type': 'reflection', 'timestamp': datetime.now().isoformat()}
                )
    
    def update_state(self, state: Dict[str, Any], result: Any) -> Dict[str, Any]:
        """Update state with CodeMinion-specific information."""
        state = super().update_state(state, result)
        
        # Extract confidence from result if available
        if isinstance(result, tuple) and len(result) >= 2:
            state['last_confidence'] = result[1]  # score/confidence
        
        # Update reflection trigger counters
        if 'error_count' not in state:
            state['error_count'] = 0
        
        # 保存当前状态引用，便于外部访问
        self.state = state
            
        return state
    
    async def solve_problem(self, problem: str, reset: bool = False, **kwargs) -> str:
        """
        Solve a problem using code-based reasoning.
        
        Args:
            problem: The problem to solve
            reset: If True, reset the agent state before execution (when state tracking is enabled)
            **kwargs: Additional parameters
            
        Returns:
            The solution as a string
        """
        input_obj = Input(query=problem, route='code')
        result = await self.run_async(input_obj, reset=reset, **kwargs)
        return str(result)
    
    async def analyze_data(self, data: Any, question: str, reset: bool = False, **kwargs) -> str:
        """
        Analyze data using code-based reasoning.
        
        Args:
            data: The data to analyze
            question: The question to answer about the data
            reset: If True, reset the agent state before execution (when state tracking is enabled)
            **kwargs: Additional parameters
            
        Returns:
            The analysis result as a string
        """
        analysis_query = f"""
Analyze the following data and answer the question: {question}

Data: {data}

Use Python code to:
1. Understand the data structure
2. Perform necessary calculations
3. Generate insights
4. Answer the question
"""
        
        input_obj = Input(query=analysis_query, route='python')
        result = await self.run_async(input_obj, reset=reset, **kwargs)
        return str(result)
    
    def is_done(self, result: Any, state: Dict[str, Any]) -> bool:
        """
        Check if the task is completed by detecting the is_final_answer flag.
        """
        # First call the parent's is_done method
        parent_done = super().is_done(result, state)
        if parent_done:
            return True
        
        # Check if there is a final_answer flag in the state
        if state.get('is_final_answer', False):
            return True
        
        # For AgentResponse, use its built-in check method
        if hasattr(result, 'is_done'):
            return result.is_done()
        
        # Check if there is a termination flag in the result (5-tuple format)
        if isinstance(result, tuple) and len(result) >= 3:
            terminated = result[2]
            if terminated:
                return True
        
        return False
    
    def finalize(self, result: Any, state: Dict[str, Any]) -> Any:
        """
        Organize the final result, specially handling the final_answer case.
        """
        # Check if there is a final_answer_value in the state
        if 'final_answer_value' in state:
            return state['final_answer_value']
        
        # For AgentResponse, prioritize using its final_answer
        if hasattr(result, 'final_answer') and result.final_answer is not None:
            return result.final_answer
        
        # Call parent's finalize method
        return super().finalize(result, state)

    def _update_executor_tools(self):
        """Update the Python executor with current tools."""
        if self.python_executor and self.tools:
            if self.use_async_executor:
                # For AsyncPythonExecutor, pass tools directly - it will handle async/sync conversion
                tool_dict = {}
                for tool in self.tools:
                    if hasattr(tool, 'name'):
                        tool_dict[tool.name] = tool
                self.python_executor.send_tools(tool_dict)
            else:
                #same logic
                tool_dict = {}
                for tool in self.tools:
                    if hasattr(tool, 'name'):
                        tool_dict[tool.name] = tool
                self.python_executor.send_tools(tool_dict)
    
    def add_tool(self, tool: BaseTool):
        """Add a tool and update the executor."""
        super().add_tool(tool)
        # Update executor tools whenever a new tool is added
        if hasattr(self, 'python_executor'):
            self._update_executor_tools()
            
    # State management methods from StateCodeAgent
    
    async def run_async(self, task: Optional[Union[str, Input]] = None,
                       state: Optional[Dict[str, Any]] = None, 
                       max_steps: Optional[int] = None,
                       reset: bool = False,
                       **kwargs) -> Any:
        """
        Run the agent with enhanced state management and optional reset capability.
        
        Args:
            task: Task description or Input object
            state: Existing state for execution
            max_steps: Maximum steps to execute
            reset: If True, reset the agent state before execution (when state tracking is enabled)
            **kwargs: Additional parameters
            
        Returns:
            Agent response with conversation context when state tracking is enabled
        """
        # Skip state management if state tracking is disabled
        if not self.enable_state_tracking:
            # Pass parameters with named arguments to avoid conflicts
            return await super().run_async(task, state=state, max_steps=max_steps, **kwargs)
        
        # Handle reset functionality
        if reset:
            self.reset_state()
            logger.info("Agent state has been reset")
        
        # Convert string task to Input if needed
        input_data = task
        if isinstance(task, str):
            input_data = Input(query=task)
        
        # Update conversation context in input if we have state tracking enabled
        if input_data and isinstance(input_data, Input):
            enhanced_input = self._add_conversation_context(input_data)
        else:
            enhanced_input = input_data
        
        # Prepare state with persistent information
        if state is None:
            state = {}
        state.update(self.persistent_state)
        state['conversation_history'] = self.get_recent_history()
        kwargs['state'] = state
        
        # Execute the step with enhanced input and state
        try:
            # Remove state from kwargs since we're passing it directly to avoid duplicate arg error
            kwargs_copy = kwargs.copy()
            if 'state' in kwargs_copy:
                del kwargs_copy['state']
            result = await super().run_async(enhanced_input, state=state, max_steps=max_steps, **kwargs_copy)
            
            # Record this interaction
            if input_data and isinstance(input_data, Input):
                await self._record_interaction(input_data, result, reset)
            
            # Auto-save state if enabled
            if self.auto_save_state:
                self._save_persistent_state(state)
            
            return result
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            # Still record the failed interaction
            if input_data and isinstance(input_data, Input):
                await self._record_interaction(input_data, f"Error: {e}", reset)
            raise
    
    def reset_state(self) -> None:
        """
        Reset agent state.
        
        This clears:
        - Conversation history
        - Working variables
        - Temporary memory
        But preserves:
        - Learned patterns
        - Core configuration
        """
        if not self.enable_state_tracking:
            logger.warning("State tracking is disabled, reset_state has no effect")
            return
            
        # Clear conversation history
        self.conversation_history = []
        
        # Reset session ID
        self.session_id = str(uuid.uuid4())
        
        # Reset working state but preserve learned patterns
        learned_patterns = self.persistent_state.get('learned_patterns', [])
        self.persistent_state = {
            'initialized_at': str(uuid.uuid4()),
            'conversation_count': 0,
            'variables': {},
            'memory_store': {},
            'learned_patterns': learned_patterns  # Preserve learned patterns
        }
        
        # Reset code executor state if available
        if self.python_executor:
            if hasattr(self.python_executor, 'reset'):
                self.python_executor.reset()
        
        logger.info("Agent state reset completed")
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current agent state including conversation and persistent state.
        
        Returns:
            Complete state dictionary or empty dict if state tracking is disabled
        """
        if not self.enable_state_tracking:
            return {}
            
        return {
            'conversation_history': self.conversation_history,
            'persistent_state': self.persistent_state,
            'session_id': self.session_id,
            'conversation_count': len(self.conversation_history) // 2,  # Approximate turns
        }
    
    def load_state(self, state: Dict[str, Any]) -> None:
        """
        Load agent state from dictionary.
        
        Args:
            state: State dictionary to load
        """
        if not self.enable_state_tracking:
            logger.warning("State tracking is disabled, load_state has no effect")
            return
            
        if 'conversation_history' in state:
            self.conversation_history = state['conversation_history']
        
        if 'persistent_state' in state:
            self.persistent_state = state['persistent_state']
        
        if 'session_id' in state:
            self.session_id = state['session_id']
        
        logger.info(f"Agent state loaded with {len(self.conversation_history)} conversation entries")
    
    def _add_conversation_context(self, input_data: Input) -> Input:
        """Add conversation context to input for better continuity."""
        if not self.enable_state_tracking or not self.conversation_history:
            return input_data
        
        # Get recent conversation for context
        recent_history = self.get_recent_history(limit=self.conversation_context_limit)
        
        if not recent_history:
            return input_data
        
        # Format conversation context
        context_lines = []
        for entry in recent_history:
            role = entry['role'].upper()
            content = str(entry['content'])[:200]  # Limit content length
            context_lines.append(f"{role}: {content}")
        
        conversation_context = "\n".join(context_lines)
        
        # Enhanced query with conversation context
        enhanced_query = f"""**Conversation Context:**
{conversation_context}

**Current Request:**
{input_data.query}

**Instructions:**
- Consider the conversation context when responding
- Maintain consistency with previous interactions
- Use any relevant information from the conversation history
- If variables or results from previous steps are relevant, reference them in your code
"""
        
        return Input(
            query=enhanced_query,
            route=getattr(input_data, 'route', None) or 'code',
            check=getattr(input_data, 'check', False),
            dataset=getattr(input_data, 'dataset', None),
            metadata=getattr(input_data, 'metadata', {})
        )
    
    async def _record_interaction(self, input_data: Input, result: Any, was_reset: bool) -> None:
        """Record the interaction in conversation history."""
        if not self.enable_state_tracking:
            return
            
        # Record user input
        self.add_to_history("user", input_data.query)
        
        # Record system response
        if isinstance(result, AgentResponse):
            response_content = result.raw_response
        else:
            response_content = str(result)
        
        self.add_to_history("assistant", response_content)
        
        # Add reset indicator if state was reset
        if was_reset:
            self.add_to_history("system", "State was reset before this interaction")
        
        # Update conversation count in persistent state
        self.persistent_state['conversation_count'] = len(self.conversation_history) // 2
    
    def _save_persistent_state(self, current_state: Dict[str, Any]) -> None:
        """Save relevant information to persistent state."""
        if not self.enable_state_tracking:
            return
            
        # Extract variables from execution state
        variables = {}
        for key, value in current_state.items():
            if key.startswith('code_result_'):
                variables[key] = value
        
        if variables:
            self.persistent_state['variables'].update(variables)
        
        # Save any learned patterns or insights
        if 'learned_patterns' in current_state:
            self.persistent_state['learned_patterns'].extend(current_state['learned_patterns'])
    
    def get_recent_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent conversation history."""
        if not self.enable_state_tracking:
            return []
            
        if limit is None:
            return self.conversation_history
        return self.conversation_history[-limit:] if self.conversation_history else []
    
    def clear_history(self) -> None:
        """Clear conversation history while preserving persistent state."""
        if not self.enable_state_tracking:
            logger.warning("State tracking is disabled, clear_history has no effect")
            return
            
        self.conversation_history = []
        self.session_id = str(uuid.uuid4())
        logger.info("Conversation history cleared")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get complete conversation history."""
        if not self.enable_state_tracking:
            return []
            
        return self.conversation_history
    
    def add_to_history(self, role: str, content: Any) -> None:
        """
        Add entry to conversation history.
        
        Args:
            role: Role (user, assistant, system)
            content: Content of the message
        """
        if not self.enable_state_tracking:
            return
            
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": str(uuid.uuid4())[:8]  # Short timestamp
        })
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get conversation and usage statistics."""
        if not self.enable_state_tracking:
            return {
                'state_tracking': 'disabled'
            }
            
        return {
            'total_conversations': self.persistent_state.get('conversation_count', 0),
            'current_session_messages': len(self.conversation_history),
            'session_id': self.session_id,
            'variables_stored': len(self.persistent_state.get('variables', {})),
            'patterns_learned': len(self.persistent_state.get('learned_patterns', [])),
            'auto_save_enabled': self.auto_save_state
        }