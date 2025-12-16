from typing import Any, Union, List, Optional, Type
from pydantic import BaseModel
import json
import xml.etree.ElementTree as ET
import re
import random
import inspect

from tenacity import retry, stop_after_attempt, retry_if_exception_type

from minion.configs.config import config
from minion.schema.message_types import Message
from minion.actions.action_node import LLMActionNode
from minion.schema.messages import user
from minion.providers import create_llm_provider
from minion.models.schemas import Answer  # Import the Answer model
from minion.exceptions import FinalAnswerException
from minion.tools.tool_decorator import tool as decorate_tool


def _format_tool_result(tool_name: str, tool_result: Any) -> str:
    """
    Format tool execution result for LLM consumption.

    Args:
        tool_name: Name of the tool
        tool_result: Result from tool execution

    Returns:
        Formatted string for the tool result
    """
    # Special handling for final_answer tool
    if tool_name == 'final_answer':
        if isinstance(tool_result, dict):
            result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
        else:
            result_str = str(tool_result)
        return f"FINAL_ANSWER:{result_str}"

    # Format the result based on type
    if isinstance(tool_result, dict):
        result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
    elif isinstance(tool_result, (list, tuple)):
        result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
    else:
        result_str = str(tool_result)

    return f"Tool {tool_name} execution result:\n{result_str}"


# @ell.complex(model="gpt-4o-mini")
# def ell_call(ret):
#     """You are a helpful assistant."""
#     return ret
class LmpActionNode(LLMActionNode):
    def __init__(self, llm, input_parser=None, output_parser=None):
        super().__init__(llm, input_parser, output_parser)
        #ell.init(**config.ell, default_client=self.llm.client_sync)

    async def execute(self, messages: Union[str, Message, List[Message], dict, List[dict]], response_format: Optional[Union[Type[BaseModel], dict]] = None, output_raw_parser=None, format="json", tools=None, tool_choice="auto", stream=False, stop=None, **kwargs) -> Any:
        # 处理 system_prompt 参数
        system_prompt = kwargs.pop('system_prompt', None)
        
        # 处理可选的 llm 参数
        selected_llm = kwargs.pop('llm', None)
        current_llm = selected_llm if selected_llm is not None else self.llm
        
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

        # 如果有 system_prompt，将其添加到 messages 的开头
        if system_prompt:

            # has_system = any(msg.get("role") == "system" for msg in messages)
            # if not has_system:
                messages.insert(0, {"role": "system", "content": system_prompt})

        # 处理 tools 参数
        if tools is not None:
            # 将 tools 转换为 API 格式
            tools_formatted = self._format_tools_for_api(tools)
            if tools_formatted:
                api_params = {
                    "temperature": current_llm.config.temperature,
                    "model": current_llm.config.model,
                    "tools": tools_formatted,
                    "tool_choice": tool_choice,
                    "original_tools": tools  # 保存原始工具对象
                }
            else:
                api_params = {
                    "temperature": current_llm.config.temperature,
                    "model": current_llm.config.model,
                    "original_tools": tools  # 保存原始工具对象
                }
        else:
            # 从 llm.config 获取配置
            api_params = {
                "temperature": current_llm.config.temperature, #+ random.random() * 0.01, #add random to avoid prompt caching
                "model": current_llm.config.model,
            }

        # 处理stop参数
        if stop is not None:
            api_params['stop'] = stop
        
        # 将 kwargs 合并到 api_params 中，允许覆盖默认值
        api_params.update(kwargs)
        
        # 处理流式参数
        if stream:
            api_params['stream'] = True
            
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

        # 根据是否流式调用不同的方法
        if stream:
            # 流式模式：返回异步生成器（工具调用在生成器内部处理）
            return self._execute_stream_generator(messages, selected_llm=selected_llm, **api_params)
        
        # 非流式模式
        # 提取工具参数（使用原始工具对象）
        tools = api_params.get('original_tools') or api_params.get('tools')
        
        # 创建 LLM API 参数（移除内部参数）
        llm_api_params = {k: v for k, v in api_params.items() if k != 'original_tools'}
        
        # 如果有选定的LLM，临时替换self.llm
        original_llm = self.llm
        if selected_llm is not None:
            self.llm = selected_llm
        
        try:
            response = await super().execute(messages, **llm_api_params)
        finally:
            # 恢复原始LLM
            self.llm = original_llm
        
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
        
        # 处理工具调用（仅在非流式模式）
        if tools is not None:
            response_text = await self._handle_tool_calls(response, tools, messages, llm_api_params)

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
    
    async def _execute_stream_generator(self, messages, selected_llm=None, **api_params):
        """流式执行生成器，支持工具调用"""
        # 处理可选的 llm 参数
        current_llm = selected_llm if selected_llm is not None else self.llm
        
        # 添加 input_parser 处理
        if self.input_parser:
            messages = self.input_parser(messages)

        # Convert string/single message to list
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, Message):
            messages = [messages.model_dump()]
        elif isinstance(messages, dict) and "role" in messages:
            messages = [messages]
        elif isinstance(messages, list) and all(isinstance(msg, Message) for msg in messages):
            messages = [msg.model_dump() for msg in messages]

        # 提取工具参数（使用原始工具对象）
        tools = api_params.get('original_tools') or api_params.get('tools')
        
        # 使用流式生成
        full_content = ""
        tool_calls = []
        
        # 创建 LLM API 参数（移除内部参数）
        llm_api_params = {k: v for k, v in api_params.items() if k != 'original_tools'}
        
        # 确保stop参数被传递
        if 'stop' in api_params:
            llm_api_params['stop'] = api_params['stop']
        
        async for chunk in current_llm.generate_stream(messages, **llm_api_params):
            # 处理 StreamChunk 对象
            if hasattr(chunk, 'content'):
                if chunk.chunk_type == "text":
                    content = chunk.content
                    full_content += content
                    yield chunk  # 直接传递文本 StreamChunk 对象
                elif chunk.chunk_type == "tool_call":
                    # 收集工具调用
                    tool_call = chunk.metadata.get('tool_call')
                    if tool_call:
                        tool_calls.append(tool_call)
                    yield chunk  # 传递工具调用 StreamChunk
                    
                    # 立即执行工具并 yield 工具响应
                    if tool_call:
                        async for response_chunk in self._execute_and_yield_tool_response(tool_call, tools):
                            yield response_chunk
            else:
                # 向后兼容字符串
                content = str(chunk)
                full_content += content
                yield content
        
        # 如果有工具调用，递归获取最终响应
        if tools and tool_calls:
            # 构造包含工具调用的消息
            assistant_message = {
                "role": "assistant",
                "content": full_content if full_content else None,
                "tool_calls": tool_calls
            }
            
            # 执行所有工具调用并获取结果
            tool_results = []
            for tool_call in tool_calls:
                tool_result = await self._execute_single_tool_call(tool_call, tools)
                tool_results.append(tool_result)

            # 检查是否调用了 final_answer，如果是则不再递归调用 LLM
            has_final_answer = any(
                tc.get("function", {}).get("name") == "final_answer"
                for tc in tool_calls
            )

            if has_final_answer:
                # final_answer 已调用，直接结束，不再递归
                return

            # 添加工具调用消息和结果到对话历史
            updated_messages = messages + [assistant_message] + tool_results

            # 递归调用获取最终响应
            async for chunk in self._execute_stream_generator(updated_messages, **api_params):
                yield chunk
        else:
            pass
            # 最终处理
            # if self.output_parser:
            #     full_content = self.output_parser(full_content)
            #
            # # 返回最终完整内容作为特殊标记
            # yield f"[STREAM_COMPLETE: {full_content}]"
    
    async def _execute_and_yield_tool_response(self, tool_call, tools):
        """执行工具调用并立即 yield 工具响应"""
        tool_call_id = tool_call.get('id', 'unknown')
        function_name = tool_call.get('function', {}).get('name')
        function_args = tool_call.get('function', {}).get('arguments', '{}')
        
        # 查找对应的工具
        tool = self._find_tool(function_name, tools)
        
        if tool:
            try:
                # 解析参数
                import json
                args = json.loads(function_args) if function_args else {}
                
                # 执行工具 - 统一的调用方式
                if hasattr(tool, 'execute'):
                    # 传统的 execute 方法
                    result = tool.execute(**args)
                    import asyncio
                    if asyncio.iscoroutine(result):
                        result = await result
                elif callable(tool):
                    # 直接调用工具
                    result = tool(**args)
                    import asyncio
                    if asyncio.iscoroutine(result):
                        result = await result
                else:
                    result = f"Error: Tool {function_name} is not callable"
                
                # 立即 yield 工具响应
                from minion.main.action_step import StreamChunk

                # Check if this is the final_answer tool
                is_final = function_name == "final_answer"

                tool_response_chunk = StreamChunk(
                    content=f"\n📊 工具执行结果: {str(result)}\n",
                    chunk_type="tool_response" if not is_final else "final_answer",
                    metadata={
                        "tool_call_id": tool_call_id,
                        "tool_name": function_name,
                        "tool_result": str(result)
                    }
                )
                # Set is_final_answer flag for final_answer tool
                if is_final:
                    tool_response_chunk.is_final_answer = True

                yield tool_response_chunk
                
            except Exception as e:
                # 工具执行失败，也要 yield 错误响应
                error_msg = f"Error executing {function_name}: {str(e)}"
                
                from minion.main.action_step import StreamChunk
                error_response_chunk = StreamChunk(
                    content=f"\n❌ 工具执行错误: {error_msg}\n",
                    chunk_type="tool_response",
                    metadata={
                        "tool_call_id": tool_call_id,
                        "tool_name": function_name,
                        "error": str(e)
                    }
                )
                yield error_response_chunk
        else:
            # 工具未找到，也要 yield 错误响应
            error_msg = f"Error: Tool {function_name} not found"
            
            from minion.main.action_step import StreamChunk
            error_response_chunk = StreamChunk(
                content=f"\n❌ 工具未找到: {function_name}\n",
                chunk_type="tool_response",
                metadata={
                    "tool_call_id": tool_call_id,
                    "tool_name": function_name,
                    "error": error_msg
                }
            )
            yield error_response_chunk
    
    def _find_tool(self, function_name, tools):
        """查找指定名称的工具"""
        for tool in tools:
            if hasattr(tool, 'name') and tool.name == function_name:
                return tool
            elif hasattr(tool, 'get_schema'):
                schema = tool.get_schema()
                if schema.get('function', {}).get('name') == function_name:
                    return tool
        return None
    
    async def _execute_single_tool_call(self, tool_call, tools):
        """执行单个工具调用并返回结果消息"""
        tool_call_id = tool_call.get('id', 'unknown')
        function_name = tool_call.get('function', {}).get('name')
        function_args = tool_call.get('function', {}).get('arguments', '{}')
        
        # 查找对应的工具
        tool = self._find_tool(function_name, tools)
        
        if tool:
            try:
                # 解析参数
                import json
                args = json.loads(function_args) if function_args else {}
                
                # 执行工具 - 统一的调用方式
                if hasattr(tool, 'execute'):
                    # 传统的 execute 方法
                    result = tool.execute(**args)
                    import asyncio
                    if asyncio.iscoroutine(result):
                        result = await result
                elif callable(tool):
                    # 直接调用工具
                    result = tool(**args)
                    import asyncio
                    if asyncio.iscoroutine(result):
                        result = await result
                else:
                    result = f"Error: Tool {function_name} is not callable"
                
                # 创建工具结果消息
                return {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(result)
                }
                
            except Exception as e:
                # 工具执行失败
                error_msg = f"Error executing {function_name}: {str(e)}"
                return {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": error_msg
                }
        else:
            # 工具未找到
            error_msg = f"Error: Tool {function_name} not found"
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": error_msg
            }
    
    async def _handle_tool_calls_stream(self, response, tools, messages, api_params):
        """处理流式模式下的工具调用"""
        # 简化版本，直接返回响应
        # 在流式模式下，工具调用会在完整响应后处理
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
            elif hasattr(tool, 'to_function_spec'):
                # 支持 MCP 工具的 to_function_spec 方法
                spec = tool.to_function_spec()
                if isinstance(spec, dict):
                    formatted_tools.append(spec)
            elif hasattr(tool, 'get_schema'):
                # 支持有 get_schema 方法的工具
                schema = tool.get_schema()
                if isinstance(schema, dict) and "function" in schema:
                    formatted_tools.append(schema)
                elif isinstance(schema, dict) and "type" in schema and schema["type"] == "function":
                    formatted_tools.append(schema)
            elif isinstance(tool, dict) and "function" in tool:
                # 如果已经是正确格式的工具定义
                formatted_tools.append(tool)
            elif callable(tool):
                decorated = decorate_tool(tool)
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": decorated.name,
                        "description": decorated.description,
                        "parameters": {
                            "type": "object",
                            "properties": decorated.inputs,
                            "required": [
                                name for name, param in decorated.inputs.items()
                                if not param.get("nullable", False)
                            ]
                        }
                    }
                }
                formatted_tools.append(tool_def)
                     
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

                    # 如果是final_answer，则直接抛出FinalAnswerException
                    if tool_name == 'final_answer':
                        try:
                            import json
                            args_dict = json.loads(args_str) if isinstance(args_str, str) else args_str
                            answer_value = args_dict.get('answer', str(args_dict))
                            raise FinalAnswerException(answer_value)
                        except json.JSONDecodeError:
                            # 如果解析失败，直接使用整个参数字符串
                            raise FinalAnswerException(args_str)

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
                            if callable(target_tool):
                                # 普通可调用对象
                                if isinstance(args_str,str):
                                    import json
                                    try:
                                        args_dict = json.loads(args_str)
                                        tool_result = target_tool(**args_dict)
                                    except:
                                        args_str.strip().strip('"\'')
                                        args_dict = json.loads(args_str)
                                        tool_result = target_tool(**args_dict)
                                else:
                                    tool_result = target_tool(**args_str) #assume it's dict

                                # 检查是否是 awaitable，如果是则 await
                                if inspect.iscoroutine(tool_result):
                                    tool_result = await tool_result
                            else:
                                tool_result = "Tool call failed: tool is not callable"

                            final_response += _format_tool_result(tool_name, tool_result) + "\n"

                        except FinalAnswerException as e:
                            # 特殊处理 FinalAnswerException
                            final_response += f"FINAL_ANSWER:{e.answer}\n"
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

        # 提取响应文本内容用于正则匹配
        response_text = str(response) if not isinstance(response, str) else response

        # 首先尝试解析 XML 格式的工具调用
        xml_tool_call_pattern = r'<tool_call>\s*<tool_name>(\w+)</tool_name>\s*<parameters>(.*?)</parameters>\s*</tool_call>'
        xml_matches = re.finditer(xml_tool_call_pattern, response_text, re.IGNORECASE | re.DOTALL)

        final_response = response_text
        
        # 处理 XML 格式的工具调用
        for match in xml_matches:
            tool_name = match.group(1)
            parameters_xml = match.group(2).strip()
            
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
                        # BaseTool 实例，从XML中提取参数
                        if parameters_xml.strip():
                            # 从XML中提取参数值
                            # 如果是final_answer，则直接抛出FinalAnswerException，不调用forward
                            if tool_name == 'final_answer':
                                # 特殊处理 final_answer 工具
                                answer_match = re.search(r'<answer>(.*?)</answer>', parameters_xml, re.DOTALL)
                                if answer_match:
                                    answer_value = answer_match.group(1).strip()
                                    # 直接抛出异常，不调用 forward
                                    raise FinalAnswerException(answer_value)
                                else:
                                    # 直接抛出异常，不调用 forward
                                    raise FinalAnswerException(parameters_xml)
                            else:
                                # 其他工具的参数解析
                                tool_result = target_tool.forward(parameters_xml)
                        else:
                            tool_result = target_tool.forward()
                        
                        # 检查是否是 awaitable，如果是则 await
                        if inspect.iscoroutine(tool_result):
                            tool_result = await tool_result
                    else:
                        tool_result = "Tool call failed: tool is not callable"

                    # 替换响应中的工具调用为工具结果
                    final_response = final_response.replace(
                        match.group(0),
                        _format_tool_result(tool_name, tool_result)
                    )

                except FinalAnswerException as e:
                    # 特殊处理 FinalAnswerException
                    final_response = final_response.replace(
                        match.group(0),
                        f"FINAL_ANSWER:{e.answer}"
                    )
                except Exception as e:
                    error_msg = f"Tool {tool_name} execution error: {str(e)}"
                    final_response = final_response.replace(match.group(0), error_msg)

        # 然后尝试解析传统的函数调用模式
        tool_call_pattern = r'(?:调用工具|使用工具|call tool|use tool).*?(\w+)\s*\((.*?)\)'
        matches = re.finditer(tool_call_pattern, final_response, re.IGNORECASE | re.DOTALL)
        
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
                        
                        # 检查是否是 awaitable，如果是则 await
                        if inspect.iscoroutine(tool_result):
                            tool_result = await tool_result
                            
                    elif callable(target_tool):
                        # 普通可调用对象
                        if args_str.strip():
                            args_str = args_str.strip().strip('"\'')
                            tool_result = target_tool(args_str)
                        else:
                            tool_result = target_tool()
                        
                        # 检查是否是 awaitable，如果是则 await
                        if inspect.iscoroutine(tool_result):
                            tool_result = await tool_result
                    else:
                        tool_result = "Tool call failed: tool is not callable"

                    # 替换响应中的工具调用为工具结果
                    final_response = final_response.replace(
                        match.group(0),
                        _format_tool_result(tool_name, tool_result)
                    )

                except FinalAnswerException as e:
                    # 特殊处理 FinalAnswerException
                    final_response = final_response.replace(
                        match.group(0),
                        f"FINAL_ANSWER:{e.answer}"
                    )
                except Exception as e:
                    error_msg = f"Tool {tool_name} execution error: {str(e)}"
                    final_response = final_response.replace(match.group(0), error_msg)
        
        return final_response
