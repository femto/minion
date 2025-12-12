#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Chain of Thought worker minions
"""
from minion.actions.lmp_action_node import LmpActionNode
from minion.main.base_workers import WorkerMinion
from minion.main.minion import register_worker_minion
from minion.types.agent_response import AgentResponse
from minion.main.prompt import (
    COT_PROBLEM_INSTRUCTION,
    DCOT_PROMPT,
    WORKER_PROMPT,
    TASK_INPUT,
)
from minion.main.prompt import extract_think_and_answer
from minion.utils.answer_extraction import extract_answer
from minion.utils.template import construct_messages_from_template


@register_worker_minion
class CotMinion(WorkerMinion):
    """Chain of Thought (CoT) Strategy, Ask the LLM to think step-by-step, explaining each part of the problem to enhance the accuracy of the answer. Please noted you can't access web or user's local computer, so if you need information from the web or from user's local computer, DON'T USE THIS STRATEGY."""

    def __init__(self, worker_config=None, **kwargs):
        super().__init__(worker_config=worker_config, **kwargs)
        self.worker_config = worker_config
        self.input.instruction = "let's think step by step to solve this problem"

    async def execute(self):
        if self.task:
            # Task mode: use TASK_INPUT template
            template_str = COT_PROBLEM_INSTRUCTION + WORKER_PROMPT + TASK_INPUT
            messages = construct_messages_from_template(
                template_str, self.input, task=self.task
            )
        else:
            # Normal mode: use original prompt
            messages = construct_messages_from_template(
                COT_PROBLEM_INSTRUCTION + WORKER_PROMPT, self.input
            )

        # 优先使用selected_llm，如果没有则使用brain.llm
        llm_to_use = self.selected_llm if self.selected_llm else self.brain.llm
        node = LmpActionNode(llm_to_use)
        tools = (self.input.tools or []) + (self.brain.tools or [])
        response = await node.execute(messages, tools=tools)
        self.answer_node = node

        # Check post_processing setting, giving precedence to worker_config
        post_processing = None
        if self.worker_config and 'post_processing' in self.worker_config:
            post_processing = self.worker_config['post_processing']
        elif self.input.post_processing:
            post_processing = self.input.post_processing

        if post_processing == "extract_python" or self.input.query_type == "code_solution":
            self.answer = response  # Let route minion handle extraction
        else:
            # For DeepSeek think mode, extract the answer part outside <think> tags
            think_content, answer_content = extract_think_and_answer(response)
            self.answer = answer_content if answer_content else response
            # Store think content for potential debugging/analysis
            self.think_content = think_content

        self.input.answer = self.answer
        self.answer_raw = self.input.answer_raw = response

        # Return AgentResponse instead of just the answer
        return AgentResponse(
            raw_response=response,
            answer=self.answer,
            is_final_answer=True,
            score=1.0,
            terminated=True,
            truncated=False,
            info={'raw_response': response}
        )

    async def execute_stream(self):
        """流式执行方法"""
        if self.task:
            # Task mode: use TASK_INPUT template
            template_str = COT_PROBLEM_INSTRUCTION + WORKER_PROMPT + TASK_INPUT
            messages = construct_messages_from_template(
                template_str, self.input, task=self.task
            )
        else:
            # Normal mode: use original prompt
            messages = construct_messages_from_template(
                COT_PROBLEM_INSTRUCTION + WORKER_PROMPT, self.input
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
        post_processing = None
        if self.worker_config and 'post_processing' in self.worker_config:
            post_processing = self.worker_config['post_processing']
        elif self.input.post_processing:
            post_processing = self.input.post_processing

        if post_processing == "extract_python" or self.input.query_type == "code_solution":
            self.answer = full_response  # Let route minion handle extraction
        else:
            # For DeepSeek think mode, extract the answer part outside <think> tags
            think_content, answer_content = extract_think_and_answer(full_response)
            self.answer = answer_content if answer_content else full_response
            # Store think content for potential debugging/analysis
            self.think_content = think_content

        self.input.answer = self.answer
        self.answer_raw = self.input.answer_raw = full_response


# https://x.com/_philschmid/status/1842846050320544016
class DcotMinion(WorkerMinion):
    """Dynamic Chain of Thought Strategy"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = ""

    async def execute(self):
        if self.task:
            # Task mode: use TASK_INPUT template
            template_str = DCOT_PROMPT + TASK_INPUT
            messages = construct_messages_from_template(
                template_str, self.input, task=self.task
            )
        else:
            # Normal mode: use original prompt
            messages = construct_messages_from_template(
                DCOT_PROMPT, self.input
            )

        node = LmpActionNode(self.get_llm())
        #tools = (self.input.tools or []) + (self.brain.tools or [])
        response = await node.execute(messages, tools=None)

        self.answer_node = node
        self.answer = self.input.answer = extract_answer(response)
        self.answer_raw = self.input.answer_raw = response

        # Return AgentResponse instead of just the answer
        return AgentResponse(
            response=self.answer,
            score=1.0,
            terminated=False,
            truncated=False,
            info={'raw_response': response}
        )

    async def execute_stream(self):
        """流式执行方法"""
        if self.task:
            # Task mode: use TASK_INPUT template
            template_str = DCOT_PROMPT + TASK_INPUT
            messages = construct_messages_from_template(
                template_str, self.input, task=self.task
            )
        else:
            # Normal mode: use original prompt
            messages = construct_messages_from_template(
                DCOT_PROMPT, self.input
            )

        node = LmpActionNode(self.get_llm())

        full_response = ""
        async for chunk in self.stream_node_execution(node, messages, tools=None):
            # Yield StreamChunk对象，保持原始结构
            yield chunk

            # 累积内容用于后续处理
            if hasattr(chunk, 'content'):
                full_response += chunk.content
            elif isinstance(chunk, str):
                full_response += chunk

        # 处理完整响应
        self.answer = self.input.answer = extract_answer(full_response)
        self.answer_raw = self.input.answer_raw = full_response
