#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024
@Author  : femto Zheng
@File    : async_base_tool.py
"""
# Async version of base_tool.py for asynchronous tool support

import asyncio
import inspect
import json
import textwrap
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, List, Union, Set, TypeVar, get_type_hints, Awaitable
import functools
import ast
import sys

# 将get_imports函数直接定义在这里以避免循环导入
def get_imports(code: str):
    """获取代码中的导入模块"""
    import ast
    imports = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
    except:
        pass
    return imports

T = TypeVar('T', bound='AsyncBaseTool')


class AsyncBaseTool(ABC):
    """异步工具基类，定义所有异步工具的基本接口"""
    
    name: str = "async_base_tool"
    description: str = "异步基础工具类，所有异步工具应继承此类"
    inputs: Dict[str, Dict[str, Any]] = {}
    output_type: str
    output_schema: dict[str, Any] | None = None #not used now
    readonly: bool = False
    needs_state: bool = False  # 是否需要接收agent state
    
    def __init__(self):
        """初始化异步工具"""
        self.is_initialized = False
        
    async def __call__(self, *args, **kwargs) -> Any:
        """
        异步调用工具执行，这是工具的主入口
        
        Returns:
            工具执行结果
        """
        if not self.is_initialized:
            await self.setup()
            
        # 处理传入单一字典的情况
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
            potential_kwargs = args[0]
            if all(key in self.inputs for key in potential_kwargs):
                args = ()
                kwargs = potential_kwargs
                
        return await self.forward(*args, **kwargs)
    
    @abstractmethod
    async def forward(self, *args, **kwargs) -> Any:
        """
        实际的异步工具执行逻辑，子类必须实现此方法

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            工具执行结果
        """
        raise NotImplementedError("异步工具子类必须实现forward方法")

    def format_for_observation(self, output: Any) -> str:
        """
        Format tool output for LLM observation (when tool call is the last item in code).

        This method can be overridden by tools to provide LLM-friendly formatting
        of their output when used as observations. For example:
        - file_read tool can add line numbers
        - search tool can format results with highlighting
        - calculator tool can show step-by-step computation

        Args:
            output: The raw output from forward() method

        Returns:
            Formatted string suitable for LLM observation

        Default behavior: Convert output to string
        """
        return str(output) if output is not None else ""
    
    async def setup(self):
        """
        在首次使用前执行异步初始化操作
        用于执行耗时的异步初始化操作（如异步加载模型、建立网络连接等）
        """
        self.is_initialized = True
        
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典表示
        
        Returns:
            工具的字典表示
        """
        imports = set()
        tool_code = f"""
class {self.__class__.__name__}(AsyncBaseTool):
    name = "{self.name}"
    description = "{self.description}"
    inputs = {repr(self.inputs)}
    output_type = "{self.output_type}"
    readonly = {self.readonly}
    
    def __init__(self):
        super().__init__()
        self.is_initialized = True
        
    async def forward(self, *args, **kwargs):
        # 实现异步工具的逻辑
        pass
"""
        imports = get_imports(tool_code)
        requirements = {el for el in imports if el not in sys.stdlib_module_names}
        
        return {
            "name": self.name,
            "code": tool_code,
            "requirements": sorted(list(requirements))
        }


class SyncToAsyncToolAdapter(AsyncBaseTool):
    """
    适配器类，将同步工具转换为异步工具
    这允许在异步执行器中使用现有的同步工具
    """

    def __init__(self, sync_tool):
        super().__init__()
        self.sync_tool = sync_tool
        self.name = sync_tool.name
        self.description = sync_tool.description
        self.inputs = sync_tool.inputs
        self.output_type = sync_tool.output_type
        self.readonly = sync_tool.readonly
        self.is_initialized = True

    async def forward(self, *args, **kwargs):
        """
        在执行器中运行同步工具
        使用 asyncio.get_event_loop().run_in_executor 避免阻塞
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.sync_tool.forward(*args, **kwargs))

    def format_for_observation(self, output: Any) -> str:
        """
        Delegate observation formatting to the wrapped sync tool
        """
        return self.sync_tool.format_for_observation(output)


class AsyncToolCollection:
    """异步工具集合，用于管理多个异步工具"""
    
    def __init__(self, tools: List[AsyncBaseTool]):
        self.tools = tools
        
    @classmethod
    def from_directory(cls, directory_path: str) -> 'AsyncToolCollection':
        """从目录加载所有异步工具"""
        # 实现从目录加载异步工具的逻辑
        # TODO: 实现具体逻辑
        return cls([])
    
    async def setup_all(self):
        """异步初始化所有工具"""
        await asyncio.gather(*[tool.setup() for tool in self.tools if not tool.is_initialized])