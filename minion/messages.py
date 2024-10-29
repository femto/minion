# minion/messages.py
from ell.types import AnyContent, Message

from typing import Union, List

__all__ = ['system', 'user', 'assistant', 'Message']


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

