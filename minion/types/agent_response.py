import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
@dataclass
class StreamChunk:
    """单个流式输出块"""
    content: str
    chunk_type: str = "text"  # text, tool_call, observation, error, agent_response, final_answer, completion
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
@dataclass
class AgentResponse(StreamChunk):
    """
    Agent执行步骤的响应结果，替换原有的5-tuple格式
    
    This class replaces the 5-tuple format (response, score, terminated, truncated, info)
    with a more structured and extensible approach.
    
    Fields:
        raw_response: 每步的原始响应内容
        answer: 当前最佳答案（可能是最终答案，也可能是中间答案）
        is_final_answer: 标识answer是否为最终答案
        score: 执行质量指标
        confidence: 置信度
        terminated: 是否终止
        truncated: 是否被截断
        info: 扩展信息字典
        error: 错误信息
        execution_time: 执行时间
        tokens_used: 使用的token数量
    """
    
    # Override StreamChunk fields with defaults
    content: str = ""  # Will be set from raw_response in __post_init__
    
    # 主要响应内容
    raw_response: Any = None
    
    # 答案相关
    answer: Optional[Any] = None
    is_final_answer: bool = False
    
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
    
    # 执行统计
    execution_time: Optional[float] = None
    tokens_used: Optional[int] = None
    
    def __post_init__(self):
        """Initialize StreamChunk fields based on AgentResponse content"""
        # Set content from raw_response if not already set
        if not hasattr(self, 'content') or not self.content:
            self.content = str(self.raw_response) if self.raw_response is not None else ""
        
        # Set appropriate chunk_type
        if not hasattr(self, 'chunk_type') or not self.chunk_type:
            if self.error:
                self.chunk_type = "error"
            elif self.is_final_answer:
                self.chunk_type = "final_answer"  
            elif self.terminated:
                self.chunk_type = "completion"
            else:
                self.chunk_type = "agent_response"
        
        # Ensure metadata includes AgentResponse info
        if not hasattr(self, 'metadata'):
            self.metadata = {}
        self.metadata.update({
            'score': self.score,
            'confidence': self.confidence,
            'terminated': self.terminated,
            'truncated': self.truncated,
            'is_final_answer': self.is_final_answer
        })
    
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
            return cls(raw_response=tuple_result)
        
        response, score, terminated, truncated, info = tuple_result
        
        # 从info中提取特殊字段
        answer = info.get('answer', info.get('final_answer')) if isinstance(info, dict) else None
        is_final_answer = info.get('is_final_answer', False) if isinstance(info, dict) else False
        error = info.get('error') if isinstance(info, dict) else None
        
        return cls(
            raw_response=response,
            score=score,
            terminated=terminated,
            truncated=truncated,
            info=info if isinstance(info, dict) else {},
            answer=answer,
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
        if self.answer is not None:
            info['answer'] = self.answer
            info['final_answer'] = self.answer  # 为了向后兼容
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
        
        return (self.raw_response, self.score, self.terminated, self.truncated, info)
    
    def set_answer(self, value: Any, is_final: bool = True) -> 'AgentResponse':
        """
        设置答案
        
        Args:
            value: 答案值
            is_final: 是否为最终答案，默认为True
            
        Returns:
            self (for method chaining)
        """
        self.answer = value
        self.is_final_answer = is_final
        if is_final:
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