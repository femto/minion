from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class BaseTool:
    """工具基类，定义所有工具的基本接口"""
    
    name: str = "base_tool"
    description: str = "基础工具接口"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具的核心功能
        Args:
            **kwargs: 工具执行所需的参数
        Returns:
            执行结果
        """
        raise NotImplementedError("Tool must implement execute method")
    
    def validate_input(self, **kwargs) -> bool:
        """
        验证输入参数
        Args:
            **kwargs: 需要验证的参数
        Returns:
            验证是否通过
        """
        return True
    
    def format_output(self, result: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        格式化输出结果
        Args:
            result: 原始结果
            context: 上下文信息
        Returns:
            格式化后的结果
        """
        return result 