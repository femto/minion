from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import uuid

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
    
    def __post_init__(self):
        """初始化后的处理"""
        if self.brain is None:
            self.brain = Brain()
            
    async def step(self, input_data: Any, **kwargs) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        """
        处理输入（委托给brain）
        Args:
            input_data: 输入数据
            **kwargs: 其他参数，直接传递给brain
        Returns:
            Tuple[response, score, terminated, truncated, info]
            - response: 响应内容
            - score: 分数
            - terminated: 是否终止
            - truncated: 是否截断
            - info: 额外信息
        """
        if isinstance(input_data, str):
            input_data = Input(query=input_data)
            
        # 预处理输入
        input_data, kwargs = await self.pre_step(input_data, kwargs)
            
        # 执行主要步骤
        result = await self.execute_step(input_data, kwargs)
        
        # 执行后处理操作
        await self.post_step(input_data, result)
        
        return result
    
    async def execute_step(self, input_data: Input, kwargs: Dict[str, Any]) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        """
        执行实际的步骤操作，默认委托给brain处理。子类可以重写此方法以自定义执行逻辑。
        Args:
            input_data: 输入数据
            kwargs: 其他参数
        Returns:
            Tuple[response, score, terminated, truncated, info]
        """
        return await self.brain.step(input=input_data, **kwargs)
    
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
    
    def add_tool(self, tool: BaseTool) -> None:
        """
        添加工具（同时添加到brain）
        Args:
            tool: 要添加的工具
        """
        self.tools.append(tool)
        # TODO: 实现brain的add_tool方法
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
            
            # 如果提供了过滤条件，在Python中进行过滤
            if filter:
                filtered_memories = []
                for memory in memories:
                    # 检查memory是否有metadata属性或字段
                    metadata = getattr(memory, 'metadata', None)
                    if metadata is None and isinstance(memory, dict):
                        metadata = memory.get('metadata')
                    
                    if metadata is None:
                        continue
                        
                    match = True
                    for key, value in filter.items():
                        # 处理metadata可能是属性或字典的情况
                        if isinstance(metadata, dict):
                            if metadata.get(key) != value:
                                match = False
                                break
                        else:
                            if getattr(metadata, key, None) != value:
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