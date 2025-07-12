from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import uuid
import asyncio
import logging
import inspect

from ..tools.base_tool import BaseTool
from ..main.brain import Brain
from ..main.input import Input
from minion.types.agent_response import AgentResponse

logger = logging.getLogger(__name__)

@dataclass
class BaseAgent:
    """Agent基类，定义所有Agent的基本接口，支持生命周期管理"""
    
    name: str = "base_agent"
    tools: List[BaseTool] = field(default_factory=list)
    brain: Optional[Brain] = None
    user_id: Optional[str] = None
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    max_steps: int = 20
    
    # 生命周期管理
    _is_setup: bool = field(default=False, init=False)
    _mcp_toolsets: List[Any] = field(default_factory=list, init=False)  # List of MCPToolset instances
    
    def __post_init__(self):
        """初始化后的处理"""
        if self.brain is None:
            self.brain = Brain()
        
        # Automatically handle MCPToolset objects in tools parameter
        self._extract_mcp_toolsets_from_tools()
    
    def _extract_mcp_toolsets_from_tools(self):
        """
        Extract MCPToolset objects from tools parameter and move them to _mcp_toolsets.
        This enables direct passing of MCPToolset objects in the tools parameter.
        """
        if self._is_setup:
            raise RuntimeError("Cannot modify toolsets after setup")
            
        # Check if any tools are MCPToolset objects
        mcp_toolsets = []
        regular_tools = []
        
        for tool in self.tools:
            # Check if it's an MCPToolset object
            if hasattr(tool, '_ensure_setup') and hasattr(tool, 'connection_params'):
                mcp_toolsets.append(tool)
            else:
                regular_tools.append(tool)
        
        # Update the tools list to only contain regular tools
        self.tools = regular_tools
        
        # Add MCPToolset objects to _mcp_toolsets
        for toolset in mcp_toolsets:
            self._mcp_toolsets.append(toolset)
            logger.info(f"Auto-detected MCPToolset {getattr(toolset, 'name', 'unnamed')} from tools parameter")
    
    async def setup(self):
        """Setup agent with tools"""
        # Setup MCP toolsets
        for toolset in self._mcp_toolsets:
            try:
                await toolset._ensure_setup()
                if not toolset.is_healthy:
                    logger.warning(f"MCP toolset {toolset.name} failed to setup: {toolset.setup_error}")
            except Exception as e:
                logger.error(f"Failed to setup MCP toolset {toolset.name}: {e}")

        # Get tools from healthy toolsets
        tools = []
        for toolset in self._mcp_toolsets:
            if toolset.is_healthy:
                tools.extend(toolset.get_tools())
            else:
                logger.warning(f"Skipping unhealthy MCP toolset {toolset.name}")

        # Initialize brain with tools
        self.brain = Brain(tools=tools)
        
        # Mark agent as setup
        self._is_setup = True
    
    async def close(self):
        """
        Agent清理关闭，在停止使用agent时调用
        这里会清理所有的MCPToolset和其他资源
        """
        if not self._is_setup:
            logger.warning(f"Agent {self.name} not setup, skipping cleanup")
            return
        
        logger.info(f"Closing agent {self.name}")
        
        # 清理所有MCPToolset
        for toolset in self._mcp_toolsets:
            try:
                await toolset.close()
                logger.info(f"Closed MCP toolset {getattr(toolset, 'name', 'unnamed')}")
            except Exception as e:
                logger.error(f"Error closing MCP toolset {getattr(toolset, 'name', 'unnamed')}: {e}")
        
        # 清理MCP相关的工具
        self.tools = [tool for tool in self.tools if not self._is_mcp_tool(tool)]
        self._mcp_toolsets.clear()
        
        self._is_setup = False
        logger.info(f"Agent {self.name} cleanup completed")
    
    def _is_mcp_tool(self, tool: BaseTool) -> bool:
        """检查工具是否是MCP工具"""
        # 检查工具是否是BrainTool类型（MCP工具的包装类）
        return tool.__class__.__name__ == 'BrainTool'
    
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

    async def run_async(self, 
                       task: Optional[Union[str, Input]] = None,
                       state: Optional[Dict[str, Any]] = None, 
                       max_steps: Optional[int] = None,
                       **kwargs) -> Any:
        """
        运行完整任务，自动多步执行直到完成，支持从中断状态恢复
        
        Args:
            task: 任务描述或Input对象 (state为None时必须提供)
            state: 已有状态，用于恢复中断的执行
            max_steps: 最大步数
            **kwargs: 附加参数，可包含:
                - tools: 临时工具覆盖
                - streaming: 若为True则使用异步迭代器返回中间结果
                - 其他参数会传递给brain.step
                
        Returns:
            最终任务结果
        """
        self._ensure_setup()
        
        # 处理参数
        streaming = kwargs.pop("streaming", False)
        
        # 处理状态初始化或恢复
        if state is None:
            if task is None:
                raise ValueError("Either 'task' or 'state' must be provided")
            state = self.init_state(task, **kwargs)
        else:
            # 使用已有状态，可选择更新task
            if task is not None:
                if isinstance(task, str):
                    state["task"] = task
                    # 更新input对象的query
                    if "input" in state and hasattr(state["input"], 'query'):
                        state["input"].query = task
                else:
                    state["task"] = task.query
                    state["input"] = task
        
        # 确定最大步数
        max_steps = max_steps or self.max_steps
        
        # 保存当前状态引用，便于外部访问
        self._current_state = state
        
        if streaming:
            # 返回异步迭代器
            return self._run_streaming(state, max_steps, kwargs)
        else:
            # 一次性执行完成返回最终结果
            return await self._run_complete(state, max_steps, kwargs)
            
    async def _run_streaming(self, state, max_steps, kwargs):
        """返回一个异步迭代器，逐步执行并返回中间结果"""
        step_count = 0
        while step_count < max_steps:
            result = await self.step(state, **kwargs)
            
            # 返回本步结果
            yield result
            
            # 检查是否完成
            if self.is_done(result, state):
                final_result = self.finalize(result, state)
                yield final_result
                break
            
            # 更新状态，继续下一步
            state = self.update_state(state, result)
            step_count += 1
            
        # 达到最大步数
        if step_count >= max_steps:
            raise Exception(f"任务执行达到最大步数 {max_steps} 仍未完成")
            
    async def _run_complete(self, state, max_steps, kwargs):
        """一次性执行所有步骤直到完成，返回最终结果"""
        step_count = 0
        final_result = None
        
        while step_count < max_steps:
            result = await self.step(state, **kwargs)
            
            # 检查是否完成
            if self.is_done(result, state):
                final_result = self.finalize(result, state)
                break
                
            # 更新状态，继续下一步
            state = self.update_state(state, result)
            step_count += 1
            
        # 达到最大步数
        if step_count >= max_steps:
            raise Exception(f"任务执行达到最大步数 {max_steps} 仍未完成")
            
        return final_result
    
    async def step(self, state: Dict[str, Any], **kwargs) -> AgentResponse:
        """
        执行单步决策/行动
        Args:
            state: 状态字典，包含 input, tools 等必要信息
            **kwargs: 其他参数，直接传递给brain
        Returns:
            AgentResponse: 结构化的响应对象，支持tuple解包以保持向后兼容性
        """
        if "input" not in state:
            raise ValueError("State must contain 'input' key with Input object")
            
        input_obj = state["input"]
        if not isinstance(input_obj, Input):
            # 将字符串转为Input
            input_obj = Input(query=str(input_obj))
            state["input"] = input_obj
            
        # 预处理输入
        input_obj, kwargs = await self.pre_step(input_obj, kwargs)
        
        # 执行主要步骤，优先使用状态中的tools
        tools = kwargs.pop("tools", None)
        if tools is None:
            tools = state.get("tools", self.tools)
        if tools is None:
            tools = self.tools
            
        # 执行主要步骤
        result = await self.execute_step(state, **kwargs)
        
        # 确保result是AgentResponse格式
        if not isinstance(result, AgentResponse):
            # 如果是旧的5-tuple格式，转换为AgentResponse
            result = AgentResponse.from_tuple(result)
        
        # 执行后处理操作
        await self.post_step(state["input"], result)
        
        return result
    
    async def execute_step(self, state: Dict[str, Any], **kwargs) -> AgentResponse:
        """
        执行实际的步骤操作，默认委托给brain处理。子类可以重写此方法以自定义执行逻辑。
        Args:
            state: 状态字典，包含 input, tools 等信息
            **kwargs: 其他参数
        Returns:
            AgentResponse: 结构化的响应对象
        """
        # 传递状态给brain.step
        result = await self.brain.step(state, **kwargs)
        
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
        pass
    
    def init_state(self, task: Union[str, Input], **kwargs) -> Dict[str, Any]:
        """
        初始化任务状态
        Args:
            task: 任务描述或Input对象
            **kwargs: 附加参数
        Returns:
            Dict: 初始状态字典
        """
        # 将任务转换为Input对象
        if isinstance(task, str):
            input_obj = Input(query=task)
        else:
            input_obj = task
            
        return {
            "input": input_obj,
            "history": [],
            "tools": self.tools,
            "step_count": 0,
            "task": task if isinstance(task, str) else task.query,
            **kwargs
        }
    
    def update_state(self, state: Dict[str, Any], result: Any) -> Dict[str, Any]:
        """
        根据步骤结果更新状态
        Args:
            state: 当前状态
            result: 步骤执行结果 (可以是5-tuple或AgentResponse)
        Returns:
            Dict: 更新后的状态
        """
        # 添加结果到历史
        state["history"].append(result)
        state["step_count"] += 1
        
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
            
        if isinstance(state["input"], Input):
            state["input"].query = f"上一步结果: {response}\n继续执行任务: {state['task']}"
            
        return state
    
    def is_done(self, result: Any, state: Dict[str, Any]) -> bool:
        """
        判断任务是否完成
        Args:
            result: 当前步骤结果 (可以是5-tuple或AgentResponse)
            state: 当前状态
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
        
        # 检查结果中是否包含final_answer
        if isinstance(result, dict) and "final_answer" in result:
            return True
            
        return False
    
    def finalize(self, result: Any, state: Dict[str, Any]) -> Any:
        """
        整理最终结果
        Args:
            result: 最后一步结果 (可以是5-tuple或AgentResponse)
            state: 当前状态
        Returns:
            最终处理后的结果
        """
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
    
    def get_current_state(self) -> Dict[str, Any]:
        """
        获取当前执行状态
        Returns:
            Dict[str, Any]: 当前状态的副本
        """
        if hasattr(self, '_current_state') and self._current_state:
            return self._current_state.copy()
        else:
            raise ValueError("No current state available. Run agent first.")
    
    def save_state(self, filepath: str) -> None:
        """
        保存状态到文件
        Args:
            filepath: 保存路径
        """
        import pickle
        state = self.get_current_state()
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