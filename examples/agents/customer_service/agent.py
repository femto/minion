from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field

from minion.agents.conversational_agent import ConversationalAgent
from minion.main.input import Input
from .tools import CustomerServiceTool

@dataclass
class CustomerServiceAgent(ConversationalAgent):
    """
    客服Agent，负责处理用户查询并提供响应
    """
    name: str = "customer_service_agent"
    tools: List[CustomerServiceTool] = field(default_factory=lambda: [CustomerServiceTool()])
    
    def __post_init__(self):
        """初始化后的处理"""
        super().__post_init__()
    
    async def pre_step(self, input_data: Input, kwargs: Dict[str, Any]) -> Tuple[Input, Dict[str, Any]]:
        """
        预处理输入，处理特殊指令（如问候语）
        Args:
            input_data: 输入数据
            kwargs: 其他参数
        Returns:
            处理后的输入数据和参数
        """
        # 如果是问候语请求，修改输入
        if input_data.query.lower() in ["hi", "hello", "你好"]:
            # 添加问候语到历史
            greeting = self.tools[0].get_response_template("greeting")
            self.add_to_history("assistant", greeting)
            # 设置标记，让step直接返回问候语
            kwargs["_greeting_response"] = (greeting, 1.0, False, False, {})
            
        return input_data, kwargs
    
    async def step(self, query: str, **kwargs) -> Tuple[str, float, bool, bool, Dict[str, Any]]:
        """
        处理用户查询
        Args:
            query: 用户的查询内容
            **kwargs: 其他参数，传递给brain
        Returns:
            Tuple[response, score, terminated, truncated, info]
        """
        # 如果pre_step处理了问候语，直接返回结果
        if "_greeting_response" in kwargs:
            return kwargs.pop("_greeting_response")
            
        # 使用基类的step方法处理查询
        return await super().step(query, **kwargs)
    
    def get_greeting(self) -> str:
        """获取问候语"""
        return self.tools[0].get_response_template("greeting") 