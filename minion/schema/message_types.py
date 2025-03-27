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
    description: Optional[str] = Field(None, description="函数描述")
    parameters: Optional[Dict[str, Any]] = Field(None, description="函数的参数定义，符合JSON Schema格式")
    arguments: Optional[Union[str, Dict[str, Any]]] = Field(None, description="函数调用的参数")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FunctionDefinition":
        """Create a FunctionDefinition from a dictionary."""
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data)}")
        
        # Extract known fields
        name = data.get("name")
        if not name:
            raise ValueError("Function definition must have a name")
            
        description = data.get("description")
        parameters = data.get("parameters")
        arguments = data.get("arguments")
        
        # If arguments is a string, try to parse it as JSON
        if isinstance(arguments, str):
            try:
                import json
                arguments = json.loads(arguments)
            except:
                # Keep as string if parsing fails
                pass
                
        return cls(
            name=name,
            description=description,
            parameters=parameters,
            arguments=arguments
    )

class ToolCall(BaseModel):
    """Tool call object that follows OpenAI's format."""
    id: Optional[str] = Field(None, description="工具调用的唯一标识")
    type: Literal["function"] = Field("function", description="工具调用类型，目前仅支持function")
    function: Union[FunctionDefinition, Dict[str, Any]] = Field(..., description="函数定义")
    
    @field_validator("function")
    @classmethod
    def validate_function(cls, v):
        """Ensure function is a valid FunctionDefinition."""
        if isinstance(v, dict):
            try:
                return FunctionDefinition.from_dict(v)
            except Exception as e:
                print(f"Error converting function dict to FunctionDefinition: {e}")
                # Fall back to keeping the dict as is
                return v
        return v

    def dict(self, *args, **kwargs):
        """Convert to dictionary with proper nesting."""
        try:
            result = super().dict(*args, **kwargs)
            # Ensure id is present
            if not result.get("id"):
                result["id"] = f"call_{id(self)}"
            return result
        except Exception as e:
            print(f"Error in ToolCall.dict: {e}")
            # Fallback manual conversion
            func_data = {}
            if isinstance(self.function, FunctionDefinition):
                func_data = {
                    "name": self.function.name
                }
                if self.function.description:
                    func_data["description"] = self.function.description
                if self.function.parameters:
                    func_data["parameters"] = self.function.parameters
                if self.function.arguments:
                    func_data["arguments"] = self.function.arguments
            elif isinstance(self.function, dict):
                func_data = self.function
                
            return {
                "id": self.id or f"call_{id(self)}",
                "type": self.type,
                "function": func_data
            }

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
        if v is None:
            return MessageContent(type=ContentType.TEXT, text="")
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
    
    @field_validator("tool_calls")
    @classmethod
    def validate_tool_calls(cls, v, info):
        """Ensure tool_calls is properly formatted."""
        if v is None:
            return v
        
        role = info.data.get("role")
        if role != "assistant":
            return None
            
        # Convert each tool call to proper ToolCall objects
        result = []
        for tool_call in v:
            try:
                if isinstance(tool_call, ToolCall):
                    result.append(tool_call)
                elif isinstance(tool_call, dict):
                    # Ensure id is present
                    if "id" not in tool_call:
                        tool_call["id"] = f"call_{len(result)}"
                        
                    # Ensure function is properly formatted
                    if "function" in tool_call:
                        # Handle case where function is a dict-like object but not a proper dict
                        func = tool_call["function"]
                        if not isinstance(func, dict) and hasattr(func, "__getitem__") and hasattr(func, "get"):
                            # Convert to proper dict
                            tool_call["function"] = {k: func[k] for k in func if k != "__dict__"}
                        
                        # Convert function arguments from string to dict if needed
                        elif isinstance(func, dict) and "arguments" in func and isinstance(func["arguments"], str):
                            try:
                                import json
                                func["arguments"] = json.loads(func["arguments"])
                            except Exception as e:
                                print(f"Failed to parse arguments JSON: {e}")
                    
                    # Now create a ToolCall with the processed dict
                    try:
                        result.append(ToolCall(**tool_call))
                    except Exception as e:
                        print(f"Error creating ToolCall from dict: {e}, input: {tool_call}")
                        # Fallback: construct manually with minimal required fields
                        if "function" in tool_call and isinstance(tool_call["function"], dict):
                            func_dict = tool_call["function"]
                            if "name" in func_dict:
                                function_def = FunctionDefinition(
                                    name=func_dict["name"],
                                    description=func_dict.get("description"),
                                    arguments=func_dict.get("arguments")
                                )
                                tc = ToolCall(
                                    id=tool_call.get("id", f"call_{len(result)}"),
                                    type=tool_call.get("type", "function"),
                                    function=function_def
                                )
                                result.append(tc)
            except Exception as e:
                print(f"Error processing tool call: {e}, input: {tool_call}")
                    
        return result if result else None

    def model_dump_json(self, **kwargs) -> str:
        """Convert to JSON string with proper formatting for API requests."""
        data = self.model_dump(exclude_none=True, **kwargs)
        return json.dumps(data)
    
    def model_dump(self, **kwargs) -> dict:
        """Convert to dictionary with proper formatting for API requests."""
        result = {}
        
        # Always include role and content
        result["role"] = self.role
        
        # Format content based on type
        if isinstance(self.content, MessageContent):
            if self.content.text is not None:
                result["content"] = self.content.text
            else:
                result["content"] = ""
        else:
            result["content"] = str(self.content)
            
        # Include tool-related fields if present
        if self.name is not None:
            result["name"] = self.name
            
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
            
        if self.tool_calls:
            result["tool_calls"] = [
                tc.dict() if hasattr(tc, "dict") else tc
                for tc in self.tool_calls
            ]
            
        # Apply any exclude options
        exclude = kwargs.get("exclude", set())
        for key in exclude:
            if key in result:
                del result[key]
                
        return result
    
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
            role="tool",
            name=name,
            content=content,
            tool_call_id=tool_call_id
        )
        
    @classmethod
    def tool_response(cls, tool_call_id: str, content: str) -> "Message":
        """Create a tool response message."""
        return cls(
            role="tool",
            content=content,
            tool_call_id=tool_call_id
        )