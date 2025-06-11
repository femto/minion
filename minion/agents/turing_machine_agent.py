from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, AsyncIterator, Tuple
from enum import Enum
import json
import re
import inspect
from abc import ABC, abstractmethod

from ..providers.base_provider import BaseProvider
from ..providers.llm_provider_registry import llm_registry
from ..configs.config import config, LLMConfig
from ..main.input import Input
from .base_agent import BaseAgent
from ..tools.base_tool import BaseTool


class AgentState(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    WAITING = "waiting"
    HALTED = "halted"
    ERROR = "error"


@dataclass
class Memory:
    """Memory system for the agent"""
    working_memory: Dict[str, Any] = field(default_factory=dict)  # Short-term
    episodic_memory: List[Dict[str, Any]] = field(default_factory=list)  # Experience
    semantic_memory: Dict[str, Any] = field(default_factory=dict)  # Long-term knowledge

    def update_working(self, key: str, value: Any):
        self.working_memory[key] = value

    def add_episode(self, episode: Dict[str, Any]):
        self.episodic_memory.append(episode)

    def update_semantic(self, key: str, value: Any):
        self.semantic_memory[key] = value


@dataclass
class Plan:
    """Hierarchical planning structure"""
    goal: str
    current_step: int = 0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    sub_plans: List['Plan'] = field(default_factory=list)

    def add_step(self, action: str, params: Dict[str, Any] = None):
        self.steps.append({
            "action": action,
            "params": params or {},
            "status": "pending"
        })

    def get_current_step(self) -> Optional[Dict[str, Any]]:
        if self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def advance_step(self):
        if self.current_step < len(self.steps):
            self.steps[self.current_step]["status"] = "completed"
            self.current_step += 1


@dataclass
class AgentInput:
    """Input to the Turing Machine at each step"""
    goal: str
    plan: Plan
    memory: Memory
    prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    external_input: Any = None
    available_tools: List[BaseTool] = field(default_factory=list)


@dataclass
class AgentOutput:
    """Output from the Turing Machine at each step"""
    next_instruction: str
    action_params: Dict[str, Any] = field(default_factory=dict)
    memory_updates: Dict[str, Any] = field(default_factory=dict)
    plan_updates: Optional[Plan] = None
    current_result: Any = None
    next_state: AgentState = AgentState.EXECUTING
    halt_condition: bool = False
    confidence: float = 1.0
    reasoning: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)  # 新增：专门存储工具调用


@dataclass
class AgentResponse:
    """Response from TuringMachineAgent - more convenient than gym 5-tuple"""
    response: Any
    score: float
    terminated: bool
    truncated: bool
    info: Dict[str, Any]
    step_count: int
    state: AgentState
    success: bool = True  # 新增：执行是否成功，默认为True
    error: Optional[str] = None  # 新增：错误信息，当success=False时使用
    
    def __iter__(self):
        """Allow unpacking as tuple for backward compatibility"""
        return iter((self.response, self.score, self.terminated, self.truncated, self.info))


class LLMInterface(ABC):
    """Abstract interface for LLM calls"""

    @abstractmethod
    async def generate(self, prompt: str, context: Dict[str, Any] = None) -> str:
        pass


class MinionLLMInterface(LLMInterface):
    """Real LLM implementation using Minion's provider system"""

    def __init__(self, provider_config: Union[str, LLMConfig, BaseProvider] = None):
        """
        Initialize the LLM interface
        
        Args:
            provider_config: Can be:
                - str: model name to look up in config.models
                - LLMConfig: configuration object
                - BaseProvider: provider instance
                - None: use default llm config
        """
        if isinstance(provider_config, BaseProvider):
            self.provider = provider_config
        elif isinstance(provider_config, str):
            # Look up model by name
            if provider_config in config.models:
                model_config = config.models[provider_config]
                provider_class = llm_registry.get_provider(model_config.api_type)
                self.provider = provider_class(model_config)
            else:
                raise ValueError(f"Model '{provider_config}' not found in config.models")
        elif isinstance(provider_config, LLMConfig):
            provider_class = llm_registry.get_provider(provider_config.api_type)
            self.provider = provider_class(provider_config)
        elif provider_config is None:
            # Use default
            provider_class = llm_registry.get_provider(config.llm.api_type)
            self.provider = provider_class(config.llm)
        else:
            raise ValueError(f"Invalid provider_config type: {type(provider_config)}")

    async def generate(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate response using the configured provider"""
        # Convert prompt to Input format expected by providers
        input_obj = Input(query=prompt)
        
        # Use the provider's generate method
        response = await self.provider.generate([{"role": "user", "content": prompt}])
        
        return response if isinstance(response, str) else str(response)


class AgentTuringMachine:
    """LLM Agent as a Turing Machine"""

    def __init__(self, llm: LLMInterface):
        self.llm = llm
        self.current_state = AgentState.PLANNING
        self.step_count = 0
        self.max_steps = 1000  # Prevent infinite loops

    def _construct_prompt(self, agent_input: AgentInput) -> str:
        """Construct the prompt for the LLM based on current state and memory"""

        # Get current working memory and let LLM see it directly
        memory_info = ""
        if agent_input.memory and agent_input.memory.working_memory:
            memory_info = f"\n## Your Working Memory:\n{agent_input.memory.working_memory}\n"
        
        # Get plan context  
        current_step = agent_input.plan.get_current_step()
        plan_info = f"""
## Progress:
- Current step: {agent_input.plan.current_step + 1} of {len(agent_input.plan.steps)}
- Current action: {current_step['action'] if current_step else 'Starting'}"""

        # Get available tools information
        tools_info = ""
        if agent_input.available_tools:
            tools_info = "\n## Available Tools:\n"
            for tool in agent_input.available_tools:
                tools_info += f"- **{tool.name}**: {tool.description}\n"
                if hasattr(tool, 'inputs') and tool.inputs:
                    inputs_desc = ", ".join([f"{k}: {v.get('description', v.get('type', 'any'))}" for k, v in tool.inputs.items()])
                    tools_info += f"  - Inputs: {inputs_desc}\n"

        # Construct comprehensive prompt
        prompt = f"""You are a Turing Machine Agent in state: {self.current_state.value}

## Task Goal: {agent_input.goal}

## Current Context: {agent_input.prompt}
{plan_info}{memory_info}{tools_info}

Please analyze the situation and determine your next action. Consider:
1. Current state and goal
2. Your existing working memory and what you've learned so far
3. Any previous tool execution results mentioned in the context
4. What action would best progress toward the goal
5. Whether you need to transition to a different state  
6. How to synthesize your previous memory with this step's results into an updated summary
7. Whether the task is complete and you should halt execution
8. If you're repeating similar actions, provide the actual final answer instead

IMPORTANT: If the task asks for code, explanations, calculations, or specific content - provide the ACTUAL result in current_result, not just descriptions of what you plan to do. Avoid repetitive planning - move to concrete output.

Available states: planning, executing, reflecting, waiting, halted, error

Preferred JSON format:
{{
    "reasoning": "explanation of your decision",
    "next_instruction": "detailed instruction for what to do next - describe WHAT you want to accomplish, not HOW to do it", 
    "current_result": "your detailed response or analysis",
    "next_state": "planning|executing|reflecting|waiting|halted|error",
    "halt_condition": false,
    "confidence": 0.95,
    "memory_updates": {{
        "working_execution_summary": "UPDATED summary combining your previous memory with this step's accomplishments",
        "working_current_progress": "UPDATED overall progress assessment integrating past and current work",
        "working_next_focus": "UPDATED focus for next steps based on accumulated understanding"
    }}
}}

IMPORTANT: 
- Your next_instruction should be a clear description of WHAT needs to be done, not specific implementation details or tool calls
- Your memory_updates should be CUMULATIVE SUMMARIES that integrate your existing working memory with this step's results, NOT just descriptions of the current step. Think of it as updating your persistent understanding.
- Set halt_condition to true when the task is fully completed and no further steps are needed. This will stop the execution.

If you cannot provide JSON, just give a helpful response to complete the current task step.
"""
        return prompt

    def _parse_llm_output(self, output: str) -> AgentOutput:
        """Parse LLM output into structured AgentOutput"""
        
        # Handle empty or None output
        if not output or output.strip() == "":
            return AgentOutput(
                next_instruction="handle empty response error and check API configuration",
                current_result="LLM returned empty response. This may be due to API configuration issues.",
                next_state=AgentState.ERROR,
                halt_condition=True,
                reasoning="Empty LLM response - check API configuration"
            )
        
        # Extract JSON from markdown code blocks if present
        json_content = self._extract_json_from_output(output)
        
        try:
            # Try to parse as JSON
            data = json.loads(json_content)
            return AgentOutput(
                next_instruction=data.get("next_instruction", data.get("next_instruction", "wait and continue")),
                action_params=data.get("action_params", {}),
                memory_updates=data.get("memory_updates", {}),
                plan_updates=data.get("plan_updates"),
                current_result=data.get("current_result"),
                next_state=AgentState(data.get("next_state", "executing")),
                halt_condition=data.get("halt_condition", False),
                confidence=data.get("confidence", 1.0),
                reasoning=data.get("reasoning", ""),
                tool_calls=data.get("tool_calls", [])
            )
        except json.JSONDecodeError:
            # If it's not JSON, try to handle as plain text
            return self._handle_non_json_output(output)
        except (ValueError, KeyError) as e:
            # Handle other parsing errors
            return AgentOutput(
                next_instruction="handle parsing error and request properly formatted response",
                current_result=f"Error parsing LLM response: {str(e)}",
                next_state=AgentState.ERROR,
                halt_condition=True,
                reasoning=f"Parse error: {str(e)}"
            )
    
    def _extract_json_from_output(self, output: str) -> str:
        """Extract JSON content from markdown code blocks or plain text"""
        output = output.strip()
        
        # Check for markdown code blocks with json, JSON, or no language specified
        patterns = [
            r'```json\s*\n(.*?)\n```',  # ```json ... ```
            r'```JSON\s*\n(.*?)\n```',  # ```JSON ... ```
            r'```\s*\n(\{.*?\})\s*\n```',  # ``` { ... } ```
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Look for JSON object without code blocks - use proper brace matching
        extracted_json = self._extract_balanced_json(output)
        if extracted_json:
            return extracted_json
        
        # If no JSON found, return original output
        return output
    
    def _extract_balanced_json(self, text: str) -> str:
        """Extract JSON with proper brace matching to handle nested objects"""
        # Find the first opening brace
        start = text.find('{')
        if start == -1:
            return ""
        
        # Count braces to find matching closing brace
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found matching closing brace
                        return text[start:i+1]
        
        return ""  # No matching closing brace found
    
    def _handle_non_json_output(self, output: str) -> AgentOutput:
        """Handle non-JSON output by extracting information from plain text"""
        return AgentOutput(
            next_instruction=output.strip(),
            current_result=output.strip(),
            next_state=AgentState.EXECUTING,
            halt_condition=False,
            reasoning="Non-JSON response processed",
            tool_calls=[]  # 新增：空的工具调用列表
        )

    def _update_state(self, agent_input: AgentInput, agent_output: AgentOutput):
        """Update the agent's internal state based on output"""

        # Update memory
        for key, value in agent_output.memory_updates.items():
            if key.startswith("working_"):
                agent_input.memory.update_working(key[8:], value)
            elif key.startswith("semantic_"):
                agent_input.memory.update_semantic(key[9:], value)

        # Add episode to memory
        episode = {
            "step": self.step_count,
            "state": self.current_state.value,
            "instruction": agent_output.next_instruction,
            "result": agent_output.current_result,
            "confidence": agent_output.confidence
        }
        agent_input.memory.add_episode(episode)

        # Update plan
        if agent_output.plan_updates:
            agent_input.plan = agent_output.plan_updates
        elif "advance_plan" in agent_output.next_instruction.lower():
            agent_input.plan.advance_step()

        # Update state
        self.current_state = agent_output.next_state
        self.step_count += 1

    async def step(self, agent_input: AgentInput, debug: bool = False) -> AgentOutput:
        """Execute one step of the Turing Machine"""
        if self.step_count >= self.max_steps:
            return AgentOutput(
                next_instruction="max steps reached",
                current_result="Maximum steps exceeded",
                next_state=AgentState.HALTED,
                halt_condition=True,
                reasoning="Reached maximum step limit"
            )

        self.step_count += 1
        
        if debug:
            print(f"\n=== Step {self.step_count} ===")
            print(f"Current state: {self.current_state}")
            print(f"Goal: {agent_input.goal}")
            print(f"Available tools: {[tool.name for tool in agent_input.available_tools]}")

        # Stage 1: Generate next_instruction and basic agent output
        prompt = self._construct_prompt(agent_input)
        
        if debug:
            print(f"Prompt length: {len(prompt)} characters")

        try:
            llm_output = await self.llm.generate(prompt)
            if debug:
                print(f"LLM Output: {llm_output[:500]}...")  # First 500 chars
            
            agent_output = self._parse_llm_output(llm_output)
            
        except Exception as e:
            if debug:
                print(f"Error generating LLM response: {e}")
            agent_output = AgentOutput(
                next_instruction="handle LLM error",
                current_result=f"Error communicating with LLM: {str(e)}",
                next_state=AgentState.ERROR,
                halt_condition=True,
                reasoning=f"LLM error: {str(e)}"
            )

        # Stage 2: 判断是否需要工具调用
        if not agent_output.halt_condition and agent_input.available_tools:
            if debug:
                print(f"Stage 2: Determining tool calls for instruction: {agent_output.next_instruction}")
            
            tool_calls = await self._determine_tool_calls(agent_input, agent_output)
            agent_output.tool_calls = tool_calls
            
            # Stage 3: 执行工具调用（如果有的话）
            if tool_calls:
                if debug:
                    print(f"Executing {len(tool_calls)} tool calls")
                agent_output = await self._execute_tool_calls(agent_input, agent_output, debug)

        # Update internal state
        self._update_state(agent_input, agent_output)

        if debug:
            print(f"Next state: {agent_output.next_state}")
            print(f"Halt condition: {agent_output.halt_condition}")
            if agent_output.tool_calls:
                print(f"Tool calls: {[tc.get('tool_name') for tc in agent_output.tool_calls]}")

        return agent_output

    async def run(self, agent_input: AgentInput, debug: bool = False) -> List[AgentOutput]:
        """Run the agent until halt condition"""

        outputs = []

        while not self.current_state == AgentState.HALTED:
            output = await self.step(agent_input, debug)
            outputs.append(output)

            if output.halt_condition:
                break

        return outputs
    
    async def _execute_tool_calls(self, agent_input: AgentInput, agent_output: AgentOutput, debug: bool = False) -> AgentOutput:
        """Stage 3: 执行具体的工具调用"""
        if not agent_output.tool_calls:
            return agent_output
        
        tool_results = []
        tools_used = []
        
        # 创建工具名称到工具对象的映射
        tool_map = {tool.name: tool for tool in agent_input.available_tools}
        
        for tool_call in agent_output.tool_calls:
            tool_name = tool_call.get("tool_name")
            parameters = tool_call.get("parameters", {})
            description = tool_call.get("description", "")
            
            if debug:
                print(f"Executing tool: {tool_name} with params: {parameters}")
            
            try:
                if tool_name in tool_map:
                    tool = tool_map[tool_name]
                    # 执行工具 - 首先调用方法，然后检查结果是否需要await
                    result = tool(**parameters)
                    
                    # 检查结果是否是awaitable（协程对象）
                    if inspect.isawaitable(result):
                        result = await result
                    
                    tool_results.append(f"Tool '{tool_name}' executed successfully:\n{result}")
                    tools_used.append(tool_name)
                    
                    if debug:
                        print(f"Tool '{tool_name}' result: {result}")
                else:
                    error_msg = f"Tool '{tool_name}' not found in available tools"
                    tool_results.append(error_msg)
                    if debug:
                        print(error_msg)
                        
            except Exception as e:
                error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                tool_results.append(error_msg)
                if debug:
                    print(error_msg)
        
        # 更新agent output with tool results
        if tool_results:
            original_result = agent_output.current_result or ""
            combined_result = f"{original_result}\n\nTool Execution Results:\n" + "\n".join(tool_results)
            
            # 检查是否有工具执行错误
            has_tool_errors = any("Error executing tool" in result for result in tool_results)
            
            # 如果有工具错误，设置agent状态为错误
            next_state = AgentState.ERROR if has_tool_errors else agent_output.next_state
            halt_condition = has_tool_errors or agent_output.halt_condition  # 错误时停止执行
            
            # 更新reasoning包含错误信息
            updated_reasoning = agent_output.reasoning
            if tools_used:
                updated_reasoning += f" [Used tools: {', '.join(set(tools_used))}]"
            if has_tool_errors:
                updated_reasoning += " [Tool execution failed - see results for details]"
            
            # 创建更新的agent output
            updated_output = AgentOutput(
                next_instruction=agent_output.next_instruction,
                action_params=agent_output.action_params,
                memory_updates=agent_output.memory_updates,
                plan_updates=agent_output.plan_updates,
                current_result=combined_result,
                next_state=next_state,
                halt_condition=halt_condition,
                confidence=0.1 if has_tool_errors else agent_output.confidence,  # 降低错误时的信心度
                reasoning=updated_reasoning,
                tool_calls=agent_output.tool_calls
            )
            return updated_output
        
        return agent_output

    async def _determine_tool_calls(self, agent_input: AgentInput, agent_output: AgentOutput) -> List[Dict[str, Any]]:
        """第二阶段：根据next_instruction确定是否需要工具调用，如果需要则生成具体的工具调用"""
        if not agent_input.available_tools:
            return []
        
        instruction = agent_output.next_instruction
        
        # 构建工具调用判断的提示词
        tools_info = ""
        for tool in agent_input.available_tools:
            tools_info += f"- **{tool.name}**: {tool.description}\n"
            if hasattr(tool, 'inputs') and tool.inputs:
                inputs_desc = ", ".join([f"{k}: {v.get('description', v.get('type', 'any'))}" for k, v in tool.inputs.items()])
                tools_info += f"  - Inputs: {inputs_desc}\n"
        
        tool_decision_prompt = f"""You are analyzing whether a task requires tool usage and generating the specific tool calls.

## Current Instruction: {instruction}

## Goal: {agent_input.goal}

## Available Tools:
{tools_info}

## Current Memory:
{agent_input.memory.working_memory if agent_input.memory.working_memory else "Empty"}

Please analyze the instruction and determine:
1. Does this instruction require using any of the available tools?
2. If yes, which specific tools and with what parameters?

Respond in JSON format:
{{
    "needs_tools": true/false,
    "reasoning": "why tools are or aren't needed",
    "tool_calls": [
        {{
            "tool_name": "exact_tool_name",
            "parameters": {{
                "param1": "value1",
                "param2": "value2"
            }},
            "description": "what this tool call accomplishes"
        }}
    ]
}}

If no tools are needed, set "needs_tools" to false and "tool_calls" to an empty array.
Only generate tool calls for actions that actually require external tools - not for simple analysis, reasoning, or text generation.
"""
        
        try:
            tool_response = await self.llm.generate(tool_decision_prompt)
            tool_json = self._extract_json_from_output(tool_response)
            tool_data = json.loads(tool_json)
            
            if tool_data.get("needs_tools", False):
                return tool_data.get("tool_calls", [])
            else:
                return []
                
        except Exception as e:
            # 如果工具调用判断失败，返回空列表，不影响主流程
            return []


class TuringMachineAgent(BaseAgent):
    """Integration of Turing Machine with existing BaseAgent architecture"""
    
    def __init__(self, 
                 name: str = "turing_machine_agent",
                 llm_config: Union[str, LLMConfig, BaseProvider] = None,
                 disable_docker: bool = True,  # 默认禁用Docker避免依赖问题
                 **kwargs):
        # 如果禁用Docker，不初始化Brain
        if disable_docker:
            # 手动设置属性而不调用父类的__post_init__
            self.name = name
            self.tools = kwargs.get("tools", [])
            self.brain = None  # 不使用Brain
            self.user_id = kwargs.get("user_id")
            self.agent_id = kwargs.get("agent_id", str(__import__('uuid').uuid4()))
            self.session_id = kwargs.get("session_id", str(__import__('uuid').uuid4()))
            self.max_steps = kwargs.get("max_steps", 20)
        else:
            super().__init__(name=name, **kwargs)
        
        # Create LLM interface
        self.llm_interface = MinionLLMInterface(llm_config)
        
        # Initialize Turing Machine
        self.turing_machine = AgentTuringMachine(self.llm_interface)
        
        # Agent state
        self.agent_memory = Memory()
        self.current_plan = None
        
    async def execute_step(self, input_data: Input, **kwargs) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step using the Turing Machine approach
        """
        # If we have a brain, use the parent method
        if self.brain is not None:
            return await super().execute_step(input_data, **kwargs)
        
        # Otherwise, use pure Turing Machine approach
        # Extract goal from input
        goal = input_data.query
        
        # Create or update plan if needed
        if self.current_plan is None:
            self.current_plan = Plan(goal=goal)
            # Add basic planning steps
            self.current_plan.add_step("analyze_goal", {"goal": goal})
            self.current_plan.add_step("execute_task")
            self.current_plan.add_step("finalize_result")
        
        # Create agent input
        agent_input = AgentInput(
            goal=goal,
            plan=self.current_plan,
            memory=self.agent_memory,
            prompt=input_data.query,
            context=kwargs,
            available_tools=self.tools
        )
        
        # Execute one step of the Turing Machine
        output = await self.turing_machine.step(agent_input, debug=kwargs.get("debug", False))
        
        # Convert to AgentResponse format
        response = output.current_result
        score = output.confidence
        terminated = output.halt_condition or output.next_state == AgentState.HALTED
        truncated = False
        info = {
            "instruction": output.next_instruction,
            "action_params": output.action_params,
            "state": output.next_state.value,
            "reasoning": output.reasoning,
            "step_count": self.turing_machine.step_count,
            "success": output.next_state != AgentState.ERROR,
            "error": output.reasoning if output.next_state == AgentState.ERROR else None
        }
        
        # 判断是否有错误
        success = output.next_state != AgentState.ERROR
        error_msg = None
        if not success:
            error_msg = output.reasoning or "Agent entered ERROR state"
        
        return AgentResponse(
            response=response,
            score=score,
            terminated=terminated,
            truncated=truncated,
            info=info,
            step_count=self.turing_machine.step_count,
            state=output.next_state,
            success=success,
            error=error_msg
        )
    
    def run(self, task: Union[str, Input], **kwargs) -> Any:
        """
        Override BaseAgent run method to handle the case without Brain
        
        Note: This is NOT async when streaming=True to return async generator directly
        """
        if self.brain is not None:
            # Use parent implementation if we have a brain (as async method)
            return super().run(task, **kwargs)
        
        # Handle the case without brain
        max_steps = kwargs.pop("max_steps", self.max_steps)
        streaming = kwargs.pop("streaming", False)
        
        if streaming:
            # Return the async generator directly (not awaited)
            return self._run_streaming_turing_machine(task, max_steps, kwargs)
        else:
            # Return a coroutine for non-streaming case
            return self._run_complete_turing_machine(task, max_steps, kwargs)
    
    async def _run_streaming_turing_machine(self, task, max_steps, kwargs):
        """Streaming execution using pure Turing Machine approach - async generator"""
        goal = task if isinstance(task, str) else task.query
        
        # Reset for new task
        self.reset()
        
        # Create initial plan
        if self.current_plan is None:
            self.current_plan = Plan(goal=goal)
            self.current_plan.add_step("analyze_goal", {"goal": goal})
            self.current_plan.add_step("execute_task")
            self.current_plan.add_step("finalize_result")
        
        # Create initial agent input
        agent_input = AgentInput(
            goal=goal,
            plan=self.current_plan,
            memory=self.agent_memory,
            prompt=goal,
            context=kwargs,
            available_tools=self.tools
        )
        
        step_count = 0
        previous_outputs = []  # Track previous outputs
        
        while step_count < max_steps:
            if self.turing_machine.current_state == AgentState.HALTED:
                break
                
            output = await self.turing_machine.step(agent_input, debug=kwargs.get("debug", False))
            previous_outputs.append(output)
            
            # Convert to BaseAgent format and yield
            response = output.current_result
            score = output.confidence
            terminated = output.halt_condition or output.next_state == AgentState.HALTED
            truncated = False
            
            # 检查是否有错误状态
            if output.next_state == AgentState.ERROR:
                terminated = True  # 错误时终止执行
            
            info = {
                "action": output.next_instruction,
                "action_params": output.action_params,
                "state": output.next_state.value,
                "reasoning": output.reasoning,
                "step_count": self.turing_machine.step_count,
                "success": output.next_state != AgentState.ERROR,
                "error": output.reasoning if output.next_state == AgentState.ERROR else None
            }
            
            result = (response, score, terminated, truncated, info)
            yield result
            
            if terminated or output.halt_condition:
                break
            
            # Update agent_input for next iteration with previous results
            agent_input = self._update_agent_input_with_history(
                agent_input, previous_outputs, goal
            )
            step_count += 1
        
        if step_count >= max_steps:
            # Provide better information about what was accomplished
            partial_result = f"Reached maximum steps limit ({max_steps})"
            if len(self.agent_memory.episodic_memory) > 0:
                partial_result += f". Completed {len(self.agent_memory.episodic_memory)} instructions."
                last_instruction = self.agent_memory.episodic_memory[-1].get("instruction", "unknown")
                partial_result += f" Last instruction: {last_instruction}"
            
            yield (
                partial_result, 
                0.5,  # score - medium confidence since we didn't complete
                False,  # terminated - not naturally terminated
                True,   # truncated - yes, we reached max steps
                {
                    "reason": "max_steps_reached",
                    "steps_completed": step_count,
                    "max_steps": max_steps,
                    "instructions_completed": len(self.agent_memory.episodic_memory),
                    "last_state": self.turing_machine.current_state.value
                }
            )
    
    async def _run_complete_turing_machine(self, task, max_steps, kwargs):
        """Complete execution using pure Turing Machine approach"""
        goal = task if isinstance(task, str) else task.query
        
        # Reset for new task
        self.reset()
        
        # Create initial plan
        if self.current_plan is None:
            self.current_plan = Plan(goal=goal)
            self.current_plan.add_step("analyze_goal", {"goal": goal})
            self.current_plan.add_step("execute_task")
            self.current_plan.add_step("finalize_result")
        
        # Create agent input
        agent_input = AgentInput(
            goal=goal,
            plan=self.current_plan,
            memory=self.agent_memory,
            prompt=goal,
            context=kwargs,
            available_tools=self.tools
        )
        
        step_count = 0
        final_result = None
        last_output = None
        previous_outputs = []  # Track previous outputs
        
        while step_count < max_steps:
            if self.turing_machine.current_state == AgentState.HALTED:
                break
                
            output = await self.turing_machine.step(agent_input, debug=kwargs.get("debug", False))
            last_output = output
            final_result = output.current_result
            previous_outputs.append(output)
            
            if output.halt_condition or output.next_state == AgentState.HALTED:
                break
            
            # Update agent_input for next iteration with previous results
            agent_input = self._update_agent_input_with_history(
                agent_input, previous_outputs, goal
            )
            step_count += 1
        
        # Handle max steps reached - return a proper result with context
        if step_count >= max_steps:
            # Try to provide a meaningful partial result
            if last_output and final_result:
                partial_result = f"Partial result after {max_steps} steps: {final_result}"
                if len(self.agent_memory.episodic_memory) > 0:
                    partial_result += f"\n\nProgress made: {len(self.agent_memory.episodic_memory)} instructions completed."
                return partial_result
            else:
                return f"Unable to complete task within {max_steps} steps. Please try increasing max_steps or simplifying the task."
            
        return final_result

    def _update_agent_input_with_history(self, agent_input: AgentInput, 
                                         previous_outputs: List[Any], goal: str) -> AgentInput:
        """Update agent input with tool execution results from previous steps"""
        
        # Build context from previous tool executions
        tool_history = ""
        if previous_outputs:
            recent_outputs = previous_outputs[-3:]  # Keep last 3 steps to avoid too long prompts
            for i, output in enumerate(recent_outputs):
                step_num = len(previous_outputs) - len(recent_outputs) + i + 1
                if output.current_result and "Tool Execution Results:" in output.current_result:
                    # Extract tool results from current_result
                    tool_results = output.current_result.split("Tool Execution Results:")[-1].strip()
                    tool_history += f"\nStep {step_num} - {tool_results}"
        
        # Create enhanced prompt with tool execution history
        if tool_history:
            updated_prompt = f"""Continue working towards: {goal}

## Previous Tool Execution Results:
{tool_history}

Please consider these tool results when planning your next action."""
        else:
            updated_prompt = f"Continue working towards: {goal}" if previous_outputs else goal
        
        # Create updated agent input
        return AgentInput(
            goal=goal,
            plan=agent_input.plan,
            memory=agent_input.memory,  # LLM manages memory via memory_updates
            prompt=updated_prompt,
            context=agent_input.context,
            external_input=agent_input.external_input,
            available_tools=agent_input.available_tools
        )


    def reset(self):
        """Reset the agent state"""
        self.turing_machine.current_state = AgentState.PLANNING
        self.turing_machine.step_count = 0
        self.agent_memory = Memory()
        self.current_plan = None


# Usage examples and factory functions
def create_turing_machine_agent(model_name: str = "default", **kwargs) -> TuringMachineAgent:
    """
    Factory function to create a TuringMachineAgent with specified model
    
    Args:
        model_name: Name of the model in config.models, or None for default
        **kwargs: Additional arguments for TuringMachineAgent
    
    Returns:
        TuringMachineAgent instance
    """
    return TuringMachineAgent(llm_config=model_name, **kwargs)


async def demo_turing_machine():
    """Demo function showing how to use the Turing Machine Agent"""
    
    # Create agent with default LLM
    agent = create_turing_machine_agent()
    
    # Create initial state
    memory = Memory()
    plan = Plan(goal="Research latest AI developments")
    plan.add_step("search_web", {"query": "AI research 2024"})
    plan.add_step("analyze_results")
    plan.add_step("summarize_findings")

    agent_input = AgentInput(
        goal="Find and summarize the latest AI research developments",
        plan=plan,
        memory=memory,
        prompt="User wants to know about recent AI breakthroughs"
    )

    # Run one step
    output = await agent.turing_machine.step(agent_input, debug=True)
    print("Output:", output)
    
    # Or use the BaseAgent interface
    task_input = Input(query="Research latest AI developments and provide a summary")
    result = await agent.step(task_input, debug=True)
    print("BaseAgent result:", result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_turing_machine()) 