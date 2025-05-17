#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024
@Author  : femto Zheng
@File    : base_tool.py
"""
#modified from smolagents

from abc import ABC, abstractmethod
import inspect
import json
import textwrap
from typing import Any, Dict, Optional, Callable, List, Union, Set, TypeVar, get_type_hints
import functools
import ast
import sys

T = TypeVar('T', bound='BaseTool')

def get_json_schema(func: Callable) -> Dict[str, Any]:
    """从函数提取JSON schema定义"""
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""
    
    # 获取函数名和描述
    description = doc.split('\n\n')[0] if doc else ""
    
    # 从docstring解析参数描述
    param_descriptions = {}
    if 'Args:' in doc:
        args_section = doc.split('Args:')[1].split('Returns:')[0] if 'Returns:' in doc else doc.split('Args:')[1]
        for line in args_section.strip().split('\n'):
            if ':' in line:
                param_name = line.split(':')[0].strip()
                param_desc = line.split(':', 1)[1].strip()
                param_descriptions[param_name] = param_desc
    
    # 获取类型提示
    type_hints = get_type_hints(func)
    
    # 构建参数属性
    properties = {}
    for name, param in sig.parameters.items():
        if name in type_hints:
            param_type = type_hints[name]
            type_name = str(param_type)
            
            # 转换类型名到JSON schema类型
            json_type = "string"
            if "str" in type_name:
                json_type = "string"
            elif "int" in type_name:
                json_type = "integer"
            elif "float" in type_name:
                json_type = "number"
            elif "bool" in type_name:
                json_type = "boolean"
            elif "list" in type_name or "List" in type_name:
                json_type = "array"
            elif "dict" in type_name or "Dict" in type_name:
                json_type = "object"
            
            # 检查参数是否可选
            is_optional = "Optional" in type_name or param.default != inspect.Parameter.empty
            
            properties[name] = {
                "type": json_type,
                "description": param_descriptions.get(name, ""),
            }
            
            if is_optional:
                properties[name]["nullable"] = True
    
    # 获取返回类型
    return_type = "any"
    if "return" in type_hints:
        return_type_str = str(type_hints["return"])
        if "str" in return_type_str:
            return_type = "string"
        elif "int" in return_type_str:
            return_type = "integer"
        elif "float" in return_type_str:
            return_type = "number"
        elif "bool" in return_type_str:
            return_type = "boolean"
        elif "list" in return_type_str or "List" in return_type_str:
            return_type = "array"
        elif "dict" in return_type_str or "Dict" in return_type_str:
            return_type = "object"
    
    return {
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": [
                    name for name, param in sig.parameters.items() 
                    if param.default == inspect.Parameter.empty
                ]
            },
            "return": {
                "type": return_type
            }
        }
    }

def get_imports(code: str) -> Set[str]:
    """获取代码中的导入模块"""
    imports = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except SyntaxError:
        # 语法错误时返回空集合
        pass
    return imports

class BaseTool(ABC):
    """工具基类，定义所有工具的基本接口"""
    
    name: str = "base_tool"
    description: str = "基础工具类，所有工具应继承此类"
    inputs: Dict[str, Dict[str, Any]] = {}
    output_type: str = "any"
    
    def __init__(self):
        """初始化工具"""
        self.is_initialized = False
        
    def __call__(self, *args, **kwargs) -> Any:
        """
        调用工具执行，这是工具的主入口
        
        Returns:
            工具执行结果
        """
        if not self.is_initialized:
            self.setup()
            
        # 处理传入单一字典的情况
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
            potential_kwargs = args[0]
            if all(key in self.inputs for key in potential_kwargs):
                args = ()
                kwargs = potential_kwargs
                
        return self.forward(*args, **kwargs)
    
    @abstractmethod
    def forward(self, *args, **kwargs) -> Any:
        """
        实际的工具执行逻辑，子类必须实现此方法
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            工具执行结果
        """
        raise NotImplementedError("工具子类必须实现forward方法")
    
    def setup(self):
        """
        在首次使用前执行初始化操作
        用于执行耗时的初始化操作（如加载模型）
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
class {self.__class__.__name__}(BaseTool):
    name = "{self.name}"
    description = "{self.description}"
    inputs = {repr(self.inputs)}
    output_type = "{self.output_type}"
    
    def __init__(self):
        super().__init__()
        self.is_initialized = True
        
    def forward(self, *args, **kwargs):
        # 实现工具的逻辑
        pass
"""
        imports = get_imports(tool_code)
        requirements = {el for el in imports if el not in sys.stdlib_module_names}
        
        return {
            "name": self.name,
            "code": tool_code,
            "requirements": sorted(list(requirements))
        }

def tool(tool_function: Callable) -> BaseTool:
    """
    装饰器，将函数转换为BaseTool实例
    
    Args:
        tool_function: 要转换为工具的函数
            应该为每个输入和输出提供类型提示
            应该有包含函数描述和'Args:'部分的文档字符串
            
    Returns:
        BaseTool: 基于函数创建的工具实例
    """
    tool_json_schema = get_json_schema(tool_function)["function"]
    
    class SimpleTool(BaseTool):
        name = tool_json_schema["name"]
        description = tool_json_schema["description"]
        inputs = tool_json_schema["parameters"]["properties"]
        output_type = tool_json_schema["return"]["type"]
        
        def __init__(self):
            super().__init__()
            self.is_initialized = True
        
        def forward(self, *args, **kwargs):
            return tool_function(*args, **kwargs)
    
    # 获取工具函数的签名参数
    sig = inspect.signature(tool_function)
    # 添加"self"作为第一个参数
    new_sig = sig.replace(
        parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)] + list(sig.parameters.values())
    )
    # 设置forward方法的签名
    SimpleTool.forward.__signature__ = new_sig
    
    # 获取工具函数的源代码
    try:
        tool_source = inspect.getsource(tool_function)
        # 移除装饰器和函数定义行
        tool_source_lines = tool_source.split('\n')
        # 查找实际函数体开始的行
        for i, line in enumerate(tool_source_lines):
            if line.strip().startswith("def ") and tool_function.__name__ in line:
                tool_source_body = '\n'.join(tool_source_lines[i+1:])
                break
        else:
            tool_source_body = '\n'.join(tool_source_lines[1:])
        
        # 去除缩进
        tool_source_body = textwrap.dedent(tool_source_body)
        # 创建forward方法源码，包括def行和缩进
        forward_method_source = f"def forward{str(new_sig)}:\n{textwrap.indent(tool_source_body, '    ')}"
        # 创建class源码
        class_source = (
            textwrap.dedent(f'''
            class SimpleTool(Tool):
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
        SimpleTool.__source__ = class_source
        SimpleTool.forward.__source__ = forward_method_source
    except (IOError, TypeError):
        # 无法获取源代码时
        SimpleTool.__source__ = None
        SimpleTool.forward.__source__ = None
    
    function_tool = SimpleTool()
    return function_tool

class ToolCollection:
    """工具集合，用于管理多个工具"""
    
    def __init__(self, tools: List[BaseTool]):
        self.tools = tools
        
    @classmethod
    def from_directory(cls, directory_path: str) -> 'ToolCollection':
        """从目录加载所有工具"""
        # 实现从目录加载工具的逻辑
        pass 