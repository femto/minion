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
import json
import re
import ast
import traceback
import logging
from datetime import datetime

from .base_agent import BaseAgent
from ..tools.base_tool import BaseTool
from ..main.brain import Brain
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
    
    def __init__(self, agent: 'CodeMinion'):
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


#maybe we should call it CodeAgent?
@dataclass
class CodeMinion(BaseAgent):
    """
    A "think in code" agent that uses Python code for reasoning and actions.
    
    This agent extends BaseAgent with:
    - Code-based reasoning instead of JSON
    - Self-reflection capabilities
    - ReAct (Reason-Act-Observe) cycles
    - Safe code execution
    """
    
    name: str = "code_minion"
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
            additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn"],
            max_print_outputs_length=50000,
            additional_functions={}
        )
        
        # Add the think tool
        self.add_tool(ThinkTool())
        self.add_tool(FinalAnswerTool())

    async def execute_step(self, input_data: Input, **kwargs) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        """
        Execute a step with enhanced code-based reasoning.
        
        This method overrides the parent's execute_step to add:
        - Code-based reasoning
        - Self-reflection triggers
        - Enhanced error handling
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
            result = await self.brain.step(input=enhanced_input, tools=tools, **kwargs)
            
            # Process any generated code
            if result and len(result) > 0:
                response = result[0]
                processed_response = await self._process_code_response(response, state)
                
                # Update the result with processed response
                result = (processed_response, result[1], result[2], result[3], result[4])
            
            return result
            
        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            error_msg = f"Step execution failed: {e}"
            return (error_msg, 0.0, False, False, {'error': str(e)})
    
    def _enhance_input_for_code_thinking(self, input_data: Input) -> Input:
        """Enhance input with code-thinking instructions."""
        enhanced_query = f"""
You are a CodeMinion that thinks in Python code. Instead of just describing what to do, 
you should write Python code to reason about problems and execute actions.

**Core Principles:**
1. Use Python code for reasoning, calculations, and problem-solving
2. Break down complex problems into smaller, manageable code snippets
3. Use variables to store intermediate results and thoughts
4. Write clear, readable code with comments explaining your reasoning
5. **CRUCIAL**: When you have the final answer, call `final_answer("your answer")` to end the task

**Your Task:**
{input_data.query}

**Instructions:**
1. Start by writing code to understand the problem
2. Break it down into steps using Python
3. Execute each step and observe the results  
4. **IMPORTANT**: When you have the final answer, call the `final_answer()` function with your answer

**Example of proper completion:**
```python
# Step 1: Understand the problem
# Step 2: Solve it step by step
result = calculate_something()
print(f"The answer is: {{result}}")

# Step 3: Provide final answer using the built-in final_answer function
# DO NOT define your own final_answer function - use the built-in one
final_answer(f"The answer is {{result}}")
```

**Available Functions:**
- `final_answer(answer)`: Built-in function to provide final answer and end the task
- All standard Python functions (math, etc.)
- Additional imports: numpy, pandas, matplotlib, seaborn

**IMPORTANT RULES:**
1. DO NOT define your own `final_answer` function - it is already provided as a built-in
2. Call `final_answer(your_answer)` directly when you have the solution
3. Think in code, not just in words!

Remember: Always end by calling the built-in `final_answer()` function when you have the solution.
"""
        
        # Create a new Input with enhanced query
        enhanced_input = Input(
            query=enhanced_query,
            route=getattr(input_data, 'route', 'python'),
            check=getattr(input_data, 'check', False),
            dataset=getattr(input_data, 'dataset', None),
            metadata=getattr(input_data, 'metadata', {})
        )
        
        return enhanced_input
    
    async def _process_code_response(self, response: str, state: Dict[str, Any]) -> str:
        """Process and execute any code found in the response."""
        # Extract Python code blocks from the response
        code_blocks = self._extract_code_blocks(response)
        
        if not code_blocks:
            return response
        
        processed_parts = []
        processed_parts.append(response)
        
        for i, code in enumerate(code_blocks):
            if len(code) > self.max_code_length:
                processed_parts.append(f"\n[Code block {i+1} too long to execute safely]")
                continue
            
            if not self.python_executor:
                processed_parts.append(f"\n[Python executor not available]")
                continue
                
            try:
                # 使用 LocalPythonExecutor 执行代码
                output, logs, is_final_answer = self.python_executor(code)
                
                processed_parts.append(f"\n[Code block {i+1} executed successfully]")
                if logs:
                    processed_parts.append(f"Output: {logs}")
                if output is not None:
                    processed_parts.append(f"Result: {output}")
                
                # Store result in state for future reference
                state[f'code_result_{i}'] = output
                state[f'code_logs_{i}'] = logs
                state[f'is_final_answer_{i}'] = is_final_answer
                
                # 如果是最终答案，设置全局标志
                if is_final_answer:
                    state['is_final_answer'] = True
                    state['final_answer_value'] = output
                    
            except Exception as e:
                processed_parts.append(f"\n[Code block {i+1} execution failed]")
                processed_parts.append(f"Error: {str(e)}")
                
                # Increment error count
                state['error_count'] = state.get('error_count', 0) + 1
        
        return '\n'.join(processed_parts)
    
    def _extract_code_blocks(self, text: str) -> List[str]:
        """Extract Python code blocks from text."""
        # Look for code blocks marked with ```python or ```
        python_code_pattern = r'```(?:python)?\s*\n(.*?)\n```'
        matches = re.findall(python_code_pattern, text, re.DOTALL)
        
        # Try a different pattern that's more flexible
        if not matches:
            # Try without requiring newlines
            alternative_pattern = r'```(?:python)?(.*?)```'
            alt_matches = re.findall(alternative_pattern, text, re.DOTALL)
            matches = [match.strip() for match in alt_matches if match.strip()]
        
        # Also look for inline code that looks like assignments or function calls
        inline_pattern = r'^\s*([a-zA-Z_][a-zA-Z0-9_]*\s*=.*|[a-zA-Z_][a-zA-Z0-9_]*\(.*\))$'
        lines = text.split('\n')
        inline_matches = [line.strip() for line in lines if re.match(inline_pattern, line.strip())]
        
        return matches + inline_matches
    
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
        input_obj = Input(query=problem, route='python')
        result = await self.run(input_obj, **kwargs)
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
        result = await self.run(input_obj, **kwargs)
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
        
        return False
    
    def finalize(self, result: Any, state: Dict[str, Any]) -> Any:
        """
        整理最终结果，特别处理 final_answer 的情况
        """
        # 检查是否有最终答案值
        if 'final_answer_value' in state:
            return state['final_answer_value']
        
        # 调用父类的 finalize 方法
        return super().finalize(result, state)