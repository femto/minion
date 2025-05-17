from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import uuid
import asyncio

from ..tools.base_tool import BaseTool
from ..main.brain import Brain
from ..main.input import Input

@dataclass
class BaseAgent:
    """Agent基类，定义所有Agent的基本接口"""
    
    name: str = "base_agent"
    tools: List[BaseTool] = field(default_factory=list)
    brain: Optional[Brain] = None
    user_id: Optional[str] = None
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    max_steps: int = 20
    
    def __post_init__(self):
        """初始化后的处理"""
        if self.brain is None:
            self.brain = Brain()
    
    async def run(self, task: Union[str, Input], **kwargs) -> Any:
        """
        运行完整任务，自动多步执行直到完成
        
        Args:
            task: 任务描述或Input对象
            **kwargs: 附加参数，可包含:
                - max_steps: 最大步数
                - tools: 临时工具覆盖
                - streaming: 若为True则使用异步迭代器返回中间结果
                - 其他参数会传递给brain.step
                
        Returns:
            最终任务结果
        """
        # 处理参数
        max_steps = kwargs.pop("max_steps", self.max_steps)
        streaming = kwargs.pop("streaming", False)
        
        # 初始化任务状态
        state = self.init_state(task, **kwargs)
        
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
    
    async def step(self, input_data: Any, **kwargs) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        """
        执行单步决策/行动
        Args:
            input_data: 输入数据（可以是状态字典或Input对象）
            **kwargs: 其他参数，直接传递给brain
        Returns:
            Tuple[response, score, terminated, truncated, info]
            - response: 响应内容
            - score: 分数
            - terminated: 是否终止
            - truncated: 是否截断
            - info: 额外信息
        """
        if isinstance(input_data, dict) and "input" in input_data:
            # 从状态字典提取Input
            input_obj = input_data["input"]
        elif not isinstance(input_data, Input):
            # 将字符串转为Input
            input_obj = Input(query=str(input_data))
        else:
            input_obj = input_data
            
        # 预处理输入
        input_obj, kwargs = await self.pre_step(input_obj, kwargs)
        
        # 执行主要步骤，优先使用状态中的tools
        tools = kwargs.pop("tools", None)
        if tools is None and isinstance(input_data, dict) and "tools" in input_data:
            tools = input_data.get("tools", self.tools)
        if tools is None:
            tools = self.tools
            
        # 执行主要步骤
        result = await self.execute_step(input_obj, tools=tools, **kwargs)
        
        # 执行后处理操作
        await self.post_step(input_obj, result)
        
        return result
    
    async def execute_step(self, input_data: Input, **kwargs) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        """
        执行实际的步骤操作，默认委托给brain处理。子类可以重写此方法以自定义执行逻辑。
        Args:
            input_data: 输入数据
            **kwargs: 其他参数
        Returns:
            Tuple[response, score, terminated, truncated, info]
        """
        # 明确传递tools参数给brain
        tools = kwargs.pop("tools", self.tools)
        return await self.brain.step(input=input_data, tools=tools, **kwargs)
    
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
    
    async def post_step(self, input_data: Input, result: Tuple[Any, float, bool, bool, Dict[str, Any]]) -> None:
        """
        step执行后的处理操作
        Args:
            input_data: 输入数据
            result: step的执行结果
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
            result: 步骤执行结果
        Returns:
            Dict: 更新后的状态
        """
        # 添加结果到历史
        state["history"].append(result)
        state["step_count"] += 1
        
        # 提取结果的first元素作为下一步输入
        response = result[0] if isinstance(result, tuple) and len(result) > 0 else result
        if isinstance(state["input"], Input):
            state["input"].query = f"上一步结果: {response}\n继续执行任务: {state['task']}"
            
        return state
    
    def is_done(self, result: Any, state: Dict[str, Any]) -> bool:
        """
        判断任务是否完成
        Args:
            result: 当前步骤结果
            state: 当前状态
        Returns:
            bool: 是否完成
        """
        # 检查是否有明确的终止信号
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
            result: 最后一步结果
            state: 当前状态
        Returns:
            最终处理后的结果
        """
        # 提取最终答案
        if isinstance(result, tuple) and len(result) > 0:
            return result[0]  # 返回response部分
        elif isinstance(result, dict) and "final_answer" in result:
            return result["final_answer"]
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