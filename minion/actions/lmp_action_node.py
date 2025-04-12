from typing import Any, Union, List, Optional, Type
from pydantic import BaseModel
import json
import xml.etree.ElementTree as ET
import re
import random

import ell
from tenacity import retry, stop_after_attempt, retry_if_exception_type

from minion.configs.config import config
from minion.schema.message_types import Message
from minion.actions.action_node import LLMActionNode
from minion.schema.messages import user
from minion.providers import create_llm_provider
from minion.models.schemas import Answer  # Import the Answer model

# @ell.complex(model="gpt-4o-mini")
# def ell_call(ret):
#     """You are a helpful assistant."""
#     return ret
class LmpActionNode(LLMActionNode):
    def __init__(self, llm, input_parser=None, output_parser=None):
        super().__init__(llm, input_parser, output_parser)
        #ell.init(**config.ell, default_client=self.llm.client_sync)

    @ell.complex(model="gpt-4o-mini")
    def ell_call(self, ret):
        """You are a helpful assistant."""
        return ret

    async def execute(self, messages: Union[str, Message, List[Message], dict, List[dict]], response_format: Optional[Union[Type[BaseModel], dict]] = None, output_raw_parser=None, format="json", system_prompt: Optional[str] = None, **kwargs) -> Any:
        # 添加 input_parser 处理
        if self.input_parser:
            messages = self.input_parser(messages)

        # Convert string/single message to list
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, Message):
            # Convert Message object to dictionary format
            messages = [messages.model_dump()]
        elif isinstance(messages, dict) and "role" in messages:
            # Single message in dictionary format
            messages = [messages]
        elif isinstance(messages, list) and all(isinstance(msg, Message) for msg in messages):
            # Convert list of Message objects to list of dictionaries
            messages = [msg.model_dump() for msg in messages]

        # Add system prompt with priority:
        # 1. Explicit system message in messages list
        # 2. system_prompt parameter
        # 3. input.system_prompt
        if not any(msg.get("role", "") == "system" if isinstance(msg, dict) else msg.role == "system" for msg in messages):
            if system_prompt is not None:
                messages.insert(0, {"role": "system", "content": system_prompt})
            elif hasattr(self, 'input') and self.input and self.input.system_prompt:
                messages.insert(0, {"role": "system", "content": self.input.system_prompt})

        # 从 llm.config 获取配置
        api_params = {
            "temperature": self.llm.config.temperature, #+ random.random() * 0.01, #add random to avoid prompt caching
            "model": self.llm.config.model,
        }

        # 将 kwargs 合并到 api_params 中，允许覆盖默认值
        api_params.update(kwargs)
        original_response_format = response_format

        if isinstance(response_format, type) and issubclass(response_format, BaseModel):
            # 生成 schema
            schema = response_format.model_json_schema()
            schema_with_indent = json.dumps(schema, indent=4)

            # 创建示例数据
            example = response_format.model_construct()

            if format == "json":
                example_str = example.model_dump_json(indent=4)
                prompt = (
                    f"Please provide the response in JSON format as per the following schema:\n"
                    f"{schema_with_indent}\n\n"
                    f"Here's an example of the expected format:\n"
                    f"{example_str}\n\n"
                    f"Please ensure your response follows this exact schema format."
                )
                api_params['response_format'] = { "type": "json_object" }
            else:  # format == "xml" or format == "xml_simple"
                example_dict = example.model_dump()
                example_xml = self._dict_to_xml_example(example_dict)
                prompt = (
                    f"""Construct an XML response that adheres to the specified schema below.

Schema Structure Example:
{example_xml}

Required JSON Schema Compliance:
{schema_with_indent}

Your response should be:

Well-formed XML: Ensure it follows XML syntax rules.
Schema-compliant: Each element, attribute, and data type must match the JSON schema requirements.
Error-free for Parsing: Escape all special characters and ensure compatibility for JSON conversion.
Provide a final XML structure that aligns seamlessly with both the XML and JSON schema constraints."""
                )
                api_params['response_format'] = { "type": "text" }

            messages.append({"role": "user", "content": prompt})

        response = await super().execute(messages, **api_params)

        if isinstance(response_format, type) and issubclass(response_format, BaseModel):
            if format == "xml" or format == "xml_simple":
                # 清理响应中的代码块标记
                response = response.strip()
                if response.startswith('```xml'):
                    response = response[6:]  # 移除开头的 ```xml
                if response.endswith('```'):
                    response = response[:-3]  # 移除结尾的 ```
                response = response.strip()

                # 确保响应是有效的 XML
                if not response.strip().startswith('<?xml'):
                    response = f'<?xml version="1.0" encoding="UTF-8"?>\n{response}'

                # 根据format选择解析方式
                if format == "xml_simple":
                    response = self._simple_xml_to_json(response_format, response)
                else:
                    response = self._xml_to_json(response)
            response = self.normalize_response(response)

        if original_response_format and isinstance(original_response_format, type) and issubclass(original_response_format, BaseModel):
            response = original_response_format.model_validate_json(response)

        if self.output_parser:
            response = self.output_parser(response)
        return response

    def _dict_to_xml_example(self, data, root_name="root"):
        """Helper method to convert a dictionary to XML example string."""
        if isinstance(data, dict):
            elements = []
            for key, value in data.items():
                elements.append(f"<{key}>{self._dict_to_xml_example(value, key)}</{key}>")
            if root_name == "root":
                return f'<?xml version="1.0" encoding="UTF-8"?>\n<{root_name}>\n  {"  ".join(elements)}\n</{root_name}>'
            return "\n".join(elements)
        elif isinstance(data, list):
            elements = []
            item_name = root_name[:-1] if root_name.endswith('s') else 'item'
            for item in data:
                elements.append(f"<{item_name}>{self._dict_to_xml_example(item, item_name)}</{item_name}>")
            return "\n".join(elements)
        else:
            return str(data) if data is not None else ""

    def _xml_to_json(self, xml_str: str) -> str:
        """Convert XML string to JSON string compatible with Pydantic model."""
        # 移除 XML 声明
        xml_str = re.sub(r'<\?xml[^>]+\?>', '', xml_str).strip()

        # 解析 XML
        root = ET.fromstring(xml_str)

        # 如果根元素是 'root'，我们需要提取其子元素
        if root.tag == 'root':
            result = {}
            for child in root:
                result[child.tag] = self._process_xml_element(child)
        else:
            result = self._process_xml_element(root)

        return json.dumps(result)

    def _process_xml_element(self, element: ET.Element) -> Any:
        """递归处理 XML 元素"""
        # 如果元素没有子元素且有文本
        if len(element) == 0:
            text = element.text.strip() if element.text else ""
            # 尝试转换布尔值
            if text.lower() == 'true':
                return True
            elif text.lower() == 'false':
                return False
            # 尝试转换数字
            try:
                if '.' in text:
                    return float(text)
                return int(text)
            except ValueError:
                return text

        # 如果元素有子元素
        result = {}
        for child in element:
            # 处理列表情况（相同标签的多个元素）
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(self._process_xml_element(child))
            else:
                result[child.tag] = self._process_xml_element(child)

        return result

    def _simple_xml_to_json(self, response_format, xml_str: str) -> str:
        """使用简单的正则表达式解析XML"""
        # 移除XML声明
        xml_str = re.sub(r'<\?xml[^>]+\?>', '', xml_str).strip()

        # 获取schema中定义的所有字段
        schema = response_format.model_json_schema()
        fields = schema.get('properties', {}).keys()

        result = {}
        for field in fields:
            # 使用非贪婪匹配来提取标签内容
            pattern = f"<{field}>(.*?)</{field}>"
            match = re.search(pattern, xml_str, re.DOTALL)
            if match:
                value = match.group(1).strip()
                # 尝试转换布尔值
                if value.lower() == 'true':
                    result[field] = True
                elif value.lower() == 'false':
                    result[field] = False
                else:
                    # 尝试转换数字
                    try:
                        if '.' in value:
                            result[field] = float(value)
                        else:
                            result[field] = int(value)
                    except ValueError:
                        result[field] = value

        return json.dumps(result)
