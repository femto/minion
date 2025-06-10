from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, AsyncIterator, Tuple
from enum import Enum
import json
import re
from abc import ABC, abstractmethod

from ..providers.base_provider import BaseProvider
from ..providers.llm_provider_registry import llm_registry
from ..configs.config import config, LLMConfig
from ..main.input import Input
from .base_agent import BaseAgent


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


@dataclass
class AgentOutput:
    """Output from the Turing Machine at each step"""
    next_action: str
    action_params: Dict[str, Any] = field(default_factory=dict)
    memory_updates: Dict[str, Any] = field(default_factory=dict)
    plan_updates: Optional[Plan] = None
    current_result: Any = None
    next_state: AgentState = AgentState.EXECUTING
    halt_condition: bool = False
    confidence: float = 1.0
    reasoning: str = ""


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

        # Construct comprehensive prompt
        prompt = f"""You are a Turing Machine Agent in state: {self.current_state.value}

## Task Goal: {agent_input.goal}

## Current Context: {agent_input.prompt}
{plan_info}{memory_info}

Please analyze the situation and determine your next action. Consider:
1. Current state and goal
2. Your existing working memory and what you've learned so far
3. What action would best progress toward the goal
4. Whether you need to transition to a different state  
5. How to synthesize your previous memory with this step's results into an updated summary
6. Whether the task is complete and you should halt execution
7. If you're repeating similar actions, provide the actual final answer instead

IMPORTANT: If the task asks for code, explanations, calculations, or specific content - provide the ACTUAL result in current_result, not just descriptions of what you plan to do. Avoid repetitive planning - move to concrete output.

Available states: planning, executing, reflecting, waiting, halted, error

Preferred JSON format:
{{
    "reasoning": "explanation of your decision",
    "next_action": "action_name", 
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
                next_action="error",
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
                next_action=data.get("next_action", "wait"),
                action_params=data.get("action_params", {}),
                memory_updates=data.get("memory_updates", {}),
                plan_updates=data.get("plan_updates"),
                current_result=data.get("current_result"),
                next_state=AgentState(data.get("next_state", "executing")),
                halt_condition=data.get("halt_condition", False),
                confidence=data.get("confidence", 1.0),
                reasoning=data.get("reasoning", "")
            )
        except json.JSONDecodeError:
            # If it's not JSON, try to handle as plain text
            return self._handle_non_json_output(output)
        except (ValueError, KeyError) as e:
            # Handle other parsing errors
            return AgentOutput(
                next_action="error",
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
        """Handle non-JSON output from LLM"""
        # If the output looks like a regular response, treat it as the result
        if len(output.strip()) > 10:  # Has some meaningful content
            return AgentOutput(
                next_action="respond",
                current_result=output.strip(),
                next_state=AgentState.HALTED,
                halt_condition=True,
                confidence=0.7,
                reasoning="LLM provided non-JSON response, treating as final answer"
            )
        else:
            return AgentOutput(
                next_action="error",
                current_result="LLM provided unclear response. Please check your API configuration.",
                next_state=AgentState.ERROR,
                halt_condition=True,
                reasoning="Unclear LLM response"
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
            "action": agent_output.next_action,
            "result": agent_output.current_result,
            "confidence": agent_output.confidence
        }
        agent_input.memory.add_episode(episode)

        # Update plan
        if agent_output.plan_updates:
            agent_input.plan = agent_output.plan_updates
        elif agent_output.next_action == "advance_plan":
            agent_input.plan.advance_step()

        # Update state
        self.current_state = agent_output.next_state
        self.step_count += 1

    async def step(self, agent_input: AgentInput, debug: bool = False) -> AgentOutput:
        """Execute one step of the Turing Machine"""

        if self.step_count >= self.max_steps:
            return AgentOutput(
                next_action="halt",
                current_result="Maximum steps reached",
                next_state=AgentState.HALTED,
                halt_condition=True
            )

        # Construct prompt
        prompt = self._construct_prompt(agent_input)

        if debug:
            print(f"Step {self.step_count} - State: {self.current_state}")
            print("Prompt:", prompt[:200] + "..." if len(prompt) > 200 else prompt)

        # Get LLM response with error handling
        try:
            llm_response = await self.llm.generate(prompt, agent_input.context)
            if debug:
                print(f"LLM Response: {llm_response[:100]}..." if len(str(llm_response)) > 100 else f"LLM Response: {llm_response}")
        except Exception as e:
            if debug:
                print(f"LLM Error: {e}")
            # Create error response
            agent_output = AgentOutput(
                next_action="error",
                current_result=f"LLM API Error: {str(e)}. Please check your API configuration.",
                next_state=AgentState.ERROR,
                halt_condition=True,
                reasoning=f"LLM API failed: {str(e)}"
            )
            self._update_state(agent_input, agent_output)
            return agent_output

        # Parse output
        agent_output = self._parse_llm_output(llm_response)

        # Update state
        self._update_state(agent_input, agent_output)

        if debug:
            print(f"Action: {agent_output.next_action}")
            print(f"Result: {agent_output.current_result}")
            print(f"Next State: {agent_output.next_state}")
            print("-" * 50)

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
            context=kwargs
        )
        
        # Execute one step of the Turing Machine
        output = await self.turing_machine.step(agent_input, debug=kwargs.get("debug", False))
        
        # Convert to BaseAgent expected format
        response = output.current_result
        score = output.confidence
        terminated = output.halt_condition or output.next_state == AgentState.HALTED
        truncated = False
        info = {
            "action": output.next_action,
            "action_params": output.action_params,
            "state": output.next_state.value,
            "reasoning": output.reasoning,
            "step_count": self.turing_machine.step_count
        }
        
        return response, score, terminated, truncated, info
    
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
            context=kwargs
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
            info = {
                "action": output.next_action,
                "action_params": output.action_params,
                "state": output.next_state.value,
                "reasoning": output.reasoning,
                "step_count": self.turing_machine.step_count
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
                partial_result += f". Completed {len(self.agent_memory.episodic_memory)} actions."
                last_action = self.agent_memory.episodic_memory[-1].get("action", "unknown")
                partial_result += f" Last action: {last_action}"
            
            yield (
                partial_result, 
                0.5,  # score - medium confidence since we didn't complete
                False,  # terminated - not naturally terminated
                True,   # truncated - yes, we reached max steps
                {
                    "reason": "max_steps_reached",
                    "steps_completed": step_count,
                    "max_steps": max_steps,
                    "actions_completed": len(self.agent_memory.episodic_memory),
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
            context=kwargs
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
                    partial_result += f"\n\nProgress made: {len(self.agent_memory.episodic_memory)} actions completed."
                return partial_result
            else:
                return f"Unable to complete task within {max_steps} steps. Please try increasing max_steps or simplifying the task."
            
        return final_result

    def _update_agent_input_with_history(self, agent_input: AgentInput, 
                                         previous_outputs: List[Any], goal: str) -> AgentInput:
        """Update agent input - memory is now managed by LLM via memory_updates"""
        
        # Simple prompt since LLM manages its own memory now
        if previous_outputs:
            updated_prompt = f"Continue working towards: {goal}"
        else:
            updated_prompt = goal
        
        # Create updated agent input - memory is updated by LLM's memory_updates
        return AgentInput(
            goal=goal,
            plan=agent_input.plan,
            memory=agent_input.memory,  # LLM manages memory via memory_updates
            prompt=updated_prompt,
            context=agent_input.context,
            external_input=agent_input.external_input
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