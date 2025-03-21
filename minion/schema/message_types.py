# use ell first, defined in messages.py
import base64
import mimetypes
import json
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union, Any

import aiofiles
import numpy as np
from PIL import Image as PILImage
from pydantic import BaseModel, Field, field_validator

from minion.configs.config import ContentType, ImageDetail

# Forward references for type hints
class ContentBlock(BaseModel):
    pass

class FunctionDefinition(BaseModel):
    """Function definition for a tool call."""
    name: str = Field(..., description="函数名称")
    description: str = Field(..., description="函数描述")
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": []
        },
        description="函数的参数定义，符合JSON Schema格式"
    )

class ToolCall(BaseModel):
    """Tool call object that follows OpenAI's format."""
    id: str = Field(..., description="工具调用的唯一标识")
    type: Literal["function"] = Field("function", description="工具调用类型，目前仅支持function")
    function: FunctionDefinition = Field(..., description="函数定义")

class ToolResult(BaseModel):
    """Result from a tool call."""
    tool_call_id: str = Field(..., description="对应的工具调用ID")
    content: str = Field(..., description="工具调用结果")

# AnyContent represents any type that can be passed to Message.
AnyContent = Union[ContentBlock, str, ToolCall, ToolResult, "ImageContent", np.ndarray, PILImage.Image, BaseModel]

class ImageContent(BaseModel):
    type: Literal["image_url", "image_base64"] = Field(..., description="图像内容类型")
    data: str = Field(..., description="图像URL或base64数据")
    detail: ImageDetail = Field(default=ImageDetail.AUTO, description="图像细节级别")

    @field_validator("data")
    @classmethod
    def validate_image_data(cls, v, info):
        if info.data.get("type") == "image_url":
            if not v.startswith(("http://", "https://", "data:")):
                raise ValueError("Invalid image URL format")
        return v


class MessageContent(BaseModel):
    type: ContentType = Field(..., description="内容类型")
    text: Optional[str] = Field(None, description="文本内容")
    image: Optional[ImageContent] = Field(None, description="图像内容")

    @field_validator("text", "image")
    @classmethod
    def validate_content(cls, v, info):
        content_type = info.data.get("type")
        if content_type == ContentType.TEXT and not v and "text" in info.data:
            raise ValueError("Text content required for text type")
        elif content_type in [ContentType.IMAGE_URL, ContentType.IMAGE_BASE64] and not v and "image" in info.data:
            raise ValueError("Image content required for image type")
        return v


class ImageUtils:
    @staticmethod
    async def encode_image_to_base64(image_path: Union[str, Path]) -> str:
        """将图像文件编码为base64字符串"""
        async with aiofiles.open(image_path, "rb") as image_file:
            image_data = await image_file.read()
            mime_type = mimetypes.guess_type(str(image_path))[0]
            b64_data = base64.b64encode(image_data).decode("utf-8")
            return f"data:{mime_type};base64,{b64_data}"

class Message(BaseModel):
    """
    Message class that represents a chat message in a conversation.
    Supports standard chat roles (system, user, assistant) as well as function/tool roles.
    """
    role: str = Field(..., description="消息角色: system/user/assistant/function/tool")
    content: Union[str, MessageContent] = Field(..., description="消息内容")
    
    # Fields for function/tool calls
    name: Optional[str] = Field(None, description="当role为function或tool时，表示函数/工具名称")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="当role为assistant且要调用工具时使用")
    tool_call_id: Optional[str] = Field(None, description="当role为tool时，关联到的tool_call ID")

    @field_validator("content")
    @classmethod
    def validate_content_type(cls, v):
        if isinstance(v, str):
            return MessageContent(type=ContentType.TEXT, text=v)
        return v
    
    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        valid_roles = ["system", "user", "assistant", "function", "tool"]
        if v not in valid_roles:
            raise ValueError(f"Invalid role: {v}. Must be one of {valid_roles}")
        return v
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v, info):
        role = info.data.get("role")
        if role in ["function", "tool"] and not v:
            raise ValueError(f"name is required when role is {role}")
        return v

    def model_dump_json(self, **kwargs) -> str:
        """Convert to JSON string with proper formatting for API requests."""
        data = self.model_dump(exclude_none=True, **kwargs)
        return json.dumps(data)
    
    @classmethod
    def tool_call(cls, tool_calls: List[ToolCall]) -> "Message":
        """Create an assistant message with tool calls."""
        return cls(
            role="assistant",
            content="",  # Empty content for tool calls
            tool_calls=tool_calls
        )
    
    @classmethod
    def function_response(cls, name: str, content: str, tool_call_id: Optional[str] = None) -> "Message":
        """Create a function response message."""
        return cls(
            role="function",
            name=name,
            content=content,
            tool_call_id=tool_call_id
        )