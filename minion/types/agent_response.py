from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class AgentResponse:
    """
    Agent执行步骤的响应结果，替换原有的5-tuple格式
    
    This class replaces the 5-tuple format (response, score, terminated, truncated, info)
    with a more structured and extensible approach.
    """
    
    # 主要响应内容
    response: Any = None
    
    # 执行质量指标
    score: float = 0.0
    confidence: float = 1.0
    
    # 终止状态
    terminated: bool = False
    truncated: bool = False
    
    # 扩展信息
    info: Dict[str, Any] = field(default_factory=dict)
    
    # 错误信息
    error: Optional[str] = None
    
    # Agent特有信息
    final_answer: Optional[Any] = None
    is_final_answer: bool = False
    
    # 执行统计
    execution_time: Optional[float] = None
    tokens_used: Optional[int] = None
    
    @classmethod
    def from_tuple(cls, tuple_result) -> 'AgentResponse':
        """
        从原有的5-tuple格式创建AgentResponse实例
        
        Args:
            tuple_result: (response, score, terminated, truncated, info) 格式的结果，或已有的AgentResponse
            
        Returns:
            AgentResponse实例
        """
        # 如果输入已经是AgentResponse，直接返回
        if isinstance(tuple_result, cls):
            return tuple_result
        
        if not isinstance(tuple_result, tuple) or len(tuple_result) < 5:
            # 如果不是标准格式，创建一个基本的响应
            return cls(response=tuple_result)
        
        response, score, terminated, truncated, info = tuple_result
        
        # 从info中提取特殊字段
        final_answer = info.get('final_answer') if isinstance(info, dict) else None
        is_final_answer = info.get('is_final_answer', False) if isinstance(info, dict) else False
        error = info.get('error') if isinstance(info, dict) else None
        
        return cls(
            response=response,
            score=score,
            terminated=terminated,
            truncated=truncated,
            info=info if isinstance(info, dict) else {},
            final_answer=final_answer,
            is_final_answer=is_final_answer,
            error=error
        )
    
    def to_tuple(self) -> tuple:
        """
        转换为原有的5-tuple格式以保持向后兼容
        
        Returns:
            (response, score, terminated, truncated, info) 格式的tuple
        """
        # 将特殊字段合并到info中
        info = self.info.copy()
        if self.final_answer is not None:
            info['final_answer'] = self.final_answer
        if self.is_final_answer:
            info['is_final_answer'] = self.is_final_answer
        if self.error:
            info['error'] = self.error
        if self.confidence != 1.0:
            info['confidence'] = self.confidence
        if self.execution_time:
            info['execution_time'] = self.execution_time
        if self.tokens_used:
            info['tokens_used'] = self.tokens_used
        
        return (self.response, self.score, self.terminated, self.truncated, info)
    
    def set_final_answer(self, value: Any) -> 'AgentResponse':
        """
        设置最终答案并标记为完成
        
        Args:
            value: 最终答案值
            
        Returns:
            self (for method chaining)
        """
        self.final_answer = value
        self.is_final_answer = True
        self.terminated = True
        return self
    
    def set_error(self, error_msg: str) -> 'AgentResponse':
        """
        设置错误信息
        
        Args:
            error_msg: 错误消息
            
        Returns:
            self (for method chaining)
        """
        self.error = error_msg
        return self
    
    def is_success(self) -> bool:
        """
        检查执行是否成功（没有错误）
        
        Returns:
            bool: 是否成功
        """
        return self.error is None
    
    def is_done(self) -> bool:
        """
        检查任务是否完成
        
        Returns:
            bool: 是否完成
        """
        return self.terminated or self.is_final_answer
    
    def __iter__(self):
        """
        使AgentResponse可以像tuple一样被解包
        
        这提供了向后兼容性，允许现有代码继续使用tuple解包：
        response, score, terminated, truncated, info = agent_response
        
        Returns:
            Iterator over (response, score, terminated, truncated, info)
        """
        return iter(self.to_tuple()) 