from typing import Dict, Any, List, Optional, Union, AsyncGenerator
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import inspect

from .base_agent import BaseAgent
from ..main.input import Input
from ..main.action_step import StreamChunk
from ..tools.base_tool import BaseTool
from ..schema.message_types import ToolCall
from ..providers import create_llm_provider
from .. import config
from ..exceptions import FinalAnswerException
from minion.types.agent_response import AgentResponse

logger = logging.getLogger(__name__)


class MinionToolCallingAgent(BaseAgent):
    """
    Minion project adaptation of smolagents ToolCallingAgent.
    
    This agent uses direct tool calls with LLM's tool calling capabilities,
    implementing the smolagents pattern of detecting final_answer by tool name
    rather than relying on FinalAnswerException.
    """
    
    def __init__(self, 
                 name: str = "minion_tool_calling_agent",
                 tools: List[BaseTool] = None,
                 llm=None,
                 model: str = "default",
                 max_tool_threads: Optional[int] = None,
                 stream_outputs: bool = False,
                 **kwargs):
        """
        Initialize the MinionToolCallingAgent
        
        Args:
            tools: List of tools available to the agent
            llm: LLM instance (if None, will create from model config)
            model: Model name from config.yaml models section (default: "default")
            max_tool_threads: Maximum number of threads for parallel tool calls
            stream_outputs: Whether to stream outputs during execution
            **kwargs: Additional arguments passed to BaseAgent
        """
        super().__init__(name=name, tools=tools or [], **kwargs)
        
        # LLM setup - follow Brain pattern
        if llm is not None:
            self.llm = llm
        else:
            # Get model config and create LLM provider
            model_config = config.models.get(model)
            if model_config is None:
                raise ValueError(f"Model '{model}' not found in config. Available models: {list(config.models.keys())}")
            self.llm = create_llm_provider(model_config)
        
        self.model = model
        
        # Tool calling setup
        self.max_tool_threads = max_tool_threads
        self.stream_outputs = stream_outputs
        
    async def setup(self):
        """Setup agent with tools"""
        await super().setup()
        logger.info(f"MinionToolCallingAgent {self.name} setup completed with {len(self.tools)} tools, using model: {self.model}")
    
    @property
    def tools_and_managed_agents(self):
        """Returns a combined list of tools and managed agents."""
        # For now, just return tools. Could be extended for managed agents later
        return self.tools
    
    def _format_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Format tools for LLM tool calling API"""
        formatted_tools = []
        
        for tool in self.tools:
            if hasattr(tool, 'name') and hasattr(tool, 'description'):
                # Get tool schema
                if hasattr(tool, 'inputs') and isinstance(tool.inputs, dict):
                    # Use inputs directly if available
                    parameters = {
                        "type": "object",
                        "properties": tool.inputs,
                        "required": [
                            name for name, param in tool.inputs.items() 
                            if not param.get("nullable", False)
                        ]
                    }
                elif hasattr(tool, 'get_schema'):
                    # Use get_schema method
                    schema = tool.get_schema()
                    if isinstance(schema, dict) and "function" in schema:
                        formatted_tools.append(schema)
                        continue
                    else:
                        parameters = schema.get("parameters", {"type": "object", "properties": {}})
                else:
                    # Generate basic schema
                    parameters = {"type": "object", "properties": {}}
                
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": parameters
                    }
                }
                formatted_tools.append(tool_def)
        
        return formatted_tools
    
    async def execute_step(self, state: Dict[str, Any], stream: bool = False, **kwargs):
        """
        Execute a single step using direct tool calling approach from smolagents
        """
        input_obj = state["input"]
        if not isinstance(input_obj, Input):
            input_obj = Input(query=str(input_obj))
            
        # Convert Input to messages format
        messages = [{"role": "user", "content": input_obj.query}]
        
        # Add conversation history if available
        history = state.get("history", [])
        if history:
            # Add previous interactions to messages
            for item in history[-3:]:  # Keep last 3 interactions
                if hasattr(item, 'raw_response'):
                    messages.append({"role": "assistant", "content": str(item.raw_response)})
        
        if stream:
            # Return the async generator directly for streaming
            return self._execute_step_stream(state, **kwargs)
        else:
            return await self._execute_step_sync(messages, state)
    
    async def _execute_step_sync(self, messages: List[Dict[str, Any]], state: Dict[str, Any]) -> AgentResponse:
        """Execute step synchronously"""
        # Format tools for LLM
        formatted_tools = self._format_tools_for_llm()
        
        # Call LLM with tools
        try:
            if formatted_tools:
                response = await self.llm.generate(
                    messages,
                    tools=formatted_tools,
                    tool_choice="auto"
                )
            else:
                response = await self.llm.generate(messages)
                
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return AgentResponse(
                answer=f"Error: LLM generation failed: {e}",
                raw_response=f"Error: {e}",
                terminated=False,
                truncated=False,
                info={"error": str(e)}
            )
        
        # Extract message from response
        if hasattr(response, 'choices') and response.choices:
            message = response.choices[0].message
        else:
            return AgentResponse(
                answer=str(response),
                raw_response=str(response),
                terminated=False,
                truncated=False,
                info={}
            )
        
        # Check for tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            return await self._process_tool_calls_sync(message.tool_calls, message.content or "")
        else:
            # No tool calls, return response
            content = message.content or ""
            return AgentResponse(
                answer=content,
                raw_response=content,
                terminated=False,
                truncated=False,
                info={}
            )
    
    async def _execute_step_stream(self, state: Dict[str, Any], **kwargs) -> AsyncGenerator[StreamChunk, None]:
        """Execute step with streaming - returns async generator"""
        input_obj = state["input"]
        if not isinstance(input_obj, Input):
            input_obj = Input(query=str(input_obj))
            
        # Convert Input to messages format
        messages = [{"role": "user", "content": input_obj.query}]
        
        # Add conversation history if available
        history = state.get("history", [])
        if history:
            # Add previous interactions to messages
            for item in history[-3:]:  # Keep last 3 interactions
                if hasattr(item, 'raw_response'):
                    messages.append({"role": "assistant", "content": str(item.raw_response)})
        
        formatted_tools = self._format_tools_for_llm()
        
        try:
            if formatted_tools:
                stream = self.llm.generate_stream(
                    messages,
                    tools=formatted_tools,
                    tool_choice="auto"
                )
            else:
                stream = self.llm.generate_stream(messages)
                
            full_content = ""
            tool_calls = []
            
            # Process streaming response
            async for chunk in stream:
                if hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                    full_content += content
                    yield StreamChunk(
                        content=content,
                        chunk_type="text",
                        metadata={}
                    )
                elif hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    # Collect tool calls
                    for tool_call in chunk.tool_calls:
                        tool_calls.append(tool_call)
                        yield StreamChunk(
                            content=f"\n🔧 Calling tool: {tool_call.function.name}\n",
                            chunk_type="tool_call",
                            metadata={"tool_call": tool_call}
                        )
                        
            # Process tool calls if any
            if tool_calls:
                async for tool_chunk in self._process_tool_calls_stream(tool_calls, full_content):
                    yield tool_chunk
                    
        except Exception as e:
            logger.error(f"Streaming execution failed: {e}")
            yield StreamChunk(
                content=f"Error: {e}\n",
                chunk_type="error",
                metadata={"error": str(e)}
            )
    
    async def _process_tool_calls_sync(self, tool_calls: List[Any], content: str) -> AgentResponse:
        """Process tool calls synchronously and return final response"""
        results = []
        is_final_answer = False
        final_answer_result = None
        
        # Process tool calls in parallel or sequentially
        if len(tool_calls) == 1:
            # Single tool call
            tool_call = tool_calls[0]
            result = await self._execute_single_tool_call(tool_call)
            results.append(result)
            
            # Check if this is final_answer
            if tool_call.function.name == "final_answer":
                is_final_answer = True
                final_answer_result = result.get("result")
                
        else:
            # Multiple tool calls - process in parallel
            with ThreadPoolExecutor(self.max_tool_threads) as executor:
                futures = [
                    executor.submit(asyncio.run, self._execute_single_tool_call(tool_call))
                    for tool_call in tool_calls
                ]
                
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    
                    # Check if any tool call is final_answer
                    if result.get("tool_name") == "final_answer":
                        is_final_answer = True
                        final_answer_result = result.get("result")
        
        # Build response
        if is_final_answer:
            # Return final answer
            answer = final_answer_result if final_answer_result is not None else "Task completed"
            return AgentResponse(
                answer=str(answer),
                raw_response=str(answer),
                terminated=True,  # This is the key - set terminated=True for final_answer
                truncated=False,
                info={"is_final_answer": True, "tool_results": results}
            )
        else:
            # Return tool execution results
            result_text = content
            for result in results:
                result_text += f"\n Tool {result['tool_name']} result: {result['result']}"
                
            return AgentResponse(
                answer=result_text,
                raw_response=result_text,
                terminated=False,
                truncated=False,
                info={"tool_results": results}
            )
    
    async def _process_tool_calls_stream(self, tool_calls: List[Any], content: str) -> AsyncGenerator[StreamChunk, None]:
        """Process tool calls with streaming output"""
        is_final_answer = False
        final_answer_result = None
        
        for tool_call in tool_calls:
            # Execute tool call
            result = await self._execute_single_tool_call(tool_call)
            
            # Yield tool result
            yield StreamChunk(
                content=f"📊 Tool {result['tool_name']} result: {result['result']}\n",
                chunk_type="tool_response",
                metadata={
                    "tool_name": result['tool_name'],
                    "tool_result": result['result']
                }
            )
            
            # Check if this is final_answer
            if tool_call.function.name == "final_answer":
                is_final_answer = True
                final_answer_result = result.get("result")
                
                # Yield final answer indication
                yield StreamChunk(
                    content=f"\n✅ Final Answer: {final_answer_result}\n",
                    chunk_type="final_answer",
                    metadata={
                        "is_final_answer": True,
                        "final_answer": final_answer_result
                    }
                )
                break  # Stop processing more tools after final_answer
        
        # If we found final_answer, indicate completion
        if is_final_answer:
            yield StreamChunk(
                content="[TASK_COMPLETED]\n",
                chunk_type="completion",
                metadata={"terminated": True}
            )
    
    async def _execute_single_tool_call(self, tool_call: Any) -> Dict[str, Any]:
        """Execute a single tool call"""
        tool_name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
        except json.JSONDecodeError:
            args = {}
        
        # Find the tool
        target_tool = None
        for tool in self.tools:
            if hasattr(tool, 'name') and tool.name == tool_name:
                target_tool = tool
                break
        
        if not target_tool:
            return {
                "tool_name": tool_name,
                "result": f"Error: Tool '{tool_name}' not found",
                "success": False
            }
        
        try:
            # Execute the tool
            if hasattr(target_tool, 'execute'):
                result = target_tool.execute(**args)
            elif hasattr(target_tool, 'forward'):
                # Handle tools with forward method
                result = target_tool.forward(**args)
            elif callable(target_tool):
                result = target_tool(**args)
            else:
                result = f"Error: Tool '{tool_name}' is not callable"
            
            # Handle async results
            if inspect.iscoroutine(result):
                result = await result
                
            return {
                "tool_name": tool_name,
                "result": result,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            return {
                "tool_name": tool_name,
                "result": f"Error executing {tool_name}: {str(e)}",
                "success": False
            }
    
    def is_done(self, result: Any, state: Dict[str, Any]) -> bool:
        """
        Override BaseAgent.is_done to properly detect final_answer completion
        """
        # First check parent implementation
        if super().is_done(result, state):
            return True
            
        # Check for our specific final_answer indication
        if isinstance(result, AgentResponse):
            return result.terminated or result.info.get("is_final_answer", False)
        
        return False


# Helper function to create a properly configured tool calling agent
def create_tool_calling_agent(
    tools: List[BaseTool],
    name: str = "tool_calling_agent",
    model: str = "default",
    llm=None,
    **kwargs
) -> MinionToolCallingAgent:
    """
    Create a MinionToolCallingAgent with proper setup
    
    Args:
        tools: List of tools to provide to the agent
        name: Agent name
        model: Model name from config.yaml models section (default: "default")
        llm: LLM instance (if None, will create from model config)
        **kwargs: Additional arguments
        
    Returns:
        Configured MinionToolCallingAgent
    """
    agent = MinionToolCallingAgent(
        name=name,
        tools=tools,
        model=model,
        llm=llm,
        **kwargs
    )
    
    return agent