from enum import Enum, auto
from typing import Dict, Type

class ImproveRoute(Enum):
    """改进路由的枚举类"""
    FEEDBACK = "feedback"
    REASONING = "reasoning"
    STEP_BY_STEP = "step_by_step"
    
    @classmethod
    def get_route(cls, route_name: str) -> "ImproveRoute":
        """根据字符串获取对应的改进路由
        
        Args:
            route_name: 路由名称字符串
            
        Returns:
            ImproveRoute: 匹配的改进路由，如果没有匹配项则返回默认的 FEEDBACK 路由
        """
        from minion.main.minion import IMPROVER_MINIONS
        route_name = route_name.lower()
        return IMPROVER_MINIONS.get(route_name, IMPROVER_MINIONS.get(cls.FEEDBACK))