# Compatibility module - imports from the new location
# This file is deprecated, please use minion.schema.message_types instead

from minion.schema.message_types import (
    ImageContent,
    ImageUtils,
    Message,
    MessageContent,
    ContentType,
)

__all__ = [
    "ImageContent",
    "ImageUtils",
    "Message",
    "MessageContent",
    "ContentType",
]
