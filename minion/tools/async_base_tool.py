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

from .base_tool import get_json_schema, get_imports

T = TypeVar('T', bound='AsyncBaseTool')


class AsyncBaseTool(ABC):
    """异步工具基类，定义所有异步工具的基本接口"""
    
    name: str = "async_base_tool"
    description: str = "异步基础工具类，所有异步工具应继承此类"
    inputs: Dict[str, Dict[str, Any]] = {}
    output_type: str = "any"
    
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


def async_tool(tool_function: Callable) -> AsyncBaseTool:
    """
    装饰器，将异步函数转换为AsyncBaseTool实例
    
    Args:
        tool_function: 要转换为异步工具的函数（应该是async函数）
            应该为每个输入和输出提供类型提示
            应该有包含函数描述和'Args:'部分的文档字符串
            
    Returns:
        AsyncBaseTool: 基于异步函数创建的工具实例
    """
    if not asyncio.iscoroutinefunction(tool_function):
        raise ValueError("tool_function must be an async function")
        
    tool_json_schema = get_json_schema(tool_function)["function"]
    
    class SimpleAsyncTool(AsyncBaseTool):
        name = tool_json_schema["name"]
        description = tool_json_schema["description"]
        inputs = tool_json_schema["parameters"]["properties"]
        output_type = tool_json_schema["return"]["type"]
        
        def __init__(self):
            super().__init__()
            self.is_initialized = True
        
        async def forward(self, *args, **kwargs):
            return await tool_function(*args, **kwargs)
    
    # 获取工具函数的签名参数
    sig = inspect.signature(tool_function)
    # 添加"self"作为第一个参数
    new_sig = sig.replace(
        parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)] + list(sig.parameters.values())
    )
    # 设置forward方法的签名
    SimpleAsyncTool.forward.__signature__ = new_sig
    
    # 获取工具函数的源代码
    try:
        tool_source = inspect.getsource(tool_function)
        # 移除装饰器和函数定义行
        tool_source_lines = tool_source.split('\n')
        # 查找实际函数体开始的行
        for i, line in enumerate(tool_source_lines):
            if line.strip().startswith("async def ") and tool_function.__name__ in line:
                tool_source_body = '\n'.join(tool_source_lines[i+1:])
                break
        else:
            tool_source_body = '\n'.join(tool_source_lines[1:])
        
        # 去除缩进
        tool_source_body = textwrap.dedent(tool_source_body)
        # 创建async forward方法源码，包括def行和缩进
        forward_method_source = f"async def forward{str(new_sig)}:\n{textwrap.indent(tool_source_body, '    ')}"
        # 创建class源码
        class_source = (
            textwrap.dedent(f'''
            class SimpleAsyncTool(AsyncTool):
                name: str = "{tool_json_schema["name"]}"
                description: str = {json.dumps(textwrap.dedent(tool_json_schema["description"]).strip())}
                inputs: dict[str, dict[str, str]] = {tool_json_schema["parameters"]["properties"]}
                output_type: str = "{tool_json_schema["return"]["type"]}"

                def __init__(self):
                    self.is_initialized = True

            ''')
            + textwrap.indent(forward_method_source, "    ")  # indent for class method
        )
        # 赋值到__source__属性
        setattr(SimpleAsyncTool, '__source__', class_source)
        setattr(SimpleAsyncTool.forward, '__source__', forward_method_source)
    except (IOError, TypeError):
        # 无法获取源代码时
        setattr(SimpleAsyncTool, '__source__', None)
        setattr(SimpleAsyncTool.forward, '__source__', None)
    
    async_function_tool = SimpleAsyncTool()
    return async_function_tool


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
        self.is_initialized = True
    
    async def forward(self, *args, **kwargs):
        """
        在执行器中运行同步工具
        使用 asyncio.get_event_loop().run_in_executor 避免阻塞
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.sync_tool.forward(*args, **kwargs))


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