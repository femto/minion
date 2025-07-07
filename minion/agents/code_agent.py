"""
CodeMinion: A "think in code" agent that uses Python code for reasoning and actions.

This agent extends the BaseAgent to provide:
- Python code-based reasoning instead of JSON
- Self-reflection capabilities with the "think" tool
- ReAct (Reason-Act-Observe) cycles
- Safe code execution with sandboxing
- Memory integration for learning
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import re
import traceback
import logging
from datetime import datetime

from .base_agent import BaseAgent
from minion.types.agent_response import AgentResponse
from ..tools.base_tool import BaseTool
from ..main.input import Input
from ..main.local_python_executor import LocalPythonExecutor
from ..tools.default_tools import FinalAnswerTool

logger = logging.getLogger(__name__)


class ThinkTool(BaseTool):
    """A tool that allows the agent to pause and reflect on its current situation."""
    
    def __init__(self):
        super().__init__()
        self.name = "think"
        self.description = "Use this tool to pause and reflect on the current situation, plan next steps, or reconsider your approach."
    
    def forward(self, reflection: str, **kwargs) -> str:
        """
        Process a reflection thought.
        
        Args:
            reflection: The agent's reflection or thought process
            
        Returns:
            A formatted response acknowledging the reflection
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"[{timestamp}] THOUGHT: {reflection}"


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
    """
    
    name: str = "code_agent"
    thinking_engine: Optional[ThinkingEngine] = None
    python_executor: Optional[LocalPythonExecutor] = None
    enable_reflection: bool = True
    max_code_length: int = 2000
    
    def __post_init__(self):
        """Initialize the CodeMinion with thinking capabilities."""
        super().__post_init__()
        
        # Initialize thinking engine
        self.thinking_engine = ThinkingEngine(self)
        
        # Initialize code executor (使用 LocalPythonExecutor)
        self.python_executor = LocalPythonExecutor(
            additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn", "requests", "json", "csv"],
            max_print_outputs_length=50000,
            additional_functions={}
        )
        
        # Add the think tool and final answer tool
        self.add_tool(ThinkTool())
        self.add_tool(FinalAnswerTool())
        
        # Send tools to the python executor
        self._update_executor_tools()

    async def execute_step(self, input_data: Input, **kwargs) -> AgentResponse:
        """
        Execute a step with enhanced code-based reasoning.
        
        This method overrides the parent's execute_step to add:
        - Code-based reasoning
        - Self-reflection triggers
        - Enhanced error handling
        
        Returns:
            AgentResponse: Structured response instead of 5-tuple
        """
        # Check if we should reflect first
        state = kwargs.get('state', {})
        if self.enable_reflection and self.thinking_engine and self.thinking_engine.should_reflect(state):
            await self._perform_reflection(state)
        
        # Enhance the input with code-thinking instructions
        enhanced_input = self._enhance_input_for_code_thinking(input_data)
        
        # Execute the step
        try:
            if not self.brain:
                raise ValueError("Brain is not initialized")
            
            # 处理tools参数，避免重复传递
            tools = kwargs.pop('tools', self.tools)
            result = await self.brain.step(input=enhanced_input, tools=tools,**kwargs)
            
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
            
            # Only process code if response is a string and contains code blocks
            if isinstance(agent_response.response, str) and self._contains_code_blocks(agent_response.response):
                processed_response = await self._process_code_response(agent_response.response, state)
                agent_response.response = processed_response
                
                # Update termination status based on state
                if state.get('is_final_answer', False):
                    agent_response.set_final_answer(state.get('final_answer_value'))
            
            return agent_response
            
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            error_msg = f"Step execution failed: {e}"
            return AgentResponse(
                response=error_msg,
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
                    available_tools.append(f"- {tool.name}: {tool.description}")
        
        tools_description = "\n".join(available_tools) if available_tools else "- final_answer: Provide the final answer to complete the task"
        
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
    
    async def step(self, input_data: Any, **kwargs) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        """
        重写step方法以支持AgentResponse同时保持向后兼容性
        
        Args:
            input_data: 输入数据
            **kwargs: 其他参数
            
        Returns:
            5-tuple格式的结果以保持向后兼容性
        """
        # 调用我们的execute_step方法，它返回AgentResponse
        agent_response = await self.execute_step(
            input_data if isinstance(input_data, Input) else 
            Input(query=str(input_data)), 
            **kwargs
        )
        
        # 转换为5-tuple格式以保持向后兼容性
        return agent_response.to_tuple()
    
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
                # 使用 LocalPythonExecutor 执行代码
                output, logs, is_final_answer = self.python_executor(code)
                
                # 构建观察反馈
                observation_parts = [f"\n**Observation:** Code block {i+1} executed successfully."]
                
                if logs:
                    # 清理并格式化日志输出
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
                
                # 如果是最终答案，设置全局标志并立即返回
                if is_final_answer:
                    state['is_final_answer'] = True
                    state['final_answer_value'] = output
                    final_observation = f"\n**Final Answer Found:** {output}"
                    final_observation += f"\n**Task Status:** COMPLETED"
                    processed_parts.append(final_observation)
                    return '\n'.join(processed_parts)
                    
            except Exception as e:
                # 提供详细的错误观察
                error_observation = f"\n**Observation:** Code block {i+1} execution failed."
                error_observation += f"\n**Error:** {str(e)}"
                
                # 如果有traceback信息，提供简化版本
                if hasattr(e, '__traceback__'):
                    try:
                        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
                        # 只取最后几行关键信息
                        key_lines = [line.strip() for line in tb_lines[-3:] if line.strip()]
                        if key_lines:
                            error_observation += f"\n**Traceback:** {' | '.join(key_lines)}"
                    except:
                        pass
                
                processed_parts.append(error_observation)
                
                # Increment error count
                state['error_count'] = state.get('error_count', 0) + 1
                
                # 提供错误恢复建议
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
            
        return state
    
    async def solve_problem(self, problem: str, **kwargs) -> str:
        """
        Solve a problem using code-based reasoning.
        
        Args:
            problem: The problem to solve
            **kwargs: Additional parameters
            
        Returns:
            The solution as a string
        """
        input_obj = Input(query=problem, route='code')
        result = await self.run_async(input_obj, **kwargs)
        return str(result)
    
    async def analyze_data(self, data: Any, question: str, **kwargs) -> str:
        """
        Analyze data using code-based reasoning.
        
        Args:
            data: The data to analyze
            question: The question to answer about the data
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
        result = await self.run_async(input_obj, **kwargs)
        return str(result)
    
    def is_done(self, result: Any, state: Dict[str, Any]) -> bool:
        """
        检查任务是否完成，通过检测 is_final_answer 标志来判断
        """
        # 先调用父类的is_done方法  
        parent_done = super().is_done(result, state)
        if parent_done:
            return True
        
        # 检查状态中是否有 final_answer 标志
        if state.get('is_final_answer', False):
            return True
        
        # 对于AgentResponse，使用其内置的检查方法
        if hasattr(result, 'is_done'):
            return result.is_done()
        
        # 检查result中是否有终止标志 (5-tuple格式)
        if isinstance(result, tuple) and len(result) >= 3:
            terminated = result[2]
            if terminated:
                return True
        
        return False
    
    def finalize(self, result: Any, state: Dict[str, Any]) -> Any:
        """
        整理最终结果，特别处理 final_answer 的情况
        """
        # 检查是否有最终答案值
        if 'final_answer_value' in state:
            return state['final_answer_value']
        
        # 对于AgentResponse，优先使用其final_answer
        if hasattr(result, 'final_answer') and result.final_answer is not None:
            return result.final_answer
        
        # 调用父类的 finalize 方法
        return super().finalize(result, state)

    def _update_executor_tools(self):
        """Update the LocalPythonExecutor with current tools."""
        if self.python_executor and self.tools:
            # Convert tools to a format that LocalPythonExecutor can understand
            tool_functions = {}
            for tool in self.tools:
                if hasattr(tool, 'forward') and hasattr(tool, 'name'):
                    # Create a wrapper function for the tool
                    def create_tool_wrapper(tool_instance):
                        def tool_wrapper(*args, **kwargs):
                            return tool_instance.forward(*args, **kwargs)
                        tool_wrapper.__name__ = tool_instance.name
                        tool_wrapper.__doc__ = tool_instance.description
                        return tool_wrapper
                    
                    tool_functions[tool.name] = create_tool_wrapper(tool)
            
            # Send tools to the executor
            self.python_executor.send_tools(tool_functions)
    
    def add_tool(self, tool: BaseTool):
        """Add a tool and update the executor."""
        super().add_tool(tool)
        # Update executor tools whenever a new tool is added
        if hasattr(self, 'python_executor'):
            self._update_executor_tools()