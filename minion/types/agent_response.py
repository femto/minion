import time
import uuid
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field


@dataclass
class Usage:
    """Token usage information for a single API call"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0  # Anthropic prompt caching
    cache_read_input_tokens: int = 0      # Anthropic prompt caching
    # Cost in USD (calculated from tokens * model pricing, not from API)
    cost_usd: Optional[float] = None

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)"""
        return self.input_tokens + self.output_tokens

    def calculate_cost(
        self,
        input_cost_per_token: float,
        output_cost_per_token: float,
        cache_read_cost_per_token: Optional[float] = None,
        cache_write_cost_per_token: Optional[float] = None,
    ) -> float:
        """
        Calculate cost based on token counts and pricing.

        Args:
            input_cost_per_token: Cost per input token (e.g., 0.000003 for $3/M)
            output_cost_per_token: Cost per output token (e.g., 0.000015 for $15/M)
            cache_read_cost_per_token: Cost per cache read token (default: 10% of input)
            cache_write_cost_per_token: Cost per cache write token (default: 125% of input)

        Returns:
            Total cost in USD
        """
        if cache_read_cost_per_token is None:
            cache_read_cost_per_token = input_cost_per_token * 0.1
        if cache_write_cost_per_token is None:
            cache_write_cost_per_token = input_cost_per_token * 1.25

        cost = (
            self.input_tokens * input_cost_per_token +
            self.output_tokens * output_cost_per_token +
            self.cache_read_input_tokens * cache_read_cost_per_token +
            self.cache_creation_input_tokens * cache_write_cost_per_token
        )
        return cost

    def calculate_cost_from_model(self, model_name: str) -> Optional[float]:
        """
        Calculate cost using model pricing from litellm price database.

        Args:
            model_name: Model name (e.g., 'gpt-4o', 'claude-3-5-sonnet-20241022')

        Returns:
            Total cost in USD, or None if model not found
        """
        try:
            from minion.utils.model_price import get_model_price
            price_info = get_model_price(model_name)
            if price_info:
                self.cost_usd = self.calculate_cost(
                    input_cost_per_token=price_info['prompt'],
                    output_cost_per_token=price_info['completion'],
                )
                return self.cost_usd
        except ImportError:
            pass
        return None

    @staticmethod
    def get_default_pricing(model_name: str) -> Dict[str, float]:
        """
        Get default pricing for common models (fallback).

        Returns dict with 'input' and 'output' cost per token.
        """
        PRICING = {
            # Anthropic (per token)
            'claude-3-5-sonnet': {'input': 0.000003, 'output': 0.000015},
            'claude-3-5-haiku': {'input': 0.0000008, 'output': 0.000004},
            'claude-3-opus': {'input': 0.000015, 'output': 0.000075},
            'claude-sonnet-4': {'input': 0.000003, 'output': 0.000015},
            # OpenAI
            'gpt-4o': {'input': 0.0000025, 'output': 0.00001},
            'gpt-4o-mini': {'input': 0.00000015, 'output': 0.0000006},
            'o1': {'input': 0.000015, 'output': 0.00006},
            'o1-mini': {'input': 0.000003, 'output': 0.000012},
            # Default (Claude 3.5 Haiku)
            'default': {'input': 0.0000008, 'output': 0.000004},
        }

        model_lower = model_name.lower()
        for key in PRICING:
            if key in model_lower:
                return PRICING[key]
        return PRICING['default']

    def add(self, other: 'Usage') -> 'Usage':
        """
        累加另一个 Usage 的值到当前对象 (in-place)

        Args:
            other: 要累加的 Usage 对象

        Returns:
            self (支持链式调用)
        """
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_creation_input_tokens += other.cache_creation_input_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens
        # cost_usd 不累加，需要最后重新计算
        return self

    def __add__(self, other: 'Usage') -> 'Usage':
        """
        支持 usage1 + usage2 语法，返回新对象
        """
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
        )


@dataclass
class StreamChunk:
    """
    单个流式输出块

    partial=True: Token stream (增量文本，追加到之前的内容)
    partial=False: Complete message (完整消息，替换之前的 partial chunks)
    """
    content: str
    chunk_type: str = "text"  # text, thinking, tool_call, tool_result, observation, error, agent_response, final_answer, completion
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    partial: bool = False  # True for token streaming, False for complete message
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    # Per-message usage (optional, from raw API response)
    usage: Optional[Usage] = None
    # Model that generated this chunk (useful for multi-model scenarios)
    model: Optional[str] = None


# =============================================================================
# StreamChunk 子类 - 用于不同类型的消息
# =============================================================================

@dataclass
class UserStreamChunk(StreamChunk):
    """用户消息"""
    chunk_type: str = "user"


@dataclass
class AssistantStreamChunk(StreamChunk):
    """助手消息，可包含多个内容块"""
    chunk_type: str = "assistant"
    stop_reason: Optional[str] = None  # "end_turn", "tool_use", etc.


@dataclass
class ThinkingStreamChunk(StreamChunk):
    """思考/推理内容 (extended thinking)"""
    chunk_type: str = "thinking"
    thinking: str = ""

    def __post_init__(self):
        if self.thinking and not self.content:
            self.content = self.thinking


@dataclass
class ToolUseStreamChunk(StreamChunk):
    """工具调用请求"""
    chunk_type: str = "tool_call"
    tool_id: str = ""
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.metadata.update({
            'tool_id': self.tool_id,
            'tool_name': self.tool_name,
            'tool_input': self.tool_input
        })


@dataclass
class ToolResultStreamChunk(StreamChunk):
    """工具执行结果"""
    chunk_type: str = "tool_result"
    tool_use_id: str = ""
    is_error: bool = False

    def __post_init__(self):
        self.metadata.update({
            'tool_use_id': self.tool_use_id,
            'is_error': self.is_error
        })


@dataclass
class CodeExecutionStreamChunk(StreamChunk):
    """代码执行块"""
    chunk_type: str = "code"
    language: str = "python"
    code: str = ""
    output: Optional[str] = None
    success: bool = True

    def __post_init__(self):
        self.metadata.update({
            'language': self.language,
            'code': self.code,
            'output': self.output,
            'success': self.success
        })


@dataclass
class SystemStreamChunk(StreamChunk):
    """系统消息 (初始化、错误等)"""
    chunk_type: str = "system"
    subtype: str = ""  # "init", "error", "warning", etc.


@dataclass
class ResultStreamChunk(StreamChunk):
    """
    最终结果块 - 标记响应结束

    Cost/usage 信息通过继承的 StreamChunk.usage: Usage 获取:
    - usage.cost_usd: 总成本
    - usage.input_tokens / output_tokens: token 统计
    """
    chunk_type: str = "completion"
    subtype: str = "success"  # "success", "error", "interrupted"
    duration_ms: int = 0
    is_error: bool = False
    num_turns: int = 0
    session_id: str = ""
    # usage 继承自 StreamChunk，类型为 Optional[Usage]


# Type alias
AnyStreamChunk = Union[
    StreamChunk,
    UserStreamChunk,
    AssistantStreamChunk,
    ThinkingStreamChunk,
    ToolUseStreamChunk,
    ToolResultStreamChunk,
    CodeExecutionStreamChunk,
    SystemStreamChunk,
    ResultStreamChunk
]
@dataclass
class AgentResponse(StreamChunk):
    """
    Agent执行步骤的响应结果，替换原有的5-tuple格式

    This class replaces the 5-tuple format (response, score, terminated, truncated, info)
    with a more structured and extensible approach.

    Usage tracking:
        - self.usage (继承自 StreamChunk): 单条消息的 usage
        - self.total_usage: 整个 agent 运行的汇总 usage

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
        execution_time: 执行时间 (ms)
        total_usage: 汇总的 token usage 和 cost
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
    tokens_used: Optional[int] = None  # deprecated, use total_usage instead

    # 汇总 usage (所有 API 调用的累计)
    # 注意: 继承的 self.usage 是单条消息的 usage
    # total_usage 是整个 agent 运行期间的汇总
    total_usage: Optional[Usage] = None
    
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