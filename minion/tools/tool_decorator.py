#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024
@Author  : femto Zheng
@File    : tool_decorator.py
"""

import asyncio
import inspect
import json
import textwrap
import warnings
import ast
from functools import wraps
from typing import Callable, Union

from .base_tool import BaseTool, get_json_schema
from .async_base_tool import AsyncBaseTool


class TypeHintParsingException(Exception):
    """工具类型提示解析异常"""
    pass


def tool(tool_function: Callable) -> Union[BaseTool, AsyncBaseTool]:
    """
    统一装饰器，将函数转换为相应的工具实例
    - 同步函数转换为BaseTool子类
    - 异步函数转换为AsyncBaseTool子类
    
    Args:
        tool_function (Callable): 要转换为工具的函数
            应该为每个输入和输出提供类型提示
            应该有包含函数描述和'Args:'部分的文档字符串
            
    Returns:
        Union[BaseTool, AsyncBaseTool]: 基于函数创建的工具实例
    """
    # 检查是否为异步函数
    is_async = asyncio.iscoroutinefunction(tool_function)
    
    # 获取JSON schema
    tool_json_schema = get_json_schema(tool_function)["function"]
    
    # 检查返回类型
    if "return" not in tool_json_schema:
        if len(tool_json_schema["parameters"]["properties"]) == 0:
            tool_json_schema["return"] = {"type": "null"}
        else:
            raise TypeHintParsingException(
                "Tool return type not found: make sure your function has a return type hint!"
            )
    
    if is_async:
        # 创建异步工具类
        @wraps(tool_function)
        async def wrapped_async_function(self, *args, **kwargs):
            return await tool_function(*args, **kwargs)
        
        class SimpleAsyncTool(AsyncBaseTool):
            def __init__(self):
                super().__init__()
                self.is_initialized = True
            
            # 直接定义forward方法
            forward = wrapped_async_function
        
        # 设置类属性
        SimpleAsyncTool.name = tool_json_schema["name"]
        SimpleAsyncTool.description = tool_json_schema["description"]
        SimpleAsyncTool.inputs = tool_json_schema["parameters"]["properties"]
        SimpleAsyncTool.output_type = tool_json_schema["return"]["type"]
        
        # 设置输出schema（如果存在）
        if "output_schema" in tool_json_schema:
            SimpleAsyncTool.output_schema = tool_json_schema["output_schema"]
        elif "return" in tool_json_schema and "schema" in tool_json_schema["return"]:
            SimpleAsyncTool.output_schema = tool_json_schema["return"]["schema"]
        
        # 获取签名参数并添加self
        sig = inspect.signature(tool_function)
        new_sig = sig.replace(
            parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)] + list(sig.parameters.values())
        )
        SimpleAsyncTool.forward.__signature__ = new_sig
        
        # 创建并附加源代码
        _attach_source_code(SimpleAsyncTool, tool_function, tool_json_schema, is_async=True)
        
        return SimpleAsyncTool()
    
    else:
        # 创建同步工具类
        @wraps(tool_function)
        def wrapped_function(self, *args, **kwargs):
            return tool_function(*args, **kwargs)
        
        class SimpleTool(BaseTool):
            def __init__(self):
                super().__init__()
                self.is_initialized = True
            
            # 直接定义forward方法
            forward = wrapped_function
        
        # 设置类属性
        SimpleTool.name = tool_json_schema["name"]
        SimpleTool.description = tool_json_schema["description"]
        SimpleTool.inputs = tool_json_schema["parameters"]["properties"]
        SimpleTool.output_type = tool_json_schema["return"]["type"]
        
        # 设置输出schema（如果存在）
        if "output_schema" in tool_json_schema:
            SimpleTool.output_schema = tool_json_schema["output_schema"]
        elif "return" in tool_json_schema and "schema" in tool_json_schema["return"]:
            SimpleTool.output_schema = tool_json_schema["return"]["schema"]
        
        # 获取签名参数并添加self
        sig = inspect.signature(tool_function)
        new_sig = sig.replace(
            parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)] + list(sig.parameters.values())
        )
        SimpleTool.forward.__signature__ = new_sig
        
        # 创建并附加源代码
        _attach_source_code(SimpleTool, tool_function, tool_json_schema, is_async=False)
        
        return SimpleTool()


def _attach_source_code(tool_class, tool_function, tool_json_schema, is_async=False):
    """
    为动态创建的工具类和forward方法附加源代码
    
    Args:
        tool_class: 动态创建的工具类
        tool_function: 原始工具函数
        tool_json_schema: 工具的JSON schema
        is_async: 是否为异步函数
    """
    try:
        # 获取工具函数的源代码
        tool_source = textwrap.dedent(inspect.getsource(tool_function))
        
        # 移除装饰器和函数定义行
        lines = tool_source.splitlines()
        tree = ast.parse(tool_source)
        
        # 查找函数定义（包括异步函数）
        func_node = next((node for node in ast.walk(tree) 
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
        if not func_node:
            raise ValueError(
                f"No function definition found in the provided source of {tool_function.__name__}. "
                "Ensure the input is a standard function."
            )
        
        # 提取装饰器行
        decorator_lines = ""
        if func_node.decorator_list:
            tool_decorators = [d for d in func_node.decorator_list if isinstance(d, ast.Name) and d.id == "tool"]
            if len(tool_decorators) > 1:
                raise ValueError(
                    f"Multiple @tool decorators found on function '{func_node.name}'. Only one @tool decorator is allowed."
                )
            if len(tool_decorators) < len(func_node.decorator_list):
                warnings.warn(
                    f"Function '{func_node.name}' has decorators other than @tool. "
                    "This may cause issues with serialization in the remote executor. See issue #1626."
                )
            if tool_decorators:
                decorator_start = tool_decorators[0].lineno - 1
                decorator_end = func_node.decorator_list[-1].lineno - 1
                decorator_lines = "\n".join(lines[decorator_start:decorator_end + 1])
        
        # 提取工具源代码主体
        body_start = func_node.body[0].lineno - 1  # AST lineno从1开始
        tool_source_body = "\n".join(lines[body_start:])
        
        # 获取新的签名
        new_sig = tool_class.forward.__signature__
        
        # 创建forward方法源代码，包括def行和缩进
        if is_async:
            forward_method_source = f"async def forward{new_sig}:\n{tool_source_body}"
            base_class_name = "AsyncBaseTool"
        else:
            forward_method_source = f"def forward{new_sig}:\n{tool_source_body}"
            base_class_name = "BaseTool"
        
        # 创建类源代码
        indent = " " * 4  # 类方法缩进
        class_source = (
            textwrap.dedent(f'''
            class SimpleTool({base_class_name}):
                name: str = "{tool_json_schema["name"]}"
                description: str = {json.dumps(textwrap.dedent(tool_json_schema["description"]).strip())}
                inputs: dict[str, dict[str, str]] = {tool_json_schema["parameters"]["properties"]}
                output_type: str = "{tool_json_schema["return"]["type"]}"

                def __init__(self):
                    self.is_initialized = True

            ''')
            + textwrap.indent(decorator_lines, indent)
            + textwrap.indent(forward_method_source, indent)
        )
        
        # 存储源代码到类和方法上以供检查
        tool_class.__source__ = class_source
        tool_class.forward.__source__ = forward_method_source
        
    except (IOError, TypeError, OSError):
        # 无法获取源代码时设置为None
        tool_class.__source__ = None
        tool_class.forward.__source__ = None