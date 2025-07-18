#!/usr/bin/env python
# coding=utf-8

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ast
import asyncio
import builtins
import difflib
import inspect
import logging
import math
import re
from collections.abc import Callable, Mapping, Awaitable
from functools import wraps
from importlib import import_module
from types import BuiltinFunctionType, FunctionType, ModuleType
from typing import Any, Union

from .local_python_executor import (
    BASE_BUILTIN_MODULES,
    MAX_LENGTH_TRUNCATE_CONTENT,
    BASE_PYTHON_TOOLS,
    DANGEROUS_MODULES,
    DANGEROUS_FUNCTIONS,
    ERRORS,
    DEFAULT_MAX_LEN_OUTPUT,
    MAX_OPERATIONS,
    MAX_WHILE_ITERATIONS,
    PrintContainer,
    BreakException,
    ContinueException,
    ReturnException,
    FinalAnswerException,
    InterpreterError,
    truncate_content,
    check_safer_result,
    safer_func,
    get_iterable,
    fix_final_answer_code,
    build_import_tree,
    check_import_authorized,
    get_safe_module,
    custom_print,
    nodunder_getattr,
)
from ..tools.async_base_tool import AsyncBaseTool, SyncToAsyncToolAdapter

logger = logging.getLogger(__name__)


def async_safer_eval(func: Callable):
    """
    Async decorator to enhance the security of an evaluation function by checking its return value.

    Args:
        func (Callable): Async evaluation function to be made safer.

    Returns:
        Callable: Safer evaluation function with return value check.
    """

    @wraps(func)
    async def _check_return(
        expression,
        state,
        static_tools,
        custom_tools,
        authorized_imports=BASE_BUILTIN_MODULES,
    ):
        result = await func(expression, state, static_tools, custom_tools, authorized_imports=authorized_imports)
        check_safer_result(result, static_tools, authorized_imports)
        return result

    return _check_return


def create_async_function(
    func_def: Union[ast.FunctionDef, ast.AsyncFunctionDef],
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> Callable:
    """
    Create a function (sync or async) from AST FunctionDef or AsyncFunctionDef
    """
    source_code = ast.unparse(func_def)
    is_async = isinstance(func_def, ast.AsyncFunctionDef)

    if is_async:
        async def new_async_func(*args: Any, **kwargs: Any) -> Any:
            func_state = state.copy()
            arg_names = [arg.arg for arg in func_def.args.args]
            default_values = []
            for d in func_def.args.defaults:
                default_values.append(await evaluate_async_ast(d, state, static_tools, custom_tools, authorized_imports))

            # Apply default values
            defaults = dict(zip(arg_names[-len(default_values) :], default_values))

            # Set positional arguments
            for name, value in zip(arg_names, args):
                func_state[name] = value

            # Set keyword arguments
            for name, value in kwargs.items():
                func_state[name] = value

            # Handle variable arguments
            if func_def.args.vararg:
                vararg_name = func_def.args.vararg.arg
                func_state[vararg_name] = args

            if func_def.args.kwarg:
                kwarg_name = func_def.args.kwarg.arg
                func_state[kwarg_name] = kwargs

            # Set default values for arguments that were not provided
            for name, value in defaults.items():
                if name not in func_state:
                    func_state[name] = value

            # Update function state with self and __class__
            if func_def.args.args and func_def.args.args[0].arg == "self":
                if args:
                    func_state["self"] = args[0]
                    func_state["__class__"] = args[0].__class__

            result = None
            try:
                for stmt in func_def.body:
                    result = await evaluate_async_ast(stmt, func_state, static_tools, custom_tools, authorized_imports)
            except ReturnException as e:
                result = e.value

            if func_def.name == "__init__":
                return None

            return result
        
        # Store original AST, source code, and name
        new_async_func.__ast__ = func_def
        new_async_func.__source__ = source_code
        new_async_func.__name__ = func_def.name
        return new_async_func
    else:
        # Use the existing create_function for sync functions
        from .local_python_executor import create_function
        return create_function(func_def, state, static_tools, custom_tools, authorized_imports)


def evaluate_async_function_def(
    func_def: Union[ast.FunctionDef, ast.AsyncFunctionDef],
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> Callable:
    """
    Evaluate a function definition (sync or async) and add it to custom tools
    """
    custom_tools[func_def.name] = create_async_function(func_def, state, static_tools, custom_tools, authorized_imports)
    return custom_tools[func_def.name]


async def evaluate_async_call(
    call: ast.Call,
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> Any:
    """
    Async version of evaluate_call that handles both sync and async tool calls.
    """
    if not isinstance(call.func, (ast.Call, ast.Lambda, ast.Attribute, ast.Name, ast.Subscript)):
        raise InterpreterError(f"This is not a correct function: {call.func}).")

    func, func_name = None, None

    if isinstance(call.func, ast.Call):
        func = await evaluate_async_ast(call.func, state, static_tools, custom_tools, authorized_imports)
    elif isinstance(call.func, ast.Lambda):
        func = await evaluate_async_ast(call.func, state, static_tools, custom_tools, authorized_imports)
    elif isinstance(call.func, ast.Attribute):
        obj = await evaluate_async_ast(call.func.value, state, static_tools, custom_tools, authorized_imports)
        func_name = call.func.attr
        if not hasattr(obj, func_name):
            raise InterpreterError(f"Object {obj} has no attribute {func_name}")
        func = getattr(obj, func_name)
    elif isinstance(call.func, ast.Name):
        func_name = call.func.id
        if func_name in state:
            func = state[func_name]
        elif func_name in static_tools:
            func = static_tools[func_name]
        elif func_name in custom_tools:
            func = custom_tools[func_name]
        elif func_name in ERRORS:
            func = ERRORS[func_name]
        else:
            raise InterpreterError(
                f"Forbidden function evaluation: '{call.func.id}' is not among the explicitly allowed tools or defined/imported in the preceding code"
            )
    elif isinstance(call.func, ast.Subscript):
        func = await evaluate_async_ast(call.func, state, static_tools, custom_tools, authorized_imports)
        if not callable(func):
            raise InterpreterError(f"This is not a correct function: {call.func}).")
        func_name = None

    args = []
    for arg in call.args:
        if isinstance(arg, ast.Starred):
            args.extend(await evaluate_async_ast(arg.value, state, static_tools, custom_tools, authorized_imports))
        else:
            args.append(await evaluate_async_ast(arg, state, static_tools, custom_tools, authorized_imports))

    kwargs = {}
    for keyword in call.keywords:
        kwargs[keyword.arg] = await evaluate_async_ast(keyword.value, state, static_tools, custom_tools, authorized_imports)

    if func_name == "super":
        if not args:
            if "__class__" in state and "self" in state:
                return super(state["__class__"], state["self"])
            else:
                raise InterpreterError("super() needs at least one argument")
        cls = args[0]
        if not isinstance(cls, type):
            raise InterpreterError("super() argument 1 must be type")
        if len(args) == 1:
            return super(cls)
        elif len(args) == 2:
            instance = args[1]
            return super(cls, instance)
        else:
            raise InterpreterError("super() takes at most 2 arguments")
    elif func_name == "print":
        state["_print_outputs"] += " ".join(map(str, args)) + "\n"
        return None
    else:  # Assume it's a callable object
        # Check if it's an AsyncBaseTool
        if isinstance(func, AsyncBaseTool):
            return func(*args, **kwargs) #don't await, let ast.Await handle it
        # Check if it's a coroutine function
        elif asyncio.iscoroutinefunction(func):
            return func(*args, **kwargs) #don't await, let ast.Await handle it
        # Regular sync function call
        else:
            if func is None:
                raise InterpreterError(f"Function '{func_name}' is None and cannot be called")
            if (inspect.getmodule(func) == builtins) and inspect.isbuiltin(func) and (func not in static_tools.values()):
                raise InterpreterError(
                    f"Invoking a builtin function that has not been explicitly added as a tool is not allowed ({func_name})."
                )
            return func(*args, **kwargs)


async def evaluate_async_attribute(
    expression: ast.Attribute,
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> Any:
    if expression.attr.startswith("__") and expression.attr.endswith("__"):
        raise InterpreterError(f"Forbidden access to dunder attribute: {expression.attr}")
    value = await evaluate_async_ast(expression.value, state, static_tools, custom_tools, authorized_imports)
    return getattr(value, expression.attr)


async def evaluate_async_subscript(
    subscript: ast.Subscript,
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> Any:
    index = await evaluate_async_ast(subscript.slice, state, static_tools, custom_tools, authorized_imports)
    value = await evaluate_async_ast(subscript.value, state, static_tools, custom_tools, authorized_imports)
    try:
        return value[index]
    except (KeyError, IndexError, TypeError) as e:
        error_message = f"Could not index {value} with '{index}': {type(e).__name__}: {e}"
        if isinstance(index, str) and isinstance(value, Mapping):
            close_matches = difflib.get_close_matches(index, list(value.keys()))
            if len(close_matches) > 0:
                error_message += f". Maybe you meant one of these indexes instead: {str(close_matches)}"
        raise InterpreterError(error_message) from e


async def evaluate_async_name(
    name: ast.Name,
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> Any:
    if name.id in state:
        return state[name.id]
    elif name.id in static_tools:
        tool = static_tools[name.id]
        if isinstance(tool, AsyncBaseTool):
            return tool
        else:
            return safer_func(tool, static_tools=static_tools, authorized_imports=authorized_imports)
    elif name.id in custom_tools:
        return custom_tools[name.id]
    elif name.id in ERRORS:
        return ERRORS[name.id]
    close_matches = difflib.get_close_matches(name.id, list(state.keys()))
    if len(close_matches) > 0:
        return state[close_matches[0]]
    raise InterpreterError(f"The variable `{name.id}` is not defined.")


async def evaluate_async_condition(
    condition: ast.Compare,
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> bool | object:
    result = True
    left = await evaluate_async_ast(condition.left, state, static_tools, custom_tools, authorized_imports)
    for i, (op, comparator) in enumerate(zip(condition.ops, condition.comparators)):
        op = type(op)
        right = await evaluate_async_ast(comparator, state, static_tools, custom_tools, authorized_imports)
        if op == ast.Eq:
            current_result = left == right
        elif op == ast.NotEq:
            current_result = left != right
        elif op == ast.Lt:
            current_result = left < right
        elif op == ast.LtE:
            current_result = left <= right
        elif op == ast.Gt:
            current_result = left > right
        elif op == ast.GtE:
            current_result = left >= right
        elif op == ast.Is:
            current_result = left is right
        elif op == ast.IsNot:
            current_result = left is not right
        elif op == ast.In:
            current_result = left in right
        elif op == ast.NotIn:
            current_result = left not in right
        else:
            raise InterpreterError(f"Unsupported comparison operator: {op}")

        if current_result is False:
            return False
        result = current_result if i == 0 else (result and current_result)
        left = right
    return result


async def evaluate_async_for(
    for_loop: ast.For,
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> Any:
    result = None
    iterator = await evaluate_async_ast(for_loop.iter, state, static_tools, custom_tools, authorized_imports)
    for counter in iterator:
        await set_async_value(
            for_loop.target,
            counter,
            state,
            static_tools,
            custom_tools,
            authorized_imports,
        )
        for node in for_loop.body:
            try:
                line_result = await evaluate_async_ast(node, state, static_tools, custom_tools, authorized_imports)
                if line_result is not None:
                    result = line_result
            except BreakException:
                break
            except ContinueException:
                continue
        else:
            continue
        break
    return result


async def set_async_value(
    target: ast.AST,
    value: Any,
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str],
) -> None:
    if isinstance(target, ast.Name):
        if target.id in static_tools:
            raise InterpreterError(f"Trying to modify a static tool '{target.id}' is not allowed.")
        state[target.id] = value
    elif isinstance(target, ast.Tuple):
        if not isinstance(value, (list, tuple)):
            raise InterpreterError(f"Cannot unpack non-iterable {type(value).__name__} object")
        for i, element in enumerate(target.elts):
            await set_async_value(element, value[i], state, static_tools, custom_tools, authorized_imports)
    elif isinstance(target, ast.Subscript):
        obj = await evaluate_async_ast(target.value, state, static_tools, custom_tools, authorized_imports)
        key = await evaluate_async_ast(target.slice, state, static_tools, custom_tools, authorized_imports)
        obj[key] = value
    elif isinstance(target, ast.Attribute):
        obj = await evaluate_async_ast(target.value, state, static_tools, custom_tools, authorized_imports)
        setattr(obj, target.attr, value)
    else:
        raise InterpreterError(f"Unsupported assignment target: {type(target).__name__}")


@async_safer_eval
async def evaluate_async_ast(
    expression: ast.AST,
    state: dict[str, Any],
    static_tools: dict[str, Union[Callable, AsyncBaseTool]],
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]],
    authorized_imports: list[str] = BASE_BUILTIN_MODULES,
):
    """
    Async version of evaluate_ast that handles asynchronous tool calls and coroutines.
    """
    if state.setdefault("_operations_count", {"counter": 0})["counter"] >= MAX_OPERATIONS:
        raise InterpreterError(
            f"Reached the max number of operations of {MAX_OPERATIONS}. Maybe there is an infinite loop somewhere in the code, or you're just asking too many calculations."
        )
    state["_operations_count"]["counter"] += 1
    
    # Import evaluate functions from sync version for non-call operations
    from .local_python_executor import (
        evaluate_assign,
        evaluate_annassign,
        evaluate_augassign,
        evaluate_unaryop,
        evaluate_lambda,
        evaluate_while,
        evaluate_function_def,
        evaluate_class_def,
        evaluate_boolop,
        evaluate_binop,
        evaluate_if,
        evaluate_listcomp,
        evaluate_setcomp,
        evaluate_try,
        evaluate_raise,
        evaluate_assert,
        evaluate_with,
        evaluate_dictcomp,
        evaluate_delete,
        evaluate_import,
    )
    
    common_params = (state, static_tools, custom_tools, authorized_imports)
    
    if isinstance(expression, ast.Call):
        # Handle async function calls
        return await evaluate_async_call(expression, *common_params)
    elif isinstance(expression, ast.Name):
        return await evaluate_async_name(expression, *common_params)
    elif isinstance(expression, ast.Attribute):
        return await evaluate_async_attribute(expression, *common_params)
    elif isinstance(expression, ast.Subscript):
        return await evaluate_async_subscript(expression, *common_params)
    elif isinstance(expression, ast.Compare):
        return await evaluate_async_condition(expression, *common_params)
    elif isinstance(expression, ast.For):
        return await evaluate_async_for(expression, *common_params)
    elif isinstance(expression, ast.FunctionDef):
        return evaluate_async_function_def(expression, *common_params)
    elif isinstance(expression, ast.AsyncFunctionDef):
        return evaluate_async_function_def(expression, *common_params)
    elif isinstance(expression, ast.Assign):
        # For assignments, we need async version due to set_async_value
        targets = []
        for target in expression.targets:
            targets.append(target)
        value = await evaluate_async_ast(expression.value, *common_params)
        for target in targets:
            await set_async_value(target, value, *common_params)
        return value
    elif isinstance(expression, ast.Constant):
        return expression.value
    elif isinstance(expression, ast.Tuple):
        elements = []
        for elt in expression.elts:
            elements.append(await evaluate_async_ast(elt, *common_params))
        return tuple(elements)
    elif isinstance(expression, ast.List):
        elements = []
        for elt in expression.elts:
            elements.append(await evaluate_async_ast(elt, *common_params))
        return elements
    elif isinstance(expression, ast.Dict):
        keys = []
        values = []
        for k in expression.keys:
            keys.append(await evaluate_async_ast(k, *common_params))
        for v in expression.values:
            values.append(await evaluate_async_ast(v, *common_params))
        return dict(zip(keys, values))
    elif isinstance(expression, ast.Expr):
        return await evaluate_async_ast(expression.value, *common_params)
    elif isinstance(expression, ast.BinOp):
        left = await evaluate_async_ast(expression.left, *common_params)
        right = await evaluate_async_ast(expression.right, *common_params)
        # Use sync evaluate_binop by recreating the expression with evaluated operands
        # We need to call the sync version directly for binary operations
        from .local_python_executor import evaluate_binop
        return evaluate_binop(expression, state, static_tools, custom_tools, authorized_imports)
    elif isinstance(expression, ast.Return):
        value = None
        if expression.value:
            value = await evaluate_async_ast(expression.value, *common_params)
        raise ReturnException(value)
    elif isinstance(expression, ast.Await):
        # 先评估值，不立即await
        value = await evaluate_async_ast(expression.value, *common_params)
        # 只有当它是协程时才await
        if inspect.isawaitable(value):
            return await value
        # 如果不是协程，直接返回值
        return value
    elif isinstance(expression, ast.Pass):
        return None
    else:
        # For other operations, fall back to sync evaluation
        # Most operations don't need async handling
        from .local_python_executor import evaluate_ast
        return evaluate_ast(expression, state, static_tools, custom_tools, authorized_imports)


async def evaluate_async_python_code(
    code: str,
    static_tools: dict[str, Union[Callable, AsyncBaseTool]] | None = None,
    custom_tools: dict[str, Union[Callable, AsyncBaseTool]] | None = None,
    state: dict[str, Any] | None = None,
    authorized_imports: list[str] = BASE_BUILTIN_MODULES,
    max_print_outputs_length: int = DEFAULT_MAX_LEN_OUTPUT,
):
    """
    Async version of evaluate_python_code that handles asynchronous tool execution.
    """
    try:
        expression = ast.parse(code)
    except SyntaxError as e:
        raise InterpreterError(
            f"Code parsing failed on line {e.lineno} due to: {type(e).__name__}\n"
            f"{e.text}"
            f"{' ' * (e.offset or 0)}^\n"
            f"Error: {str(e)}"
        )

    if state is None:
        state = {}
    static_tools = static_tools.copy() if static_tools is not None else {}
    custom_tools = custom_tools if custom_tools is not None else {}
    result = None
    state["_print_outputs"] = PrintContainer()
    state["_operations_count"] = {"counter": 0}
    
    # Create a custom asyncio module
    import types
    import sys
    import asyncio as real_asyncio
    
    # Only create custom module if asyncio is in authorized imports
    if "asyncio" in authorized_imports:
        custom_asyncio = types.ModuleType("asyncio")
        
        # Copy all attributes from real asyncio module
        for attr_name in dir(real_asyncio):
            if not attr_name.startswith("_") or attr_name in ("__name__", "__doc__"):
                try:
                    setattr(custom_asyncio, attr_name, getattr(real_asyncio, attr_name))
                except (AttributeError, TypeError):
                    pass
        
        # Define custom async functions
        async def custom_run(coro):
            """Custom asyncio.run() for AsyncPythonExecutor"""
            if asyncio.iscoroutine(coro):
                return await coro
            return coro
            
        async def custom_gather(*args):
            """Custom asyncio.gather() for AsyncPythonExecutor"""
            results = []
            for arg in args:
                if asyncio.iscoroutine(arg):
                    results.append(await arg)
                else:
                    results.append(arg)
            return results
            
        # Override functions
        custom_asyncio.run = custom_run
        custom_asyncio.gather = custom_gather
        
        # Save the original module if it exists
        original_asyncio = sys.modules.get("asyncio")
        
        # Temporarily replace asyncio in sys.modules
        sys.modules["asyncio"] = custom_asyncio
        
        # Add to static tools
        static_tools["asyncio"] = custom_asyncio

    if "final_answer" in static_tools:
        previous_final_answer = static_tools["final_answer"]

        async def final_answer(*args, **kwargs):  # Allow arbitrary arguments to be passed
            if isinstance(previous_final_answer, AsyncBaseTool):
                result = await previous_final_answer(*args, **kwargs)
            else:
                result = previous_final_answer(*args, **kwargs)
            raise FinalAnswerException(result)

        static_tools["final_answer"] = final_answer

    original_asyncio = None
    if "asyncio" in authorized_imports:
        # Save reference to the original module
        original_asyncio = sys.modules.get("asyncio")
    
    try:
        for node in expression.body:
            result = await evaluate_async_ast(node, state, static_tools, custom_tools, authorized_imports)
        state["_print_outputs"].value = truncate_content(
            str(state["_print_outputs"]), max_length=max_print_outputs_length
        )
        is_final_answer = False
        return result, is_final_answer
    except FinalAnswerException as e:
        state["_print_outputs"].value = truncate_content(
            str(state["_print_outputs"]), max_length=max_print_outputs_length
        )
        is_final_answer = True
        return e.value, is_final_answer
    except Exception as e:
        state["_print_outputs"].value = truncate_content(
            str(state["_print_outputs"]), max_length=max_print_outputs_length
        )
        raise InterpreterError(
            f"Code execution failed at line '{ast.get_source_segment(code, node)}' due to: {type(e).__name__}: {e}"
        )
    finally:
        # Restore the original asyncio module if it was replaced
        if "asyncio" in authorized_imports and original_asyncio is not None:
            sys.modules["asyncio"] = original_asyncio


class AsyncPythonExecutor:
    """
    Async executor of Python code in a local environment with support for asynchronous tools.

    This executor evaluates Python code with restricted access to imports and built-in functions,
    making it suitable for running untrusted code. It maintains state between executions,
    allows for async and sync tools to be made available to the code, and captures
    print outputs separately from return values.
    """

    def __init__(
        self,
        additional_authorized_imports: list[str],
        max_print_outputs_length: int | None = None,
        additional_functions: dict[str, Callable] | None = None,
    ):
        self.custom_tools = {}
        self.state = {"__name__": "__main__"}
        self.max_print_outputs_length = max_print_outputs_length
        if max_print_outputs_length is None:
            self.max_print_outputs_length = DEFAULT_MAX_LEN_OUTPUT
        self.additional_authorized_imports = additional_authorized_imports
        # Add multi_tool_use, functions, inspect and asyncio to authorized imports for GPT parallel tool calls and async support
        authorized_imports_with_multi_tool = list(set(BASE_BUILTIN_MODULES) | set(self.additional_authorized_imports) | {"multi_tool_use", "inspect", "asyncio", "functions"})
        self.authorized_imports = authorized_imports_with_multi_tool
        self.static_tools = None
        self.additional_functions = additional_functions or {}

    async def __call__(self, code_action: str) -> tuple[Any, str, bool]:
        max_length = self.max_print_outputs_length if self.max_print_outputs_length is not None else DEFAULT_MAX_LEN_OUTPUT
        output, is_final_answer = await evaluate_async_python_code(
            code_action,
            static_tools=self.static_tools,
            custom_tools=self.custom_tools,
            state=self.state,
            authorized_imports=self.authorized_imports,
            max_print_outputs_length=max_length,
        )
        logs = str(self.state["_print_outputs"])
        return output, logs, is_final_answer

    def send_variables(self, variables: dict):
        self.state.update(variables)

    def send_tools(self, tools: dict[str, Any]):
        """
        Send tools to the async executor. Automatically wraps sync tools in async adapters.
        Handles meta tools (AgentStateAwareTool) specially - they are available in code but not exposed to LLM.
        """
        from ..tools.base_tool import BaseTool
        from ..tools.agent_state_aware_tool import AgentStateAwareTool
        import sys
        import types
        
        converted_tools = {}
        meta_tools = {}  # 分离meta工具
        
        for name, tool in tools.items():
            if isinstance(tool, AgentStateAwareTool):
                # Meta工具特殊处理 - 不暴露给LLM
                meta_tools[name] = tool
            elif isinstance(tool, AsyncBaseTool):
                # Already async, use directly
                converted_tools[name] = tool
            elif hasattr(tool, 'forward') and isinstance(tool, BaseTool):  # BaseTool instance
                # Convert sync tool to async using adapter
                converted_tools[name] = SyncToAsyncToolAdapter(tool)
            else:
                # Regular function, keep as is
                converted_tools[name] = tool
        
        # 注册内置meta工具
        meta_tools.update(self._get_builtin_meta_tools())
        
        # Add multi_tool_use module for GPT's parallel tool calls
        from ..tools.multi_tool_use import parallel, smart_parallel
        
        # Create a real module object for multi_tool_use
        multi_tool_use_module = types.ModuleType("multi_tool_use")
        multi_tool_use_module.parallel = smart_parallel  # Use smart version for better compatibility
        
        # Register the module in sys.modules so it can be imported
        sys.modules["multi_tool_use"] = multi_tool_use_module
        
        # 创建meta工具调用函数
        def meta_call(tool_name: str, *args, **kwargs):
            """调用meta工具的函数 - 对LLM透明"""
            if tool_name in meta_tools:
                import asyncio
                import concurrent.futures
                import threading
                
                tool = meta_tools[tool_name]
                
                # 简化的异步处理：使用线程池运行异步任务
                def run_async_tool():
                    try:
                        # 在新的事件循环中运行
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(tool(*args, **kwargs))
                        finally:
                            loop.close()
                    except Exception as e:
                        return {"error": f"Meta tool execution failed: {e}"}
                
                # 使用线程池执行，避免事件循环冲突
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_async_tool)
                    try:
                        result = future.result(timeout=30)  # 30秒超时
                        return result
                    except concurrent.futures.TimeoutError:
                        return {"error": "Meta tool execution timeout"}
                    except Exception as e:
                        return {"error": f"Meta tool execution error: {e}"}
            else:
                raise ValueError(f"Meta tool '{tool_name}' not found")
        
        # Combine converted tools, base Python tools, and additional Python functions first
        self.static_tools = {
            **converted_tools, 
            **meta_tools,  # 添加meta工具到static_tools（但不到functions命名空间）
            **BASE_PYTHON_TOOLS.copy(), 
            **self.additional_functions,
            "multi_tool_use": multi_tool_use_module,  # Add the real module
            "_meta_call": meta_call,  # 添加meta工具调用函数
        }
        
        # Create a functions namespace object to hold tools (ONLY for LLM-visible tools)
        functions_namespace = types.SimpleNamespace()
        for name, tool in converted_tools.items():  # 注意：只包含converted_tools，不包含meta_tools
            # Add tools to functions namespace with both original name and function name
            setattr(functions_namespace, name, tool)
            if hasattr(tool, '__name__'):
                setattr(functions_namespace, tool.__name__, tool)
        
        # Add the functions namespace to static_tools
        self.static_tools["functions"] = functions_namespace
        
        # Create custom asyncio module with modified run function
        import types
        import asyncio as real_asyncio
        
        # Create a customized asyncio module
        # asyncio_module = types.ModuleType("asyncio")
        #
        # # Copy all attributes from real asyncio module
        # for attr_name in dir(real_asyncio):
        #     if not attr_name.startswith("_") or attr_name in ("__name__", "__doc__"):
        #         try:
        #             setattr(asyncio_module, attr_name, getattr(real_asyncio, attr_name))
        #         except (AttributeError, TypeError):
        #             pass
        #
        # # Override the run function to work in our environment
        # def custom_asyncio_run(coro):
        #     """
        #     Custom implementation of asyncio.run() for use in AsyncPythonExecutor
        #     """
        #     # In our environment, we're already in an event loop
        #     # So we need to directly execute the coroutine without creating a new loop
        #     # This simulates what asyncio.run() would do
        #     if asyncio.iscoroutine(coro):
        #         # We're already in an event loop, so just return the coroutine to be awaited
        #         return coro
        #     else:
        #         # If it's not a coroutine, just return it directly
        #         return coro
        #
        # # Define a custom gather function to handle coroutines
        # async def custom_asyncio_gather(*args):
        #     """
        #     Custom implementation of asyncio.gather() for use in AsyncPythonExecutor
        #     """
        #     results = []
        #     for arg in args:
        #         if asyncio.iscoroutine(arg):
        #             results.append(await arg)
        #         else:
        #             results.append(arg)
        #     return results
        #
        # # Set our custom functions
        # asyncio_module.run = custom_asyncio_run
        # asyncio_module.gather = custom_asyncio_gather
        
        # Register the custom asyncio module
        self.static_tools["asyncio"] = real_asyncio
        
        # Also add multi_tool_use and functions to the state as global objects for direct access
        self.state["multi_tool_use"] = multi_tool_use_module
        self.state["functions"] = functions_namespace
        
        # Create a functions module for direct import
        functions_module = types.ModuleType("functions")
        for name, tool in converted_tools.items():
            setattr(functions_module, name, tool)
        
        # Register the functions module in sys.modules so it can be imported
        sys.modules["functions"] = functions_module
        
        self.state["_meta_call"] = meta_call  # 添加到state以便代码调用
        self.state["asyncio"] = real_asyncio  # Add asyncio to state
        
        # 记录meta工具信息（用于调试）
        if meta_tools:
            self.state["_meta_tools_available"] = list(meta_tools.keys())
    
    def _get_builtin_meta_tools(self) -> dict[str, Any]:
        """获取内置的meta工具"""
        from ..tools.think_tool import ThinkTool
        from ..tools.meta_tools import PlanTool, ReflectionTool
        
        return {
            "think": ThinkTool(),
            "plan": PlanTool(),
            "reflect": ReflectionTool(),
        }


__all__ = ["evaluate_async_python_code", "AsyncPythonExecutor"]