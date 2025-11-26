"""
CodeMinion: A "think in code" agent that uses Python code for reasoning and actions.

This agent extends the BaseAgent to provide:
- Python code-based reasoning instead of JSON
- Self-reflection capabilities with the "think" tool
- ReAct (Reason-Act-Observe) cycles
- Safe code execution with sandboxing
- Memory integration for learning
"""
from copy import copy
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import re
import traceback
import logging
import uuid
from datetime import datetime

from .base_agent import BaseAgent
from minion.types.agent_response import AgentResponse
from minion.types.agent_state import AgentState, CodeAgentState
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
    
    def should_reflect(self, state: CodeAgentState) -> bool:
        """Determine if the agent should reflect based on current state."""
        # Check triggers
        if state.error_count >= self.reflection_triggers['error_count']:
            return True
        if state.step_count > 0 and state.step_count % self.reflection_triggers['step_count'] == 0:
            return True
        if state.last_confidence < self.reflection_triggers['low_confidence']:
            return True
        
        return False
    
    async def generate_reflection(self, state: CodeAgentState) -> str:
        """Generate a reflection prompt based on current state."""
        history = state.history
        task = state.task or ''
        error_count = state.error_count
        
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
    
    # Internal state management
    state: CodeAgentState = field(default_factory=CodeAgentState, init=False)
    
    def __post_init__(self):
        """Initialize the CodeAgent with thinking capabilities and optional state tracking."""
        super().__post_init__()
        
        # Set agent reference in state if not already set
        if self.state and not self.state.agent:
            self.state.agent = self
        
        # Initialize thinking engine
        self.thinking_engine = ThinkingEngine(self)
        
        # Initialize code executor based on use_async_executor flag (brain is now available)
        if self.use_async_executor:
            self.python_executor = AsyncPythonExecutor(
                additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn", "requests", "json", "csv", "asyncio","os","sys"],
                max_print_outputs_length=50000,
                additional_functions={}
            )
        else:
            self.python_executor = LocalPythonExecutor(
                additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn", "requests", "json", "csv","os","sys"],
                max_print_outputs_length=50000,
                additional_functions={}
            )
        
    @property
    def history(self) -> List[Any]:
        """Get the history from internal state."""
        return self.state.history
    
    @history.setter
    def history(self, value: List[Any]):
        """Set the history in internal state."""
        self.state.history = value

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

    async def setup(self):
        if self._is_setup:
            return
        await super().setup()
        self._is_setup = False #since super setting this to True, we immediately set it to False
        
        # Set brain.python_env to the executor after brain is initialized
        if self.brain and self.python_executor:
            self.brain.python_env = self.python_executor

        self.add_tool(FinalAnswerTool())

        # Send tools to the python executor
        self._update_executor_tools()

        # Initialize state tracking if enabled
        if self.enable_state_tracking:
            self._initialize_state()
        self._is_setup = True


    async def execute_step(self, state: CodeAgentState, stream: bool = False, **kwargs) -> AgentResponse:
        """
        Execute a step with enhanced code-based reasoning.
        
        This method overrides the parent's execute_step to add:
        - Code-based reasoning
        - Self-reflection triggers
        - Enhanced error handling
        
        Args:
            state: Strong-typed CodeAgentState
            **kwargs: Additional arguments
        
        Returns:
            AgentResponse: Structured response instead of 5-tuple
        """
        # Use the provided state
        self.state = state
        
        # Extract input_data from internal state
        input_data = self.state.input
        if not input_data:
            raise ValueError("No input found in state")
        
        # Check if we should reflect first
        if self.enable_reflection and self.thinking_engine and self.thinking_engine.should_reflect(self.state):
            await self._perform_reflection()
        
        # Enhance the input with code minion routing
        enhanced_input = self._enhance_input_for_code_thinking(input_data)
        self.state.input = enhanced_input
        
        # Execute the step
        try:
            if not self.brain:
                raise ValueError("Brain is not initialized")
            
            # Get tools list from agent
            tools = self.tools
            
            # 同步state到brain，这样minion可以访问agent的状态
            self.brain.state = self.state
            
            # Call brain.step with enhanced input directly
            result = await self.brain.step(self.state, tools=tools, stream=stream, system_prompt=self.system_prompt, **kwargs)
            
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
            raise e
    
    def _enhance_input_for_code_thinking(self, input_data: Input) -> Input:
        # Create a new Input with enhanced query
        enhanced_input = input_data
        # Ensure route is set to 'code' for code thinking
        if not enhanced_input.route:
            enhanced_input.route = 'code'
        
        return enhanced_input
    
    # step方法现在由BaseAgent处理，无需覆盖
    # BaseAgent.step已经返回AgentResponse，并且支持tuple解包向后兼容性
    
    async def _process_code_response(self, response: str) -> str:
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
                
                # Store result in internal state for future reference
                self.state.add_code_result(i, output, logs, is_final_answer)
                
                # If this is the final answer, set global flag and return immediately
                if is_final_answer:
                    self.state.is_final_answer = True
                    self.state.final_answer_value = output
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
                self.state.error_count += 1
                
                # Provide error recovery suggestions
                if self.state.error_count <= 2:
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
    
    async def _perform_reflection(self) -> None:
        """Perform self-reflection using the think tool."""
        if not self.thinking_engine:
            return
        
        # Use internal state for reflection
        reflection_prompt = await self.thinking_engine.generate_reflection(self.state)
        
        # Update reflection count
        self.state.reflection_count += 1
        self.state.last_reflection_step = self.state.step_count
        
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
    
    def update_state(self, state: CodeAgentState, result: Any) -> CodeAgentState:
        """Update state with CodeMinion-specific information."""
        # Update the internal state
        self.state = super().update_state(state, result)
        
        # Extract confidence from result if available
        if isinstance(result, tuple) and len(result) >= 2:
            self.state.last_confidence = result[1]  # score/confidence
            
        return self.state
    
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
    
    def is_done(self, result: Any, state: CodeAgentState) -> bool:
        """
        Check if the task is completed by detecting the is_final_answer flag.
        """
        # Use the provided state
        self.state = state
        
        # First call the parent's is_done method
        parent_done = super().is_done(result, self.state)
        if parent_done:
            return True
        
        # Check if there is a final_answer flag in the internal state
        if self.state.is_final_answer:
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
    
    def finalize(self, result: Any, state: CodeAgentState) -> Any:
        """
        Organize the final result, specially handling the final_answer case.
        """
        # Use the provided state
        self.state = state
        
        # Check if there is a final_answer_value in the internal state
        if self.state.final_answer_value is not None:
            return self.state.final_answer_value
        
        # For AgentResponse, prioritize using its final_answer
        if hasattr(result, 'final_answer') and result.final_answer is not None:
            return result.final_answer
        
        # Call parent's finalize method
        return super().finalize(result, self.state)

    def _update_executor_tools(self):
        """Update the Python executor with current tools."""
        if self.python_executor and self.tools:
            if self.use_async_executor:
                # For AsyncPythonExecutor, pass tools directly - it will handle async/sync conversion
                tool_dict = {}
                for tool in self.tools:
                    if hasattr(tool, 'name'):
                        # Register with original name (for compatibility)
                        tool_dict[tool.name] = tool
                        # Also register with Python-safe name (dots/dashes replaced with underscores)
                        safe_name = tool.name.replace('.', '_').replace('-', '_')
                        if safe_name != tool.name:
                            tool_dict[safe_name] = tool
                self.python_executor.send_tools(tool_dict)
            else:
                # Same logic for sync executor
                tool_dict = {}
                for tool in self.tools:
                    if hasattr(tool, 'name'):
                        tool_dict[tool.name] = tool
                        safe_name = tool.name.replace('.', '_').replace('-', '_')
                        if safe_name != tool.name:
                            tool_dict[safe_name] = tool
                self.python_executor.send_tools(tool_dict)
    
    def add_tool(self, tool: BaseTool):
        """Add a tool and update the executor."""
        super().add_tool(tool)
        # Update executor tools whenever a new tool is added
        if hasattr(self, 'python_executor'):
            self._update_executor_tools()
            
    # State management methods from StateCodeAgent
    
    def run(self, 
           task: Optional[Union[str, Input]] = None,
           max_steps: Optional[int] = None,
           reset: bool = False,
           route: Optional[str] = None,
           **kwargs) -> Any:
        """
        Synchronous interface for running the agent using internal state.
        
        Args:
            task: Task description or Input object
            max_steps: Maximum number of steps
            reset: If True, reset the agent state before execution
            route: 可选的route名称，如 "code", "cot", "plan" 等，指定使用哪个minion
            **kwargs: Additional parameters
            
        Returns:
            Final task result
        """
        import asyncio
        return asyncio.run(self.run_async(task=task, max_steps=max_steps, reset=reset, stream=False, route=route, **kwargs))

    async def run_async(self, task: Optional[Union[str, Input]] = None,
                       max_steps: Optional[int] = None,
                       reset: bool = False,
                       stream: bool = False,
                       route: Optional[str] = None,
                       **kwargs) -> Any:
        """
        Run the CodeAgent with code-thinking capabilities using internal state.
        
        Args:
            task: Task description or Input object
            max_steps: Maximum steps to execute
            reset: If True, reset the agent state before execution
            stream: If True, return streaming generator
            route: 可选的route名称，如 "code", "cot", "plan" 等，指定使用哪个minion
            **kwargs: Additional parameters
            
        Returns:
            Agent response or async generator for streaming
        """
        # Prepare input and internal state
        enhanced_input = self._prepare_input(task, route=route)
        self._prepare_internal_state(task, reset)
        
        # Record input in state for interaction tracking
        self.state.input = enhanced_input
        
        try:
            # Use BaseAgent's logic but with our enhanced input and internal state
            result = await super().run_async(
                task=enhanced_input,
                state=self.state, 
                max_steps=max_steps, 
                stream=stream, 
                route=route,
                **kwargs
            )
            
            # Record interaction if state tracking is enabled
            if self.enable_state_tracking:
                await self._record_interaction(enhanced_input, result, reset)
                if self.auto_save_state:
                    self._save_persistent_state(self.state)
            
            return result
            
        except Exception as e:
            # Record failed interaction if state tracking is enabled
            if self.enable_state_tracking:
                await self._record_interaction(enhanced_input, f"Error: {e}", reset)
            raise
    
    def _prepare_input(self, task: Optional[Union[str, Input]], route: Optional[str] = None) -> Input:
        """
        Prepare input data for execution.
        
        Args:
            task: Task description or Input object
            route: 可选的route名称，如果提供则覆盖默认的'code' route
            
        Returns:
            Input: Prepared Input object with enhanced query
        """
        # Convert string task to Input if needed
        if isinstance(task, str):
            # Use provided route or default to 'code'
            default_route = route if route is not None else 'code'
            input_data = Input(query=task, route=default_route)
        elif isinstance(task, Input):
            input_data = task
            # Set route based on priority: explicit route param > existing route > default 'code'
            if route is not None:
                input_data.route = route
            elif not input_data.route:
                input_data.route = 'code'
        else:
            raise ValueError(f"Task must be string or Input object, got {type(task)}")
        
        # Enhance input with code-thinking instructions, do not repeat what's done in CodeMinion
        enhanced_input = input_data

        return enhanced_input
    
    def _prepare_internal_state(self, task: Optional[Union[str, Input]], reset: bool) -> None:
        """
        Prepare internal state for execution.
        
        Args:
            task: Task description or Input object
            reset: Whether to reset state before execution
        """
        # Initialize internal state if needed
        if not hasattr(self, 'state') or self.state is None:
            self.state = CodeAgentState(agent=self)
        
        # Handle reset functionality
        if reset:
            if self.enable_state_tracking:
                # Reset both internal state and persistent state
                self.reset_state()
                logger.info("Agent state has been reset (including persistent state)")
            else:
                # Just reset internal state
                self.state.reset()
                logger.info("Agent internal state has been reset")
        
        # Set task information
        if task is not None:
            if isinstance(task, str):
                self.state.task = task
            else:
                self.state.task = task.query
        
        # Add persistent information if state tracking is enabled
        if self.enable_state_tracking:
            # Merge persistent state into metadata
            self.state.metadata.update(self.persistent_state)
            self.state.metadata['conversation_history'] = self.get_recent_history()
    
    def reset_state(self) -> None:
        """
        Reset agent state.
        
        This clears:
        - Conversation history
        - Working variables
        - Temporary memory
        - Internal state
        But preserves:
        - Learned patterns
        - Core configuration
        """
        # Reset internal state first
        if hasattr(self, 'state') and self.state:
            self.state.reset()
        else:
            self.state = CodeAgentState(agent=self)
        
        if self.enable_state_tracking:
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