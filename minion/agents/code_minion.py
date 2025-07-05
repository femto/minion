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


class CodeExecutor:
    """Safe code executor with sandboxing and security features."""
    
    def __init__(self, python_env=None):
        self.python_env = python_env
        self.forbidden_imports = {
            'os', 'sys', 'subprocess', 'shutil', 'glob', 'tempfile',
            'importlib', '__import__', 'eval', 'exec', 'compile',
            'open', 'input', 'raw_input'
        }
        self.allowed_imports = {
            'math', 'random', 'datetime', 'time', 'json', 'collections',
            'itertools', 'functools', 'operator', 'statistics', 'decimal',
            'fractions', 'numpy', 'pandas', 'matplotlib', 'seaborn',
            'scipy', 'sympy', 'requests'
        }
    
    def validate_code(self, code: str) -> Tuple[bool, str]:
        """
        Validate code for security and safety.
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Parse the code to check for syntax errors
            ast.parse(code)
            
            # Check for forbidden patterns
            forbidden_patterns = [
                r'\b(os|sys|subprocess|shutil|glob|tempfile|importlib)\b',
                r'\b(__import__|eval|exec|compile)\b',
                r'\bopen\s*\(',
                r'\binput\s*\(',
                r'\braw_input\s*\(',
                r'import\s+os',
                r'from\s+os\s+import',
                r'__.*__',  # Dunder methods (with some exceptions)
            ]
            
            for pattern in forbidden_patterns:
                if re.search(pattern, code):
                    return False, f"Forbidden pattern detected: {pattern}"
            
            return True, ""
            
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Validation error: {e}"
    
    async def execute_code(self, code: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Any]:
        """
        Execute Python code safely.
        
        Args:
            code: Python code to execute
            context: Additional context variables
            
        Returns:
            Tuple of (success, output, result)
        """
        # Validate code first
        is_valid, error_msg = self.validate_code(code)
        if not is_valid:
            return False, f"Code validation failed: {error_msg}", None
        
        if self.python_env:
            try:
                # Use the existing python environment
                result = await self.python_env.run(code)
                return True, result, result
            except Exception as e:
                return False, f"Execution error: {e}", None
        else:
            # Fallback to local execution with restricted environment
            try:
                # Create a restricted global environment
                restricted_globals = {
                    '__builtins__': {
                        'abs': abs, 'all': all, 'any': any, 'bin': bin,
                        'bool': bool, 'chr': chr, 'dict': dict, 'dir': dir,
                        'enumerate': enumerate, 'filter': filter, 'float': float,
                        'format': format, 'frozenset': frozenset, 'hash': hash,
                        'hex': hex, 'int': int, 'isinstance': isinstance,
                        'issubclass': issubclass, 'iter': iter, 'len': len,
                        'list': list, 'map': map, 'max': max, 'min': min,
                        'next': next, 'oct': oct, 'ord': ord, 'pow': pow,
                        'print': print, 'range': range, 'repr': repr,
                        'reversed': reversed, 'round': round, 'set': set,
                        'slice': slice, 'sorted': sorted, 'str': str,
                        'sum': sum, 'tuple': tuple, 'type': type, 'zip': zip,
                    }
                }
                
                # Add context variables
                if context:
                    restricted_globals.update(context)
                
                # Execute the code
                local_vars = {}
                exec(code, restricted_globals, local_vars)
                
                # Return the result
                result = local_vars.get('result', str(local_vars))
                return True, str(result), result
                
            except Exception as e:
                error_output = f"Execution error: {e}\n{traceback.format_exc()}"
                return False, error_output, None


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
    code_executor: Optional[CodeExecutor] = None
    enable_reflection: bool = True
    max_code_length: int = 2000
    
    def __post_init__(self):
        """Initialize the CodeMinion with thinking capabilities."""
        super().__post_init__()
        
        # Initialize thinking engine
        self.thinking_engine = ThinkingEngine(self)
        
        # Initialize code executor
        python_env = getattr(self.brain, 'python_env', None) if self.brain else None
        self.code_executor = CodeExecutor(python_env=python_env)
        
        # Add the think tool
        self.add_tool(ThinkTool())
    
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
            result = await self.brain.step(input=enhanced_input, tools=self.tools, **kwargs)
            
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
5. Use the 'think' tool when you need to pause and reflect

**Available Tools:**
- think(reflection): Pause and reflect on the current situation
- Any other tools provided in the context

**Your Task:**
{input_data.query}

**Instructions:**
1. Start by writing code to understand the problem
2. Break it down into steps using Python
3. Execute each step and observe the results
4. Use the think tool if you need to reconsider your approach
5. Provide a final answer based on your code execution

Remember: Think in code, not just in words!
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
            
            if not self.code_executor:
                processed_parts.append(f"\n[Code executor not available]")
                continue
                
            success, output, result = await self.code_executor.execute_code(code)
            
            if success:
                processed_parts.append(f"\n[Code block {i+1} executed successfully]")
                processed_parts.append(f"Output: {output}")
                
                # Store result in state for future reference
                state[f'code_result_{i}'] = result
            else:
                processed_parts.append(f"\n[Code block {i+1} execution failed]")
                processed_parts.append(f"Error: {output}")
                
                # Increment error count
                state['error_count'] = state.get('error_count', 0) + 1
        
        return '\n'.join(processed_parts)
    
    def _extract_code_blocks(self, text: str) -> List[str]:
        """Extract Python code blocks from text."""
        # Look for code blocks marked with ```python or ```
        python_code_pattern = r'```(?:python)?\s*\n(.*?)\n```'
        matches = re.findall(python_code_pattern, text, re.DOTALL)
        
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