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

    async def execute(self, messages: Union[str, Message, List[Message], dict, List[dict]], response_format: Optional[Union[Type[BaseModel], dict]] = None, output_raw_parser=None, format="json", system_prompt: Optional[str] = None, tools=None, **kwargs) -> Any:
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

        # 处理 tools 参数
        if tools is not None:
            # 将 tools 转换为 API 格式
            tools_formatted = self._format_tools_for_api(tools)
            if tools_formatted:
                api_params = {
                    "temperature": self.llm.config.temperature,
                    "model": self.llm.config.model,
                    "tools": tools_formatted,
                    "tool_choice": "auto"
                }
            else:
                api_params = {
                    "temperature": self.llm.config.temperature,
                    "model": self.llm.config.model,
                }
        else:
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
        
        # 从 ChatCompletion 对象中提取字符串内容
        if hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
            message = response.choices[0].message
            if hasattr(message, 'content') and message.content:
                response_text = message.content
            else:
                response_text = ""
        else:
            # 如果不是 ChatCompletion 对象，假设是字符串
            response_text = str(response)
        
        # 处理工具调用
        if tools is not None:
            response_text = await self._handle_tool_calls(response, tools, messages, api_params)

        if isinstance(response_format, type) and issubclass(response_format, BaseModel):
            if format == "xml" or format == "xml_simple":
                # 清理响应中的代码块标记
                response_text = response_text.strip()
                if response_text.startswith('```xml'):
                    response_text = response_text[6:]  # 移除开头的 ```xml
                if response_text.endswith('```'):
                    response_text = response_text[:-3]  # 移除结尾的 ```
                response_text = response_text.strip()

                # 确保响应是有效的 XML
                if not response_text.strip().startswith('<?xml'):
                    response_text = f'<?xml version="1.0" encoding="UTF-8"?>\n{response_text}'

                # 根据format选择解析方式
                if format == "xml_simple":
                    response_text = self._simple_xml_to_json(response_format, response_text)
                else:
                    response_text = self._xml_to_json(response_text)
            response_text = self.normalize_response(response_text)

        if original_response_format and isinstance(original_response_format, type) and issubclass(original_response_format, BaseModel):
            response_text = original_response_format.model_validate_json(response_text)

        if self.output_parser:
            response_text = self.output_parser(response_text)
        return response_text

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
    
    def _format_tools_for_api(self, tools):
        """
        将工具列表转换为API调用格式
        
        Args:
            tools: 工具列表，可以是 BaseTool 实例列表
            
        Returns:
            list: 格式化后的工具定义列表，符合OpenAI API格式
        """
        if not tools:
            return []
            
        formatted_tools = []
        
        for tool in tools:
            # 检查是否是 BaseTool 实例
            if hasattr(tool, 'name') and hasattr(tool, 'description') and hasattr(tool, 'inputs'):
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": tool.inputs,
                            "required": [
                                name for name, param in tool.inputs.items() 
                                if not param.get("nullable", False)
                            ]
                        }
                    }
                }
                formatted_tools.append(tool_def)
            elif isinstance(tool, dict) and "function" in tool:
                # 如果已经是正确格式的工具定义
                formatted_tools.append(tool)
            else:
                # 尝试从工具对象的方法生成定义
                if hasattr(tool, '__call__'):
                    tool_name = tool.__name__
                    tool_desc = tool.__doc__ or f"Tool to {tool_name}"

                    # check if the tool has __input__schema__ attribute which we set when wrapping MCP tools
                    if not hasattr(tool, "__input_schema__"):
                        # Generate one from the function signature
                        import inspect

                        sig = inspect.signature(tool)
                        properties = {}
                        required = []

                        for param_name, param in sig.parameters.items():
                            # Skip *args and **kwargs
                            if param.kind in (
                                    inspect.Parameter.VAR_POSITIONAL,
                                    inspect.Parameter.VAR_KEYWORD,
                            ):
                                continue

                            # Add the parameter to properties
                            properties[param_name] = {
                                "type": "string",
                                "description": f"Parameter {param_name}",
                            }

                            # If parameter has no default, it's required
                            if param.default == inspect.Parameter.empty:
                                required.append(param_name)

                        input_schema = {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        }
                    else:
                        # Use the provided schema
                        input_schema = tool.__input_schema__

                    # Add the tool to available tools
                    formatted_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "description": tool_desc,
                                "parameters": input_schema,
                            },
                        }
                    )
                     
        return formatted_tools
    
    async def _handle_tool_calls(self, response, tools, messages, api_params):
        """
        处理工具调用响应
        
        Args:
            response: LLM的原始响应（可能是字符串或 ChatCompletion 对象）
            tools: 可用的工具列表
            messages: 消息历史
            api_params: API参数
            
        Returns:
            str: 处理后的响应
        """
        # 检查是否是 ChatCompletion 对象
        if hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
            message = response.choices[0].message
            # 检查是否有 tool_calls
            if hasattr(message, 'tool_calls') and message.tool_calls:
                # 处理 OpenAI 格式的 tool_calls
                final_response = ""
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    args_str = tool_call.function.arguments
                    
                    # 查找对应的工具
                    target_tool = None
                    for tool in tools:
                        if hasattr(tool, 'name') and tool.name == tool_name:
                            target_tool = tool
                            break
                        elif hasattr(tool, '__name__') and tool.__name__ == tool_name:
                            target_tool = tool
                            break
                    
                    if target_tool:
                        try:
                            # 解析参数
                            if hasattr(target_tool, 'forward'):
                                # BaseTool 实例
                                if args_str.strip():
                                    # 尝试解析为 JSON 参数
                                    import json
                                    try:
                                        args_dict = json.loads(args_str)
                                        tool_result = target_tool.forward(**args_dict)
                                    except:
                                        # 如果 JSON 解析失败，作为字符串传递
                                        tool_result = target_tool.forward(args_str.strip().strip('"\''))
                                else:
                                    tool_result = target_tool.forward()
                            elif callable(target_tool):
                                # 普通可调用对象
                                if args_str.strip():
                                    import json
                                    try:
                                        args_dict = json.loads(args_str)
                                        tool_result = target_tool(**args_dict)
                                    except:
                                        tool_result = target_tool(args_str.strip().strip('"\''))
                                else:
                                    tool_result = target_tool()
                            else:
                                tool_result = "Tool call failed: tool is not callable"
                            
                            final_response += f"Tool {tool_name} execution result: {tool_result}\n"
                            
                        except Exception as e:
                            error_msg = f"Tool {tool_name} execution error: {str(e)}"
                            final_response += error_msg + "\n"
                
                return final_response.strip()
            else:
                # 没有 tool_calls，返回正常内容
                return message.content or ""
        
        # 如果不是 ChatCompletion 对象，按原来的字符串处理方式
        import json
        import re
        
        # 尝试解析工具调用（这里简化处理，实际需要根据具体LLM的响应格式）
        # 查找函数调用模式
        tool_call_pattern = r'(?:调用工具|使用工具|call tool|use tool).*?(\w+)\s*\((.*?)\)'
        matches = re.finditer(tool_call_pattern, response, re.IGNORECASE | re.DOTALL)
        
        final_response = response
        
        for match in matches:
            tool_name = match.group(1)
            args_str = match.group(2)
            
            # 查找对应的工具
            target_tool = None
            for tool in tools:
                if hasattr(tool, 'name') and tool.name == tool_name:
                    target_tool = tool
                    break
                elif hasattr(tool, '__name__') and tool.__name__ == tool_name:
                    target_tool = tool
                    break
            
            if target_tool:
                try:
                    # 解析参数
                    if hasattr(target_tool, 'forward'):
                        # BaseTool 实例
                        if args_str.strip():
                            # 尝试解析为字符串参数
                            args_str = args_str.strip().strip('"\'')
                            tool_result = target_tool.forward(args_str)
                        else:
                            tool_result = target_tool.forward()
                    elif callable(target_tool):
                        # 普通可调用对象
                        if args_str.strip():
                            args_str = args_str.strip().strip('"\'')
                            tool_result = target_tool(args_str)
                        else:
                            tool_result = target_tool()
                    else:
                        tool_result = "Tool call failed: tool is not callable"
                    
                    # 替换响应中的工具调用为工具结果
                    final_response = final_response.replace(
                        match.group(0), 
                        f"Tool {tool_name} execution result: {tool_result}"
                    )
                    
                except Exception as e:
                    error_msg = f"Tool {tool_name} execution error: {str(e)}"
                    final_response = final_response.replace(match.group(0), error_msg)
        
        return final_response
