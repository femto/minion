from jinja2 import Environment, BaseLoader
from typing import List, Dict, Any, Union
import re
import base64
import io
from pathlib import Path

def _convert_pil_image_to_base64(image, format='PNG') -> str:
    """
    将PIL.Image对象转换为base64编码的字符串
    
    Args:
        image: PIL.Image对象
        format: 图像格式，默认为PNG
    
    Returns:
        str: base64编码的图像数据URL
    """
    try:
        # 尝试导入PIL
        from PIL import Image
        
        if not isinstance(image, Image.Image):
            raise ValueError(f"Expected PIL.Image.Image object, got {type(image)}")
        
        # 将图像保存到内存中的字节流
        buffer = io.BytesIO()
        
        # 如果图像有透明通道但要保存为JPEG，转换为RGB
        if format.upper() == 'JPEG' and image.mode in ('RGBA', 'LA'):
            # 创建白色背景
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        image.save(buffer, format=format)
        image_data = buffer.getvalue()
        
        # 编码为base64
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        # 构造data URL
        mime_type = f"image/{format.lower()}"
        return f"data:{mime_type};base64,{base64_data}"
        
    except ImportError:
        raise ImportError("PIL (Pillow) is required to process PIL.Image objects. Install it with: pip install Pillow")
    except Exception as e:
        raise ValueError(f"Failed to convert PIL.Image to base64: {e}")


def _convert_image_path_to_base64(image_path: Union[str, Path]) -> str:
    """
    将图像文件路径转换为base64编码的字符串
    
    Args:
        image_path: 图像文件路径
    
    Returns:
        str: base64编码的图像数据URL
    """
    try:
        from PIL import Image
        
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # 读取图像
        image = Image.open(path)
        
        # 获取文件扩展名作为格式
        format = path.suffix[1:].upper() if path.suffix else 'PNG'
        if format == 'JPG':
            format = 'JPEG'
        
        return _convert_pil_image_to_base64(image, format)
        
    except ImportError:
        raise ImportError("PIL (Pillow) is required to process image files. Install it with: pip install Pillow")
    except Exception as e:
        raise ValueError(f"Failed to convert image file to base64: {e}")


def _format_multimodal_content(item: Any) -> Dict[str, Any]:
    """
    将各种类型的内容转换为OpenAI兼容的格式
    
    Args:
        item: 内容项，可以是字符串、字典、PIL.Image、文件路径等
    
    Returns:
        Dict[str, Any]: OpenAI格式的内容字典
    """
    if isinstance(item, str):
        # 检查是否是图像文件路径
        path = Path(item)
        if path.exists() and path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            # 图像文件路径
            try:
                image_url = _convert_image_path_to_base64(item)
                return {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                }
            except Exception:
                # 如果转换失败，当作普通文本处理
                return {"type": "text", "text": item}
        else:
            # 普通文本
            return {"type": "text", "text": item}
    
    elif isinstance(item, dict):
        # 已经是OpenAI格式的内容
        return item
    
    else:
        # 检查是否是PIL.Image对象
        try:
            from PIL import Image
            if isinstance(item, Image.Image):
                # PIL.Image对象
                image_url = _convert_pil_image_to_base64(item)
                return {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                }
        except ImportError:
            pass
        
        # 其他类型，转换为文本
        return {"type": "text", "text": str(item)}


def render_template_with_variables(template_str: str, **kwargs) -> str:
    """使用 Jinja2 渲染模板字符串

    Args:
        template_str (str): 模板字符串
        **kwargs: 传递给模板的变量字典

    Returns:
        str: 渲染后的字符串
    """
    env = Environment(loader=BaseLoader())
    template = env.from_string(template_str)
    return template.render(**kwargs)


def construct_messages_from_template(
    template_str: str, 
    input_obj: Any, 
    **kwargs
) -> List[Dict[str, Any]]:
    """
    从模板构造OpenAI格式的消息列表，支持多种消息格式(文本、图片等)
    
    Args:
        template_str (str): 包含{{input.query}}的模板字符串
        input_obj: 输入对象，包含query和system_prompt属性
        **kwargs: 其他传递给模板的变量
    
    Returns:
        List[Dict[str, Any]]: OpenAI格式的消息列表
    """
    messages = []
    
    # 从input_obj获取系统提示词
    system_prompt = getattr(input_obj, 'system_prompt', None)
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })
    
    query = getattr(input_obj, 'query', '')
    
    # 检查query是否为列表（多媒体内容）
    if isinstance(query, list):
        # 多媒体内容，直接构造OpenAI消息格式
        messages.extend(_construct_multimodal_messages(template_str, query, input_obj, **kwargs))
    else:
        # 纯文本内容，使用jinja2渲染
        rendered_content = render_template_with_variables(
            template_str, 
            input=input_obj, 
            **kwargs
        )
        messages.append({
            "role": "user",
            "content": rendered_content
        })
    
    return messages


def _construct_multimodal_messages(
    template_str: str, 
    query_list: List[Any], 
    input_obj: Any, 
    **kwargs
) -> List[Dict[str, Any]]:
    """
    构造多媒体消息格式
    
    Args:
        template_str (str): 模板字符串
        query_list (List[Any]): query列表，可能包含文本、图片等
        input_obj: 输入对象
        **kwargs: 其他模板变量
    
    Returns:
        List[Dict[str, Any]]: OpenAI格式的消息列表
    """
    messages = []
    
    # 分割模板，找到{{input.query}}的位置
    query_pattern = r'\{\{\s*input\.query\s*\}\}'
    template_parts = re.split(query_pattern, template_str)
    
    # 构造消息内容
    content_parts = []
    
    # 添加query之前的模板内容
    if template_parts[0].strip():
        # 渲染前缀部分
        prefix_template = Environment(loader=BaseLoader()).from_string(template_parts[0])
        prefix_content = prefix_template.render(input=input_obj, **kwargs)
        if prefix_content.strip():
            content_parts.append({
                "type": "text",
                "text": prefix_content
            })
    
    # 添加query列表中的内容
    for item in query_list:
        content_parts.append(_format_multimodal_content(item))
    
    # 添加query之后的模板内容
    if len(template_parts) > 1 and template_parts[1].strip():
        # 渲染后缀部分
        suffix_template = Environment(loader=BaseLoader()).from_string(template_parts[1])
        suffix_content = suffix_template.render(input=input_obj, **kwargs)
        if suffix_content.strip():
            content_parts.append({
                "type": "text",
                "text": suffix_content
            })
    
    # 构造最终消息
    if content_parts:
        messages.append({
            "role": "user",
            "content": content_parts
        })
    
    return messages


def construct_simple_message(
    content: Union[str, List[Any], Any], 
    system_prompt: str = None
) -> List[Dict[str, Any]]:
    """
    构造简单的消息格式
    
    Args:
        content: 消息内容，可以是字符串、列表或Input对象
        system_prompt: 系统提示词（如果content是Input对象则忽略此参数）
    
    Returns:
        List[Dict[str, Any]]: OpenAI格式的消息列表
    """
    messages = []
    
    # 如果content是Input对象，从中提取query和system_prompt
    if hasattr(content, 'query') and hasattr(content, 'system_prompt'):
        actual_content = content.query
        actual_system_prompt = getattr(content, 'system_prompt', None)
    else:
        actual_content = content
        actual_system_prompt = system_prompt
    
    # 添加系统提示词
    if actual_system_prompt:
        messages.append({
            "role": "system",
            "content": actual_system_prompt
        })
    
    # 添加用户消息
    if isinstance(actual_content, str):
        messages.append({
            "role": "user",
            "content": actual_content
        })
    elif isinstance(actual_content, list):
        # 检查是否是messages格式（包含role字段的字典列表）
        if actual_content and isinstance(actual_content[0], dict) and "role" in actual_content[0]:
            # 这是messages列表，直接返回（但要确保content格式正确）
            formatted_messages = []
            for msg in actual_content:
                if isinstance(msg, dict):
                    formatted_msg = msg.copy()
                    # 确保content字段格式正确
                    if "content" in formatted_msg:
                        content = formatted_msg["content"]
                        if isinstance(content, str):
                            # 字符串content需要转换为标准格式
                            formatted_msg["content"] = [
                                {
                                    "type": "text",
                                    "text": content
                                }
                            ]
                        elif isinstance(content, list):
                            # 如果已经是列表，确保每个项都有type
                            formatted_content = []
                            for item in content:
                                if isinstance(item, dict) and "type" in item:
                                    # 已经有type，保持不变
                                    formatted_content.append(item)
                                elif isinstance(item, dict) and "text" in item:
                                    # 有text但没有type，添加type
                                    formatted_content.append({
                                        "type": "text",
                                        **item
                                    })
                                else:
                                    # 其他情况，转换为text
                                    formatted_content.append({
                                        "type": "text",
                                        "text": str(item)
                                    })
                            formatted_msg["content"] = formatted_content
                    formatted_messages.append(formatted_msg)
                else:
                    formatted_messages.append(msg)
            return formatted_messages
        else:
            # 多媒体内容
            formatted_content = []
            for item in actual_content:
                formatted_content.append(_format_multimodal_content(item))
            
            messages.append({
                "role": "user",
                "content": formatted_content
            })
    
    return messages 