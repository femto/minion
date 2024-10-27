# 包含 Message, MessageContent, ImageContent 等类定义

import base64
import mimetypes
from pathlib import Path
from typing import Literal, Optional, Union

import aiofiles
from pydantic import BaseModel, Field, field_validator

from minion.configs.config import ContentType, ImageDetail


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


class Message(BaseModel):
    role: str = Field(..., description="消息角色: system/user/assistant")
    content: Union[str, MessageContent] = Field(..., description="消息内容")

    @field_validator("content")
    @classmethod
    def validate_content_type(cls, v):
        if isinstance(v, str):
            return MessageContent(type=ContentType.TEXT, text=v)
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
