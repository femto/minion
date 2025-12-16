#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Base worker minions - simple workers that directly query LLM
"""
from jinja2 import Template

from minion.actions.lmp_action_node import LmpActionNode
from minion.main.minion import (
    Minion,
    register_worker_minion,
    register_minion_for_route,
)
from minion.types.agent_response import AgentResponse
from minion.main.prompt import (
    WORKER_PROMPT,
    TASK_INPUT,
)
from minion.main.prompt import extract_think_and_answer
from minion.utils.template import construct_messages_from_template, construct_simple_message


class WorkerMinion(Minion):
    pass


@register_minion_for_route("raw")
class RawMinion(WorkerMinion):
    """Raw minion that directly queries LLM without any prompt processing or modifications, supports tool calling.

    Note: This minion is NOT registered in WORKER_MINIONS intentionally - it should only be accessible
    via explicit route lookup (e.g., ToolCallingAgent with route='raw'), not through Brain's smart route selection.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = ""

    async def execute(self):
        node = LmpActionNode(self.get_llm())
        tools = (self.input.tools or []) + (self.brain.tools or [])

        # 检查是否需要流式输出
        if hasattr(self.input, 'stream') and self.input.stream:
            return self._execute_stream(node, tools)

        if self.task:
            # Task mode: use TASK_INPUT template
            template_str = TASK_INPUT
            messages = construct_messages_from_template(
                template_str, self.input, task=self.task
            )
            response = await node.execute(messages, tools=tools, stream=False)
        else:
            query = self.input.query
            # Support string, content blocks, and full messages format
            if isinstance(query, list):
                # Check if it's already in OpenAI messages format
                if query and isinstance(query[0], dict) and "role" in query[0]:
                    # Already in messages format, use directly
                    messages = query
                    # Add system prompt if provided and not already present
                    if self.input.system_prompt and (not messages or messages[0].get("role") != "system"):
                        messages = [{"role": "system", "content": self.input.system_prompt}] + messages
                else:
                    # Content blocks format, convert to messages
                    temp_input = type('obj', (object,), {'query': query, 'system_prompt': self.input.system_prompt})()
                    messages = construct_simple_message(temp_input)
                response = await node.execute(messages, tools=tools, stream=False)
            else:
                # For simple string queries, use traditional approach
                response = await node.execute(query, system_prompt=self.input.system_prompt, tools=tools, stream=False)

        # Extract answer using DeepSeek think mode
        think_content, answer_content = extract_think_and_answer(response)
        self.answer = answer_content if answer_content else response
        self.think_content = think_content

        self.answer_raw = self.input.answer_raw = response
        self.input.answer = self.answer

        # Return AgentResponse instead of just the answer
        return AgentResponse(
            answer=self.answer,
            score=1.0,
            terminated=False,
            truncated=False,
            info={'raw_response': response}
        )

    async def _execute_stream(self, node, tools):
        """流式执行方法"""
        if self.task:
            # Task mode: use TASK_INPUT template
            template_str = TASK_INPUT
            messages = construct_messages_from_template(
                template_str, self.input, task=self.task
            )
            stream_generator = await node.execute(messages, tools=tools, stream=True)
        else:
            query = self.input.query
            # Support string, content blocks, and full messages format
            if isinstance(query, list):
                # Check if it's already in OpenAI messages format
                if query and isinstance(query[0], dict) and "role" in query[0]:
                    # Already in messages format, use directly
                    messages = query
                    # Add system prompt if provided and not already present
                    if self.input.system_prompt and (not messages or messages[0].get("role") != "system"):
                        messages = [{"role": "system", "content": self.input.system_prompt}] + messages
                else:
                    # Content blocks format, convert to messages
                    temp_input = type('obj', (object,), {'query': query, 'system_prompt': self.input.system_prompt})()
                    messages = construct_simple_message(temp_input)
                stream_generator = await node.execute(messages, tools=tools, stream=True)
            else:
                # For simple string queries, use traditional approach
                stream_generator = await node.execute(query, system_prompt=self.input.system_prompt, tools=tools, stream=True)

        # 处理流式生成器并yield结果
        async for chunk in self._process_stream_generator(stream_generator):
            yield chunk

    async def execute_stream(self):
        """公共流式执行接口"""
        node = LmpActionNode(self.get_llm())
        tools = (self.input.tools or []) + (self.brain.tools or [])

        async for chunk in self._execute_stream(node, tools):
            yield chunk

    async def _process_stream_generator(self, stream_generator):
        """处理流式生成器，添加 Minion 层的元数据"""
        from minion.main.action_step import StreamChunk

        full_response = ""
        minion_chunk_counter = 0

        async for chunk in stream_generator:
            if hasattr(chunk, 'content'):
                # 已经是 StreamChunk 对象，添加 Minion 层的元数据
                content = chunk.content
                minion_chunk_counter += 1

                # 对于文本内容，累加到 full_response
                if chunk.chunk_type == "text":
                    full_response += content

                # 更新元数据
                chunk.metadata.update({
                    "minion_type": self.__class__.__name__,
                    "minion_chunk_number": minion_chunk_counter,
                    "minion_total_length": len(full_response)
                })
                yield chunk
            else:
                # 向后兼容：处理字符串（如果有的话）
                content = str(chunk)
                full_response += content
                minion_chunk_counter += 1

                # 创建 StreamChunk 对象
                stream_chunk = StreamChunk(
                    content=content,
                    chunk_type="text",
                    metadata={
                        "minion_type": self.__class__.__name__,
                        "minion_chunk_number": minion_chunk_counter,
                        "minion_total_length": len(full_response)
                    }
                )
                yield stream_chunk

        # 处理完整响应以提取答案
        think_content, answer_content = extract_think_and_answer(full_response)
        self.answer = answer_content if answer_content else full_response
        self.think_content = think_content
        self.answer_raw = self.input.answer_raw = full_response
        self.input.answer = self.answer


@register_worker_minion
class NativeMinion(WorkerMinion):
    """native minion, directly asks llm for answer"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = ""

    async def execute(self):
        query = self.input.query

        # Support string, content blocks, and full messages format
        if isinstance(query, list) and query and isinstance(query[0], dict) and "role" in query[0]:
            # Already in messages format, use directly
            messages = query
            # Add system prompt if provided and not already present
            if self.input.system_prompt and (not messages or messages[0].get("role") != "system"):
                messages = [{"role": "system", "content": self.input.system_prompt}] + messages
        else:
            # Use template-based approach for other formats
            if self.task:
                # Task mode: use TASK_INPUT template
                template_str = WORKER_PROMPT + TASK_INPUT
                messages = construct_messages_from_template(
                    template_str, self.input, task=self.task
                )
            else:
                # Normal mode: use original WORKER_PROMPT
                messages = construct_messages_from_template(
                    WORKER_PROMPT, self.input
                )

        node = LmpActionNode(self.get_llm())
        tools = (self.input.tools or []) + (self.brain.tools or [])
        response = await node.execute(messages, tools=tools)

        # Extract answer using DeepSeek think mode
        think_content, answer_content = extract_think_and_answer(response)
        self.answer = answer_content if answer_content else response
        self.think_content = think_content

        self.raw_answer = self.input.answer_raw = response
        self.input.answer = self.answer

        # Return AgentResponse instead of just the answer
        return AgentResponse(
            raw_response=response,
            answer=self.answer,
            score=1.0,
            terminated=False,
            truncated=False,
            info={'raw_response': response}
        )

    async def execute_stream(self):
        """流式执行方法"""
        if self.task:
            # Task mode: use TASK_INPUT template
            template_str = WORKER_PROMPT + TASK_INPUT
            messages = construct_messages_from_template(
                template_str, self.input, task=self.task
            )
        else:
            # Normal mode: use original WORKER_PROMPT
            messages = construct_messages_from_template(
                WORKER_PROMPT, self.input
            )

        node = LmpActionNode(self.get_llm())
        tools = (self.input.tools or []) + (self.brain.tools or [])

        full_response = ""
        async for chunk in self.stream_node_execution(node, messages, tools):
            # Yield StreamChunk对象，保持原始结构
            yield chunk

            # 累积内容用于后续处理
            if hasattr(chunk, 'content'):
                full_response += chunk.content
            elif isinstance(chunk, str):
                full_response += chunk

        # 处理完整响应
        think_content, answer_content = extract_think_and_answer(full_response)
        self.answer = answer_content if answer_content else full_response
        self.think_content = think_content
        self.raw_answer = self.input.answer_raw = full_response
        self.input.answer = self.answer
