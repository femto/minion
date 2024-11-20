from enum import Enum, auto

class ImproveRoute(Enum):
    """改进路由的枚举类"""
    FEEDBACK = "feedback"
    REASONING = "reasoning"
    STEP_BY_STEP = "step_by_step"
    
    @classmethod
    def get_route(cls, route_name: str) -> "ImproveRoute":
        """根据字符串获取对应的改进路由"""
        try:
            return cls(route_name.lower()) #or use llm to recommendend improve route?
        except ValueError:
            return cls.FEEDBACK  # 默认返回 feedback 路由 