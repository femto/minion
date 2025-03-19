# Compatibility module - imports from the new location
# This file is deprecated, please use minion.schema.messages instead
from typing import Union, List, Optional, Dict, Any

from minion.schema.message_types import AnyContent, Message, ToolCall, FunctionDefinition


def system(content: Union[AnyContent, List[AnyContent]]) -> Message:
    """Create a system message with the given content.

    Args:
        content: The content of the system message. Can be text, image, or other supported types.

    Returns:
        Message: A Message object with role='system'
    """
    return Message(role="system", content=content)


def user(content: Union[AnyContent, List[AnyContent]]) -> Message:
    """Create a user message with the given content.

    Args:
        content: The content of the user message. Can be text, image, or other supported types.

    Returns:
        Message: A Message object with role='user'
    """
    return Message(role="user", content=content)


def assistant(content: Union[AnyContent, List[AnyContent]]) -> Message:
    """Create an assistant message with the given content.

    Args:
        content: The content of the assistant message. Can be text, image, or other supported types.

    Returns:
        Message: A Message object with role='assistant'
    """
    return Message(role="assistant", content=content)


def tool_call(tool_calls: List[ToolCall]) -> Message:
    """Create an assistant message with tool calls.

    Args:
        tool_calls: List of ToolCall objects representing the tools to call.

    Returns:
        Message: A Message object with role='assistant' and tool_calls field.
    """
    return Message.tool_call(tool_calls=tool_calls)


def function_call(function_name: str, arguments: Dict[str, Any], call_id: Optional[str] = None) -> Message:
    """Create an assistant message with a function call.

    Args:
        function_name: Name of the function to call.
        arguments: Dictionary of arguments to pass to the function.
        call_id: Optional ID for the function call. If not provided, one will be generated.

    Returns:
        Message: A Message object with role='assistant' and a tool_calls field with a single function call.
    """
    import json
    import time
    
    call_id = call_id or f"call_{int(time.time())}"
    
    function_def = FunctionDefinition(
        name=function_name,
        arguments=json.dumps(arguments)
    )
    
    tool_call = ToolCall(
        id=call_id,
        type="function",
        function=function_def
    )
    
    return Message.tool_call(tool_calls=[tool_call])


def function_response(name: str, content: str, tool_call_id: Optional[str] = None) -> Message:
    """Create a function response message.

    Args:
        name: Name of the function that was called.
        content: Result of the function call.
        tool_call_id: Optional ID of the tool call this response is for.

    Returns:
        Message: A Message object with role='function', name field, and content.
    """
    return Message.function_response(name=name, content=content, tool_call_id=tool_call_id)

