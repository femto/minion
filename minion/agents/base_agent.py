from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import uuid
import asyncio
import logging
import inspect

from ..providers import BaseProvider
from ..tools.base_tool import BaseTool
from ..main.brain import Brain
from ..main.input import Input
from ..main.action_step import ActionStep, StreamChunk, StreamingActionManager
from minion.types.agent_response import AgentResponse
from minion.types.agent_state import AgentState

logger = logging.getLogger(__name__)


@dataclass
class BaseAgent:
    """Agent基类，定义所有Agent的基本接口，支持生命周期管理"""
    
    name: str = "base_agent"
    tools: List[BaseTool] = field(default_factory=list)
    brain: Optional[Brain] = None
    llm: Optional[Union[BaseProvider, str]] = None  # LLM provider or model name to pass to Brain
    system_prompt: Optional[str] = None  # 系统提示

    state: AgentState = field(default_factory=AgentState)
    user_id: Optional[str] = None
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    max_steps: int = 20
    
    # 生命周期管理
    _is_setup: bool = field(default=False, init=False)
    _toolsets: List[Any] = field(default_factory=list, init=False)  # List of toolset instances (MCP, UTCP, etc.)
    
    # 流式输出管理
    _streaming_manager: StreamingActionManager = field(default_factory=StreamingActionManager, init=False)
    
    def __post_init__(self):
        """初始化后的处理"""
        # Set agent reference in state
        if self.state and not self.state.agent:
            self.state.agent = self
            
        # Automatically handle toolset objects in tools parameter
        # not quite useful
        # current just for setting self._toolsets
        # and ensure await self._toolsets.ensure_setup() in setup()
        self._extract_toolsets_from_tools()


    @classmethod
    async def create(cls, *args, **kwargs) :
        """
        异步创建并设置实例
        
        Args:
            *args: 传递给构造函数的位置参数
            **kwargs: 传递给构造函数的关键字参数
            
        Returns:
            instance: 已设置完成的实例
        """
        instance = cls(*args, **kwargs)
        await instance.setup()
        return instance

    #what does this method do, not quite useful?
    def _extract_toolsets_from_tools(self):
        """
        Extract toolset objects from tools parameter and move them to _toolsets.
        This enables direct passing of toolset objects (MCP, UTCP, etc.) in the tools parameter.
        """
        if self._is_setup:
            raise RuntimeError("Cannot modify toolsets after setup")
            
        # Check if any tools are toolset objects (MCP, UTCP, etc.)
        toolsets = []
        regular_tools = []
        
        for tool in self.tools:
            # Check if it's a toolset object (has setup methods and connection/config params)
            if (hasattr(tool, 'ensure_setup') and hasattr(tool, 'connection_params')) or \
               (hasattr(tool, 'ensure_setup') and hasattr(tool, 'config')):
                toolsets.append(tool)
            else:
                regular_tools.append(tool)
        
        # Update the tools list to only contain regular tools
        self.tools = regular_tools #will add toolsets later if toolsets are healthy
        
        # Add toolset objects to _toolsets
        for toolset in toolsets:
            self._toolsets.append(toolset)
            logger.info(f"Auto-detected toolset {getattr(toolset, 'name', 'unnamed')} from tools parameter")
    
    async def setup(self):
        """Setup agent with tools"""
        # Prevent duplicate setup
        if self._is_setup:
            return
            
        # Setup toolsets (MCP, UTCP, etc.)
        for toolset in self._toolsets:
            try:
                await toolset.ensure_setup()
                if not toolset.is_healthy:
                    logger.warning(f"Toolset {toolset.name} failed to setup: {toolset.setup_error}")
            except Exception as e:
                logger.error(f"Failed to setup toolset {toolset.name}: {e}")

        # Get tools from healthy toolsets and merge into self.tools
        toolset_tools = []
        for toolset in self._toolsets:
            if toolset.is_healthy:
                toolset_tools.extend(toolset.get_tools())
            else:
                logger.warning(f"Skipping unhealthy toolset {toolset.name}")
        
        # Merge toolset tools into self.tools
        if toolset_tools:
            self.tools.extend(toolset_tools)
            logger.info(f"Added {len(toolset_tools)} toolset tools to agent")

        # Auto-convert raw functions to appropriate tool types
        self._convert_raw_functions_to_tools()
        
        # Wrap state-aware tools to automatically pass agent state
        logger.info("About to wrap state-aware tools...")
        self._wrap_state_aware_tools()
        logger.info("Finished wrapping state-aware tools")

        # Initialize brain with tools
        if self.brain is None:
            #we don't pass tools to brain, instead we
            #pass agent.tools when run/run_sync to brain.step
            #this way we can easily refresh tools on agent
            brain_kwargs = {'tools': []}
            if self.llm is not None:
                brain_kwargs['llm'] = self.llm
                brain_kwargs['state'] = self.state
            self.brain = Brain(**brain_kwargs)
        
        # Mark agent as setup
        self._is_setup = True
    
    async def close(self):
        """
        Agent清理关闭，在停止使用agent时调用
        这里会清理所有的toolset和其他资源
        """
        if not self._is_setup:
            logger.warning(f"Agent {self.name} not setup, skipping cleanup")
            return
        
        logger.info(f"Closing agent {self.name}")
        
        # 清理所有toolsets
        for toolset in self._toolsets:
            try:
                await toolset.close()
                logger.info(f"Closed toolset {getattr(toolset, 'name', 'unnamed')}")
            except Exception as e:
                logger.error(f"Error closing toolset {getattr(toolset, 'name', 'unnamed')}: {e}")
        
        # 清理toolset相关的工具
        self.tools = [tool for tool in self.tools if not self._is_toolset_tool(tool)]
        self._toolsets.clear()
        
        self._is_setup = False
        logger.info(f"Agent {self.name} cleanup completed")
    
    def _convert_raw_functions_to_tools(self):
        """
        自动将原始函数转换为相应的工具类型
        - 同步函数转换为BaseTool
        - 异步函数转换为AsyncBaseTool
        """
        from ..tools.tool_decorator import tool
        from ..tools.async_base_tool import AsyncBaseTool
        
        converted_tools = []
        conversion_count = 0
        
        for item in self.tools:
            # 检查是否是原始函数（不是工具实例）
            # 使用更通用的判断：如果是可调用对象但没有工具的基本属性，则认为是原始函数
            if callable(item) and not (hasattr(item, 'name') and hasattr(item, 'description')):
                try:
                    # 使用统一的tool装饰器进行转换
                    converted_tool = tool(item)
                    converted_tools.append(converted_tool)
                    conversion_count += 1
                    
                    # 记录转换信息
                    tool_type = "AsyncBaseTool" if isinstance(converted_tool, AsyncBaseTool) else "BaseTool"
                    logger.info(f"Auto-converted function '{item.__name__}' to {tool_type}")
                    
                except Exception as e:
                    logger.warning(f"Failed to convert function '{getattr(item, '__name__', str(item))}' to tool: {e}")
                    # 保留原始函数，不进行转换
                    converted_tools.append(item)
            else:
                # 保留已经是工具实例或具有工具属性的项目
                converted_tools.append(item)
        
        # 更新工具列表
        self.tools = converted_tools
        
        if conversion_count > 0:
            logger.info(f"Successfully auto-converted {conversion_count} raw functions to tools")
    
    def _wrap_state_aware_tools(self):
        """
        包装需要state的工具，使其能够接收agent的state
        """
        from ..tools.base_tool import BaseTool
        from ..tools.async_base_tool import AsyncBaseTool
        import asyncio
        
        wrapped_tools = []
        wrap_count = 0
        
        for tool in self.tools:
            if hasattr(tool, 'needs_state') and tool.needs_state:
                # 创建包装器
                tool_type = type(tool).__name__
                is_async = isinstance(tool, AsyncBaseTool)
                is_base = isinstance(tool, BaseTool)
                print(f"DEBUG: Wrapping tool {tool.name}: type={tool_type}, is_async={is_async}, is_base={is_base}")
                print(f"DEBUG: Tool MRO: {[cls.__name__ for cls in type(tool).__mro__]}")
                
                if isinstance(tool, AsyncBaseTool):
                    print(f"DEBUG: Using ASYNC wrapper for {tool.name}")
                    # 异步工具包装器 - 使用默认参数来捕获变量
                    def create_async_wrapper(original_forward, agent_ref):
                        async def wrapped_async_forward(self_tool, *args, **kwargs):
                            # 获取agent的state
                            agent_state = getattr(agent_ref, 'state', None)
                            # 将state作为关键字参数传递，这样不依赖于参数位置
                            return await original_forward(self_tool, *args, state=agent_state, **kwargs)
                        return wrapped_async_forward
                    
                    wrapper = create_async_wrapper(tool.forward, self)
                    tool.forward = wrapper.__get__(tool, type(tool))
                    
                elif isinstance(tool, BaseTool):
                    print(f"DEBUG: Using SYNC wrapper for {tool.name}")
                    # 同步工具包装器 - 使用默认参数来捕获变量
                    def create_sync_wrapper(original_forward, agent_ref):
                        def wrapped_sync_forward(self_tool, *args, **kwargs):
                            # 获取agent的state
                            agent_state = getattr(agent_ref, 'state', None)
                            # 将state作为第一个位置参数传递，不传递self_tool
                            return original_forward(agent_state, *args, **kwargs)
                        return wrapped_sync_forward
                    
                    wrapper = create_sync_wrapper(tool.forward, self)
                    tool.forward = wrapper.__get__(tool, type(tool))
                else:
                    print(f"DEBUG: Unknown tool type for {tool.name}: {type(tool)}")
                
                wrap_count += 1
                logger.info(f"Successfully wrapped state-aware tool: {tool.name}")
            
            wrapped_tools.append(tool)
        
        # 更新工具列表
        self.tools = wrapped_tools
        
        if wrap_count > 0:
            logger.info(f"Successfully wrapped {wrap_count} state-aware tools")

    def _is_toolset_tool(self, tool: BaseTool) -> bool:
        """检查工具是否是toolset工具"""
        return tool.__class__.__name__ in ['AsyncMcpTool', 'AsyncUtcpTool']
    
    async def __aenter__(self):
        """支持async context manager"""
        await self.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持async context manager"""
        await self.close()
    

    
    @property
    def is_setup(self) -> bool:
        """检查agent是否已设置"""
        return self._is_setup
    
    def _ensure_setup(self):
        """确保agent已设置"""
        if not self._is_setup:
            raise RuntimeError(f"Agent {self.name} not setup. Call setup() first.")

    def run(self, 
           task: Optional[Union[str, Input]] = None,
           state: Optional[AgentState] = None, 
           max_steps: Optional[int] = None,
           reset: bool = False,
           **kwargs) -> Any:
        """
        Synchronous interface for running the agent.
        
        Args:
            task: Task description or Input object (required if state is None)
            state: Existing state for resuming interrupted execution
            max_steps: Maximum number of steps
            reset: If True, reset the agent state before execution
            **kwargs: Additional parameters
            
        Returns:
            Final task result
        """
        import asyncio
        return asyncio.run(self.run_async(task=task, state=state, max_steps=max_steps, reset=reset, stream=False, **kwargs))

    async def run_async(self, 
                       task: Optional[Union[str, Input]] = None,
                       state: Optional[AgentState] = None, 
                       max_steps: Optional[int] = None,
                       reset: bool = False,
                       stream: bool = False,
                       **kwargs) -> Any:
        """
        运行完整任务，自动多步执行直到完成，支持从中断状态恢复
        
        Args:
            task: 任务描述或Input对象 (state为None时必须提供)
            state: 已有状态，用于恢复中断的执行 (强类型AgentState)
            max_steps: 最大步数
            reset: If True, reset the agent state before execution
            stream: 若为True则使用异步迭代器返回中间结果
            **kwargs: 附加参数，可包含:
                - tools: 临时工具覆盖
                - 其他参数会传递给brain.step
                
        Returns:
            最终任务结果
        """
        self._ensure_setup()
        
        # 处理参数
        streaming = stream
        
        # 处理状态初始化或恢复
        if state is None:
            if task is None:
                raise ValueError("Either 'task' or 'state' must be provided")
            # 初始化新状态
            self._init_state_from_task(task, **kwargs)
        else:
            # 使用已有状态
            self.state = state
                
            # 可选择更新task
            if task is not None:
                if isinstance(task, str):
                    self.state.task = task
                    # 更新input对象的query
                    if self.state.input and hasattr(self.state.input, 'query'):
                        self.state.input.query = task
                else:
                    self.state.task = task.query
                    self.state.input = task
        
        # 确定最大步数
        max_steps = max_steps or self.max_steps
        
        if stream:
            # 设置 stream_outputs 属性，供 UI 使用
            self.stream_outputs = True
            # 返回异步迭代器
            return self._run_stream(state, max_steps, kwargs)
        else:
            # 清除 stream_outputs 属性
            self.stream_outputs = False
            # 一次性执行完成返回最终结果
            return await self._run_complete(state, max_steps, kwargs)

    async def run_stream(self, 
                        task: Optional[Union[str, Input]] = None,
                        state: Optional[Dict[str, Any]] = None, 
                        max_steps: Optional[int] = None,
                        **kwargs):
        """
        Streaming interface for running the agent.
        
        Args:
            task: Task description or Input object (required if state is None)
            state: Existing state for resuming interrupted execution
            max_steps: Maximum number of steps
            **kwargs: Additional parameters
            
        Returns:
            AsyncGenerator: Stream of responses
        """
        # Force stream=True for this method
        return await self.run_async(task=task, state=state, max_steps=max_steps, stream=True, **kwargs)
            
    async def _run_stream(self, state, max_steps, kwargs):
        """返回一个异步迭代器，逐步执行并返回中间结果"""
        step_count = 0
        
        while step_count < max_steps:
            # 开始新的步骤
            action_step = self._streaming_manager.start_step(
                step_type="reasoning",
                input_query=state.get("input", {}).get("query", "") if isinstance(state.get("input"), dict) else str(state.get("input", ""))
            )
            
            # yield 步骤开始信息
            yield StreamChunk(
                content=f"[STEP {step_count + 1}] Starting reasoning...\n",
                chunk_type="step_start",
                metadata={"step_number": step_count + 1, "step_id": action_step.step_id}
            )
            
            # 执行步骤并流式输出
            async for chunk in self._execute_step_stream(state, **kwargs):
                action_step.add_chunk(chunk)
                yield chunk
                if hasattr(chunk,'is_final_answer') and chunk.is_final_answer:
                    action_step.is_final_answer = True
            
            # 完成步骤
            result = action_step.to_agent_response()
            
            # 检查是否完成
            if self.is_done(result, state):
                action_step.is_final_answer = True
                self._streaming_manager.complete_current_step(is_final_answer=True)
                
                yield StreamChunk(
                    content=f"[FINAL] Task completed!\n",
                    chunk_type="completion", #interesting, yield completion type
                    metadata={"final_answer": True}
                )
                break
            
            # 更新状态，继续下一步
            self._streaming_manager.complete_current_step()
            state = self.update_state(state, result)
            step_count += 1
            
            yield StreamChunk(
                content=f"\n[STEP {step_count}] Completed. Moving to next step...\n",
                chunk_type="step_end",
                metadata={"step_number": step_count}
            )
            
        # 达到最大步数
        if step_count >= max_steps:
            yield StreamChunk(
                content=f"\n[WARNING] Reached maximum steps ({max_steps}). Providing best available answer...\n",
                chunk_type="warning"
            )
            
            try:
                final_answer = await self.provide_final_answer(state)
                yield StreamChunk(
                    content=f"Final answer: {final_answer}\n",
                    chunk_type="final_answer"
                )
            except Exception as e:
                logger.error(f"Failed to provide final answer: {e}")
                yield StreamChunk(
                    content=f"[ERROR] Could not provide final answer: {e}\n",
                    chunk_type="error"
                )
    
    async def _execute_step_stream(self, state, **kwargs):
        """执行单个步骤的流式输出"""
        try:
            # 调用 brain.step 并检查是否返回流式生成器
            result = await self.brain.step(state, stream=True,system_prompt=self.system_prompt, **kwargs)
            
            # 如果 brain.step 返回的是异步生成器，则流式处理
            if inspect.isasyncgen(result):
                async for chunk in result:
                    if isinstance(chunk, str):
                        yield StreamChunk(content=chunk, chunk_type="llm_output")
                    elif isinstance(chunk, StreamChunk):
                        yield chunk
                    else:
                        yield StreamChunk(content=str(chunk), chunk_type="llm_output")
            else:
                # 如果不是流式，直接返回结果
                content = result.answer if hasattr(result, 'answer') else str(result)
                yield StreamChunk(content=content, chunk_type="llm_output")
                
        except Exception as e:
            logger.error(f"Error in step execution: {e}")
            yield StreamChunk(
                content=f"[ERROR] Step execution failed: {e}\n",
                chunk_type="error"
            )
            
    async def _run_complete(self, state, max_steps, kwargs):
        """一次性执行所有步骤直到完成，返回最终结果"""
        step_count = 0
        final_result = None
        
        while step_count < max_steps:
            result = await self.step(state, stream=kwargs.get('stream', False), **kwargs)
            
            # 检查是否完成
            if self.is_done(result, state):
                return result

            # 更新状态，继续下一步
            state = self.update_state(state, result)
            step_count += 1
            
        # 达到最大步数
        if step_count >= max_steps:
            # Try to get the final answer and return it
            try:
                return await self.provide_final_answer(state)
            except Exception as e:
                # If getting the final answer fails, throw the original exception
                logger.error(f"Failed to provide final answer: {e}")
                raise Exception(f"Task execution reached max steps {max_steps} and is still incomplete")
            
        return final_result
    
    async def step(self, state: AgentState, stream: bool = False, **kwargs) -> AgentResponse:
        """
        执行单步决策/行动
        Args:
            state: 强类型状态对象，包含 input 等必要信息
            **kwargs: 其他参数，直接传递给brain
        Returns:
            AgentResponse: 结构化的响应对象
        """
        if not state.input:
            raise ValueError("State must contain input object")
            
        input_obj = state.input
        if not isinstance(input_obj, Input):
            # 将字符串转为Input
            input_obj = Input(query=str(input_obj))
            state.input = input_obj
            
        # 预处理输入
        input_obj, kwargs = await self.pre_step(input_obj, kwargs)
            
        # 执行主要步骤
        result = await self.execute_step(state, stream=stream, **kwargs)
        
        # 确保result是AgentResponse格式
        if not isinstance(result, AgentResponse):
            # 如果是旧的5-tuple格式，转换为AgentResponse
            result = AgentResponse.from_tuple(result)
        
        # 执行后处理操作
        await self.post_step(state.input, result)
        
        return result
    
    async def execute_step(self, state: AgentState, stream: bool = False, **kwargs) -> AgentResponse:
        """
        执行实际的步骤操作，默认委托给brain处理。子类可以重写此方法以自定义执行逻辑。
        Args:
            state: 强类型状态对象
            **kwargs: 其他参数
        Returns:
            AgentResponse: 结构化的响应对象
        """
        # 使用agent的tools
        tools = self.tools
        
        # 同步state到brain，这样minion可以访问agent的状态
        self.brain.state = state
        
        # 传递强类型状态给brain.step
        result = await self.brain.step(state, tools=tools, stream=stream, system_prompt=self.system_prompt, **kwargs)
        
        # 确保返回AgentResponse格式
        if not isinstance(result, AgentResponse):
            result = AgentResponse.from_tuple(result)
        
        return result
    
    async def pre_step(self, input_data: Input, kwargs: Dict[str, Any]) -> Tuple[Input, Dict[str, Any]]:
        """
        step执行前的预处理操作
        Args:
            input_data: 输入数据
            kwargs: 其他参数
        Returns:
            Tuple[Input, Dict[str, Any]]: 处理后的输入数据和参数
        """
        return input_data, kwargs
    
    async def post_step(self, input_data: Input, result: Any) -> None:
        """
        step执行后的处理操作
        Args:
            input_data: 输入数据
            result: step的执行结果 (可以是5-tuple或AgentResponse)
        """
        # 默认实现不执行任何操作
        pass
        
    async def provide_final_answer(self, state: Dict[str, Any]) -> Any:
        """
        Attempt to provide a final answer when maximum steps are reached
        
        Args:
            state: Current state dictionary
            
        Returns:
            Final answer result
        """
        # 获取任务和历史
        task = state.get('task', '')
        history = state.get('history', [])
        input_obj = state.get('input')
        
        # 构建提示，要求LLM基于目前进展提供最终答案
        if isinstance(input_obj, Input):
            final_answer_prompt = f"""
You have reached the maximum step limit, but the task is not yet complete.

Original task: {task}

You have executed {len(history)} steps. Based on the current progress, please provide the best possible final answer or conclusion.
Even if the answer is not perfect, provide the best result you can currently derive.

Please provide the answer directly, without explaining why you couldn't complete the entire task.
"""
            # Update the input object's query
            input_obj.query = final_answer_prompt
            
            # Execute one step to get the final answer
            try:
                result = await self.step(state, stream=False)
                
                # Mark the result as final answer
                if hasattr(result, 'terminated') and not result.terminated:
                    # If using AgentResponse format
                    result.terminated = True
                    
                elif isinstance(result, tuple) and len(result) >= 3:
                    # If using 5-tuple format, modify the terminated flag
                    response, score, _, truncated, info = result
                    result = (response, score, True, truncated, info)
                    
                return result
            except Exception as e:
                logger.error(f"获取最终答案失败: {e}")
                # 构造一个基本的回应
                return f"The task could not be completed within the maximum step limit, but {len(history)} steps have been executed. Consider increasing the maximum step limit or simplifying the task."
        
        # If there is no valid input object, return basic information
        return f"The task execution reached the maximum step limit and could not provide a valid final answer."
    
    def _init_state_from_task(self, task: Union[str, Input], **kwargs) -> None:
        """
        从任务初始化内部状态
        Args:
            task: 任务描述或Input对象
            **kwargs: 附加参数
        """
        # 将任务转换为Input对象
        if isinstance(task, str):
            input_obj = Input(query=task)
            task_str = task
        else:
            input_obj = task
            task_str = task.query
            
        # 初始化强类型状态
        self.state = AgentState(
            agent=self,
            input=input_obj,
            history=[],
            step_count=0,
            task=task_str
        )
        
        # 添加额外的metadata
        self.state.metadata.update(kwargs)

    def update_state(self, state: AgentState, result: Any) -> AgentState:
        """
        根据步骤结果更新状态
        Args:
            state: 当前状态 (强类型AgentState)
            result: 步骤执行结果 (可以是5-tuple或AgentResponse)
        Returns:
            AgentState: 更新后的状态
        """
        # 使用传入的状态
        self.state = state
            
        # 添加结果到历史
        self.state.history.append(result)
        self.state.step_count += 1
        
        # 提取响应内容作为下一步输入
        if hasattr(result, 'raw_response'):
            response = result.raw_response
        elif hasattr(result, 'answer'):
            response = result.answer
        # 检查5-tuple格式
        elif isinstance(result, tuple) and len(result) > 0:
            response = result[0]  # 返回response部分
        else:
            response = result
            
        if isinstance(self.state.input, Input):
            self.state.input.query = f"上一步结果: {response}\n继续执行任务: {self.state.task}"
            
        return self.state
    
    def is_done(self, result: Any, state: AgentState) -> bool:
        """
        判断任务是否完成
        Args:
            result: 当前步骤结果 (可以是5-tuple或AgentResponse)
            state: 当前状态 (强类型AgentState)
        Returns:
            bool: 是否完成
        """
        # 检查AgentResponse类型
        if hasattr(result, 'is_done') and callable(result.is_done):
            return result.is_done()
        elif hasattr(result, 'terminated') or hasattr(result, 'is_final_answer'):
            return getattr(result, 'terminated', False) or getattr(result, 'is_final_answer', False)
        
        # 检查5-tuple格式
        if isinstance(result, tuple) and len(result) >= 3:
            # 返回格式为 (response, score, terminated, truncated, info)
            terminated = result[2]
            return terminated
        
        # 检查状态中的final_answer标志
        if state.is_final_answer:
            return True
            
        return False
    
    def finalize(self, result: Any, state: AgentState) -> Any:
        """
        整理最终结果
        Args:
            result: 最后一步结果 (可以是5-tuple或AgentResponse)
            state: 当前状态 (强类型AgentState)
        Returns:
            最终处理后的结果
        """
        # 检查状态中的final_answer_value
        if state.final_answer_value is not None:
            return state.final_answer_value
            
        # 检查AgentResponse类型
        if hasattr(result, 'answer') and result.answer is not None:
            return result.answer
        elif hasattr(result, 'raw_response'):
            return result.raw_response
        
        # 检查5-tuple格式
        if isinstance(result, tuple) and len(result) > 0:
            return result[0]  # 返回response部分
        elif isinstance(result, dict):
            return result.get("answer", result.get("final_answer"))  # 兼容旧格式
            
        return result
    
    def add_tool(self, tool: BaseTool) -> None:
        """
        添加工具
        Args:
            tool: 要添加的工具
        """
        self.tools.append(tool)
        # 同时向brain添加工具
        if hasattr(self.brain, 'add_tool'):
            self.brain.add_tool(tool)
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        获取指定名称的工具
        Args:
            tool_name: 工具名称
        Returns:
            找到的工具实例，如果未找到则返回None
        """
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None
    
    def add_memory(self, messages: Union[str, List[Dict[str, str]]], metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        添加记忆到brain的mem0
        Args:
            messages: 要添加的消息内容，可以是字符串或消息列表
                     如果是字符串，会被转换为 [{"role": "user", "content": messages}]
                     如果是列表，每个消息都应该是 {"role": xxx, "content": xxx} 格式
            metadata: 额外的元数据
        """
        if self.brain and self.brain.mem:
            # 确保至少有一个必需的ID
            if not any([self.user_id, self.agent_id, self.session_id]):
                raise ValueError("At least one of user_id, agent_id, or session_id (run_id) is required!")
                
            self.brain.mem.add(
                messages=messages,  # mem0会自动处理字符串到消息列表的转换
                user_id=self.user_id,
                agent_id=self.agent_id,
                run_id=self.session_id,
                metadata=metadata
            )
            
    def get_all_memories(self, filter: Optional[Dict[str, Any]] = None) -> List[Any]:
        """
        根据元数据检索记忆
        
        Args:
            filter: 可选的元数据过滤条件，用于筛选记忆

        Returns:
            List[Memory]: 检索到的记忆列表
        """
        if self.brain and self.brain.mem:
            response = self.brain.mem.get_all(
                user_id=self.user_id,
                agent_id=self.agent_id,
                run_id=self.session_id
            )
            
            # 处理返回的数据格式，提取results列表
            memories = []
            if isinstance(response, dict) and 'results' in response:
                # 新的API格式 (v1.1)
                memories = response['results']
            elif isinstance(response, list):
                # 旧的API格式
                memories = response
            else:
                return []
            
            # 如果提供了过滤条件，进行过滤
            if filter:
                filtered_memories = []
                for memory in memories:
                    if "metadata" in memory:
                        # 检查元数据是否满足过滤条件
                        match = True
                        for key, value in filter.items():
                            if key not in memory["metadata"] or memory["metadata"][key] != value:
                                match = False
                                break
                        if match:
                            filtered_memories.append(memory)
                return filtered_memories
            
            return memories
        return []
        
    def search_memories(self, query: str, top_k: int = 5, include_relations: bool = False) -> Union[List[Any], Dict[str, Any]]:
        """
        语义搜索记忆
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            include_relations: 是否包含关系数据（仅在mem0 API v1.1中有效）
        Returns:
            如果include_relations=False: List[Memory]: 搜索结果列表
            如果include_relations=True: Dict[str, Any]: 包含'results'和'relations'的字典
        """
        if self.brain and self.brain.mem:
            try:
                # 尝试使用top_k参数
                response = self.brain.mem.search(
                    user_id=self.user_id,
                    agent_id=self.agent_id,
                    run_id=self.session_id,
                    query=query,
                    top_k=top_k
                )
            except TypeError:
                # 如果top_k参数不被接受，尝试使用limit参数
                try:
                    response = self.brain.mem.search(
                        user_id=self.user_id,
                        agent_id=self.agent_id,
                        run_id=self.session_id,
                        query=query,
                        limit=top_k
                    )
                except TypeError:
                    # 如果limit参数也不被接受，只使用必需参数
                    response = self.brain.mem.search(
                        user_id=self.user_id,
                        agent_id=self.agent_id,
                        run_id=self.session_id,
                        query=query
                    )
            
            # 处理返回的数据格式
            if isinstance(response, dict):
                if include_relations and 'relations' in response:
                    # 如果需要关系数据，直接返回完整响应
                    return response
                elif 'results' in response:
                    # 否则只返回结果列表
                    return response['results']
            elif isinstance(response, list):
                # 旧的API格式
                return response
                
        return []
        
    def get_conversation_history(self, top_k: int = 10, order: str = "desc") -> List[Dict[str, str]]:
        """
        获取记忆中的对话历史
        Args:
            top_k: 返回的消息数量
            order: 排序方式，"asc" 或 "desc"
        Returns:
            List[Dict[str, str]]: 对话历史列表
        """
        if self.brain and self.brain.mem:
            response = self.brain.mem.get_conversation_history(
                user_id=self.user_id,
                agent_id=self.agent_id,
                run_id=self.session_id,
                top_k=top_k,
                order=order
            )
            
            # 处理返回的数据格式
            if isinstance(response, dict) and 'results' in response:
                # 新的API格式 (v1.1)
                return response['results']
            elif isinstance(response, list):
                # 旧的API格式
                return response
                
        return []
    
    def get_state(self) -> Dict[str, Any]:
        """
        获取当前执行状态
        Returns:
            Dict[str, Any]: 当前状态的副本
        """
        if hasattr(self, 'state') and self.state:
            return self.state.copy()
        else:
            raise ValueError("No current state available. Run agent first.")
    
    def save_state(self, filepath: str) -> None:
        """
        保存状态到文件
        Args:
            filepath: 保存路径
        """
        import pickle
        state = self.get_state()
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
    
    def load_state(self, filepath: str) -> Dict[str, Any]:
        """
        从文件加载状态
        Args:
            filepath: 文件路径
        Returns:
            Dict[str, Any]: 加载的状态
        """
        import pickle
        with open(filepath, 'rb') as f:
            return pickle.load(f)


