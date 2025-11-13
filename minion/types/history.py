"""
History Types

This module defines a History class that provides list-like interface
for managing OpenAI message format conversations.
"""

from typing import List, Dict, Any, Optional, Union, Iterator, overload
import json


class History:
    """
    History class that mimics list interface for OpenAI message format.
    
    Stores OpenAI message format dicts and provides list-like operations
    for easy manipulation.
    """
    
    def __init__(self, messages: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize conversation history.
        
        Args:
            messages: Optional list of OpenAI message dicts to initialize with
        """
        self._messages: List[Dict[str, Any]] = []
        if messages:
            self._messages.extend(messages)
    
    def __len__(self) -> int:
        """Return number of messages."""
        return len(self._messages)
    
    def __bool__(self) -> bool:
        """Return True if history is not empty."""
        return len(self._messages) > 0
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over messages."""
        return iter(self._messages)
    
    @overload
    def __getitem__(self, index: int) -> Dict[str, Any]: ...
    
    @overload
    def __getitem__(self, index: slice) -> List[Dict[str, Any]]: ...
    
    def __getitem__(self, index: Union[int, slice]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Get message(s) by index or slice."""
        return self._messages[index]
    
    def __setitem__(self, index: int, value: Dict[str, Any]) -> None:
        """Set message at index."""
        self._messages[index] = value
    
    def __delitem__(self, index: Union[int, slice]) -> None:
        """Delete message(s) at index or slice."""
        del self._messages[index]
    
    def __contains__(self, item: Dict[str, Any]) -> bool:
        """Check if message is in history."""
        return item in self._messages
    
    def __eq__(self, other) -> bool:
        """Check equality with another History or list."""
        if isinstance(other, History):
            return self._messages == other._messages
        elif isinstance(other, list):
            return self._messages == other
        return False
    
    def __repr__(self) -> str:
        """String representation."""
        return f"History({len(self._messages)} messages)"
    
    def __str__(self) -> str:
        """Human readable string."""
        if not self._messages:
            return "History(empty)"
        
        lines = [f"History({len(self._messages)} messages):"]
        for i, msg in enumerate(self._messages):
            content_preview = str(msg.get('content', ''))[:50] + "..." if len(str(msg.get('content', ''))) > 50 else str(msg.get('content', ''))
            lines.append(f"  {i}: {msg.get('role', 'unknown')} - {content_preview}")
        return "\n".join(lines)
    
    # List-like methods
    def append(self, message: Dict[str, Any]) -> None:
        """Add a message to the end of history."""
        self._messages.append(message)
    
    def extend(self, messages: List[Dict[str, Any]]) -> None:
        """Extend history with multiple messages."""
        self._messages.extend(messages)
    
    def insert(self, index: int, message: Dict[str, Any]) -> None:
        """Insert message at specified index."""
        self._messages.insert(index, message)
    
    def remove(self, message: Dict[str, Any]) -> None:
        """Remove first occurrence of message."""
        self._messages.remove(message)
    
    def pop(self, index: int = -1) -> Dict[str, Any]:
        """Remove and return message at index (default last)."""
        return self._messages.pop(index)
    
    def clear(self) -> None:
        """Remove all messages."""
        self._messages.clear()
    
    def index(self, message: Dict[str, Any], start: int = 0, stop: Optional[int] = None) -> int:
        """Return index of first occurrence of message."""
        return self._messages.index(message, start, stop or len(self._messages))
    
    def count(self, message: Dict[str, Any]) -> int:
        """Return number of occurrences of message."""
        return self._messages.count(message)
    
    def reverse(self) -> None:
        """Reverse the order of messages."""
        self._messages.reverse()
    
    def sort(self, key=None, reverse: bool = False) -> None:
        """Sort messages (typically not used for conversation history)."""
        self._messages.sort(key=key, reverse=reverse)
    
    def copy(self) -> 'History':
        """Return a shallow copy of the history."""
        return History(self._messages.copy())
    
    # Additional utility methods
    def to_list(self) -> List[Dict[str, Any]]:
        """Convert to list of dictionaries (OpenAI format)."""
        return self._messages.copy()
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Alias for to_list() for backward compatibility."""
        return self.to_list()
    
    def filter_by_role(self, role: str) -> 'History':
        """Return new history with only messages of specified role."""
        filtered_messages = [msg for msg in self._messages if msg.get('role') == role]
        return History(filtered_messages)
    
    def get_recent(self, limit: int) -> 'History':
        """Return new history with only the most recent messages."""
        if limit <= 0:
            return History()
        return History(self._messages[-limit:])
    
    def get_user_messages(self) -> 'History':
        """Return new history with only user messages."""
        return self.filter_by_role('user')
    
    def get_assistant_messages(self) -> 'History':
        """Return new history with only assistant messages."""
        return self.filter_by_role('assistant')
    
    def add_user_message(self, content: Union[str, List[Dict[str, Any]]]) -> None:
        """Convenience method to add a user message."""
        self.append({"role": "user", "content": content})
    
    def add_assistant_message(self, content: str) -> None:
        """Convenience method to add an assistant message."""
        self.append({"role": "assistant", "content": content})
    
    def add_system_message(self, content: str) -> None:
        """Convenience method to add a system message."""
        self.append({"role": "system", "content": content})
    
    def add_tool_message(self, content: str, tool_call_id: str) -> None:
        """Convenience method to add a tool message."""
        self.append({"role": "tool", "content": content, "tool_call_id": tool_call_id})
    
    def has_role(self, role: str) -> bool:
        """Check if history contains any messages with specified role."""
        return any(msg.get('role') == role for msg in self._messages)
    
    def get_last_message(self) -> Optional[Dict[str, Any]]:
        """Get the last message in history."""
        return self._messages[-1] if self._messages else None
    
    def get_last_user_message(self) -> Optional[Dict[str, Any]]:
        """Get the last user message in history."""
        for msg in reversed(self._messages):
            if msg.get('role') == 'user':
                return msg
        return None
    
    def get_last_assistant_message(self) -> Optional[Dict[str, Any]]:
        """Get the last assistant message in history."""
        for msg in reversed(self._messages):
            if msg.get('role') == 'assistant':
                return msg
        return None
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_list(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'History':
        """Create from JSON string."""
        messages = json.loads(json_str)
        return cls(messages)
    
    @classmethod
    def from_list(cls, messages: List[Dict[str, Any]]) -> 'History':
        """Create from list of message dictionaries."""
        return cls(messages)