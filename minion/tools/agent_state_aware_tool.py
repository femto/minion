#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent状态感知的Meta工具基类
"""
import inspect
from typing import Any, Dict, Optional
from .async_base_tool import AsyncBaseTool

class AgentStateAwareTool(AsyncBaseTool):
    """
    支持访问agent状态但对LLM透明的meta工具基类
    
    特点：
    1. 能够通过调用栈发现agent上下文
    2. 对LLM不可见（不出现在functions命名空间）
    3. 可以访问Brain、state、Input等agent内部状态
    """
    
    def __init__(self):
        super().__init__()
        self._agent_context = None
        self._is_meta_tool = True  # 标记为meta工具
        
    async def __call__(self, *args, **kwargs):
        """调用前自动发现agent上下文"""
        self._agent_context = self._discover_agent_context()
        return await super().__call__(*args, **kwargs)
    
    def _discover_agent_context(self) -> Optional[Dict[str, Any]]:
        """
        通过调用栈发现agent状态
        
        Returns:
            Dict包含: brain, state, input, agent等引用
        """
        frame = inspect.currentframe()
        context = {}
        
        try:
            # 向上遍历调用栈
            while frame:
                locals_vars = frame.f_locals
                
                # 查找Brain实例
                if 'brain' in locals_vars:
                    context['brain'] = locals_vars['brain']
                
                # 查找state字典
                if 'state' in locals_vars and isinstance(locals_vars['state'], dict):
                    context['state'] = locals_vars['state']
                
                # 查找Input对象
                if 'input' in locals_vars:
                    context['input'] = locals_vars['input']
                
                # 查找Agent实例（如果有）
                if 'self' in locals_vars:
                    obj = locals_vars['self']
                    # 检查是否是Agent或Brain类的实例
                    if hasattr(obj, 'brain') and hasattr(obj, 'run_async'):
                        context['agent'] = obj
                    elif hasattr(obj, 'step') and hasattr(obj, 'tools'):
                        context['brain'] = obj
                
                frame = frame.f_back
                
        finally:
            del frame  # 避免循环引用
        
        return context if context else None
    
    def get_agent_state(self) -> Dict[str, Any]:
        """获取agent状态，安全访问"""
        if not self._agent_context:
            return {}
        return self._agent_context.get('state', {})
    
    def get_brain(self):
        """获取Brain实例"""
        if not self._agent_context:
            return None
        return self._agent_context.get('brain')
    
    def get_input(self):
        """获取当前Input对象"""
        if not self._agent_context:
            return None
        return self._agent_context.get('input')
    
    def get_agent(self):
        """获取Agent实例（如果有）"""
        if not self._agent_context:
            return None
        return self._agent_context.get('agent')