#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multi Tool Use Module - 处理GPT生成的并行工具调用

这个模块拦截GPT生成的 `from multi_tool_use import parallel` 调用，
并提供实际的并行工具执行功能。
"""

import asyncio
import inspect
from typing import List, Dict, Any, Union


async def parallel(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    并行执行多个工具调用
    
    Args:
        config: 包含 tool_uses 列表的配置字典
        
    Returns:
        包含所有工具执行结果的字典
    """
    tool_uses = config.get("tool_uses", [])
    if not tool_uses:
        return {"results": [], "error": "No tool_uses provided"}
    
    # 获取当前执行环境中的工具
    frame = inspect.currentframe()
    tools_dict = {}
    
    # 遍历调用栈，查找可用的工具
    while frame:
        local_vars = frame.f_locals
        global_vars = frame.f_globals
        
        # 优先查找 static_tools（AsyncPythonExecutor 中的工具）
        if 'static_tools' in local_vars:
            static_tools = local_vars['static_tools']
            if isinstance(static_tools, dict):
                # 直接查找 functions 命名空间
                if 'functions' in static_tools:
                    functions_ns = static_tools['functions']
                    if hasattr(functions_ns, '__dict__'):
                        for attr_name in dir(functions_ns):
                            if not attr_name.startswith('_'):
                                tool = getattr(functions_ns, attr_name)
                                if callable(tool):
                                    tools_dict[f"functions.{attr_name}"] = tool
                
                # 也查找其他工具
                for name, tool in static_tools.items():
                    if name == 'functions':
                        continue  # 已经处理过了
                    if callable(tool) and hasattr(tool, '__name__'):
                        tools_dict[f"functions.{tool.__name__}"] = tool
                    elif hasattr(tool, 'name') and hasattr(tool, 'forward'):
                        tools_dict[f"functions.{tool.name}"] = tool
                    elif callable(tool):
                        tools_dict[f"functions.{name}"] = tool
                        
        # 检查全局和局部变量中的 functions 命名空间
        for vars_dict in [local_vars, global_vars]:
            if 'functions' in vars_dict:
                functions_obj = vars_dict['functions']
                if hasattr(functions_obj, '__dict__') or hasattr(functions_obj, '__dir__'):
                    for attr_name in dir(functions_obj):
                        if not attr_name.startswith('_'):
                            attr_value = getattr(functions_obj, attr_name)
                            if callable(attr_value):
                                tools_dict[f"functions.{attr_name}"] = attr_value
        
        # 检查 __main__ 执行环境中的工具
        if '__name__' in local_vars and local_vars.get('__name__') == '__main__':
            for name, obj in local_vars.items():
                if name.startswith('async_') and callable(obj):
                    tools_dict[f"functions.{name}"] = obj
        
        # 查找工具函数和对象
        for name, obj in {**local_vars, **global_vars}.items():
            if callable(obj) and hasattr(obj, '__name__'):
                if obj.__name__.startswith('async_') or obj.__name__.endswith('_tool'):
                    tools_dict[f"functions.{obj.__name__}"] = obj
            elif hasattr(obj, 'name') and hasattr(obj, 'forward'):
                # BaseTool或AsyncBaseTool实例
                tools_dict[f"functions.{obj.name}"] = obj
        
        frame = frame.f_back
    
    # 准备并行执行的任务
    tasks = []
    
    for tool_use in tool_uses:
        recipient_name = tool_use.get("recipient_name", "")
        parameters = tool_use.get("parameters", {})
        
        # 查找对应的工具
        tool = tools_dict.get(recipient_name)
        if not tool:
            # 尝试不带 functions. 前缀
            tool_name = recipient_name.replace("functions.", "")
            tool = tools_dict.get(f"functions.{tool_name}")
        
        if tool:
            # 创建工具调用任务
            task = _execute_single_tool(tool, parameters, recipient_name)
            tasks.append(task)
        else:
            # 工具未找到，添加错误结果
            tasks.append(_create_error_result(recipient_name, "Tool not found"))
    
    # 并行执行所有任务
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 格式化结果
    formatted_results = []
    for i, result in enumerate(results):
        tool_use = tool_uses[i]
        if isinstance(result, Exception):
            formatted_results.append({
                "recipient_name": tool_use.get("recipient_name", ""),
                "error": str(result),
                "success": False
            })
        elif isinstance(result, dict) and "error" in result:
            # 处理错误结果（如 Tool not found）
            formatted_results.append({
                "recipient_name": tool_use.get("recipient_name", ""),
                "error": result.get("error", "Unknown error"),
                "success": False
            })
        else:
            formatted_results.append({
                "recipient_name": tool_use.get("recipient_name", ""),
                "result": result,
                "success": True
            })
    
    return {
        "results": formatted_results,
        "total_calls": len(tool_uses),
        "successful_calls": sum(1 for r in formatted_results if r.get("success", False)),
        "failed_calls": sum(1 for r in formatted_results if not r.get("success", False))
    }


async def _execute_single_tool(tool: Any, parameters: Dict[str, Any], tool_name: str) -> Any:
    """
    执行单个工具
    
    Args:
        tool: 工具对象或函数
        parameters: 参数字典
        tool_name: 工具名称
        
    Returns:
        工具执行结果
    """
    try:
        # 处理字符串类型的数值参数
        processed_params = {}
        for key, value in parameters.items():
            if isinstance(value, str):
                # 尝试转换数字字符串，但更保守一些
                if value.replace('.', '').replace('-', '').isdigit():
                    # 包含小数点的浮点数
                    if '.' in value:
                        try:
                            processed_params[key] = float(value)
                        except ValueError:
                            processed_params[key] = value
                    # 纯整数
                    else:
                        try:
                            processed_params[key] = int(value)
                        except ValueError:
                            processed_params[key] = value
                else:
                    # 保持为字符串
                    processed_params[key] = value
            else:
                processed_params[key] = value
        
        # 检查工具类型并调用
        if hasattr(tool, 'forward'):
            # BaseTool或AsyncBaseTool实例
            if asyncio.iscoroutinefunction(tool.forward):
                result = await tool.forward(**processed_params)
            else:
                result = tool.forward(**processed_params)
        elif callable(tool):
            # 普通函数或异步函数
            if asyncio.iscoroutinefunction(tool):
                result = await tool(**processed_params)
            else:
                result = tool(**processed_params)
        else:
            raise ValueError(f"Tool {tool_name} is not callable")
        
        # 添加调试信息，同时确保结果正确返回
        print(f"Tool {tool_name.replace('functions.', '')} execution result: {result}")
        return result
        
    except Exception as e:
        raise Exception(f"Error executing {tool_name}: {str(e)}")


async def _create_error_result(tool_name: str, error_message: str) -> Dict[str, Any]:
    """创建错误结果"""
    return {
        "error": error_message,
        "tool_name": tool_name
    }


def smart_parallel(config: Union[Dict[str, Any], List[Dict[str, Any]], None] = None, **kwargs) -> Union[Dict[str, Any], Any]:
    """
    智能的并行工具执行，自动检测异步环境和参数格式
    
    Args:
        config: 包含 tool_uses 列表的配置字典，或者直接传递工具列表
        **kwargs: 支持 tool_uses 等关键字参数
        
    Returns:
        包含所有工具执行结果的字典
    """
    # 处理不同的调用方式
    if config is None and 'tool_uses' in kwargs:
        # parallel(tool_uses=[...]) 调用方式
        config = {"tool_uses": kwargs['tool_uses']}
    elif isinstance(config, list):
        # parallel([...]) 调用方式
        config = {"tool_uses": config}
    elif not isinstance(config, dict) or "tool_uses" not in config:
        raise ValueError("参数必须是包含 'tool_uses' 键的字典，或者直接传递工具列表，或者使用 tool_uses 关键字参数")
    
    # 尝试同步执行，避免复杂的异步检测
    try:
        # 检查是否已经在事件循环中
        loop = asyncio.get_running_loop()
        # 在异步环境中，创建新的事件循环来执行
        import threading
        import concurrent.futures
        
        def run_in_thread():
            return asyncio.run(parallel(config))
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result()
            
    except RuntimeError:
        # 没有运行中的循环，直接同步执行
        return asyncio.run(parallel(config))


# 为了兼容性，也提供同步版本
def parallel_sync(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    同步版本的并行工具执行（实际上会在内部使用异步）
    
    Args:
        config: 包含 tool_uses 列表的配置字典
        
    Returns:
        包含所有工具执行结果的字典
    """
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已经在异步环境中，创建任务
            task = asyncio.create_task(parallel(config))
            return task
        else:
            # 如果不在异步环境中，运行异步函数
            return loop.run_until_complete(parallel(config))
    except RuntimeError:
        # 没有事件循环，创建新的
        return asyncio.run(parallel(config))


# 默认导出智能版本和异步版本
__all__ = ["parallel", "smart_parallel", "parallel_sync"]