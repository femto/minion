from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import uuid

from .base_agent import BaseAgent
from ..main.input import Input

@dataclass
class ConversationalAgent(BaseAgent):
    """对话型Agent基类，提供对话历史管理功能"""
    
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    
    async def post_step(self, input_data: Input, result: Tuple[Any, float, bool, bool, Dict[str, Any]]) -> None:
        """
        记录对话历史
        Args:
            input_data: 输入数据
            result: step的执行结果
        """
        # 记录用户输入
        self.add_to_history("user", input_data.query)
        
        # 记录系统响应
        self.add_to_history("assistant", result[0])
    
    def clear_history(self) -> None:
        """清除对话历史"""
        self.conversation_history = []
        # 清除历史时生成新的session_id
        self.session_id = str(uuid.uuid4())
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return self.conversation_history
    
    def add_to_history(self, role: str, content: Any) -> None:
        """
        添加记录到对话历史
        Args:
            role: 角色（如user、assistant等）
            content: 内容
        """
        self.conversation_history.append({
            "role": role,
            "content": content
        }) 