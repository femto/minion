#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import asyncio
import json
import os
import re
import uuid
from collections import Counter
from typing import Any, Callable, Dict, List

import dill
import networkx as nx
from jinja2 import Template

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_none

from minion.actions.action_node import ActionNode
from minion.configs.config import config
from minion.logs import logger
from minion.main.async_python_executor import AsyncPythonExecutor
from minion.main.local_python_executor import LocalPythonExecutor
from minion.main.pre_processing import PreProcessingMinion
from minion.main.check import CheckMinion
from minion.main.check_route import CheckRouterMinion
from minion.main.improve import ImproverMinion
from minion.main.improve_route import ImproveRoute
from minion.main.result_strategy import ResultStrategy
from minion.main.input import Input
from minion.main.minion import (
    MINION_REGISTRY,
    WORKER_MINIONS,
    Minion,
    register_worker_minion,
    RESULT_STRATEGY_REGISTRY,
)
from minion.types.agent_response import AgentResponse
from minion.main.prompt import (
    ASK_PROMPT_JINJA,
    COT_PROBLEM_INSTRUCTION,
    DCOT_PROMPT,
    DOT_PROMPT,
    IDENTIFY_PROMPT,
    MATH_PLAN_PROMPT,
    MERGE_PROMPT,
    PLAN_PROMPT,
    PYTHON_PROMPT,
    QA_PROMPT_JINJA,
    SCORE_PROMPT,
    SMART_PROMPT_TEMPLATE,
    TASK_INPUT,
    TASK_ROUTE_PROMPT,
    WORKER_PROMPT, PYTHON_EXECUTE_PROMPT,
)
from minion.main.symbol_table import Symbol
from minion.main.task_graph import convert_tasks_to_graph
from minion.utils.utils import most_similar_minion, camel_case_to_snake_case
from minion.actions.lmp_action_node import LmpActionNode
from minion.exceptions import FinalAnswerException
from minion.models.schemas import (
    MetaPlan,
    Identification,
    QuestionAndAnswer,
    EnsembleLogic,
    Plan
)
from minion.utils.answer_extraction import extract_final_answer, extract_longest_json_from_string, extract_python, \
    extract_answer
from minion.main.prompt import extract_think_and_answer
from minion.utils.template import construct_messages_from_template, construct_simple_message

class WorkerMinion(Minion):
    pass

#don't register worker minion here for RawMinion
class RawMinion(WorkerMinion):
    """Raw minion that directly queries LLM without any prompt processing or modifications"""

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

# class DotMinion(WorkerMinion):
#     """Diagram of Thought (DoT) Strategy"""
#
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.input.instruction = "let's think step by step to solve this problem"
#
#     async def execute(self):
#         prompt = Template(DOT_PROMPT)
#         prompt = prompt.render(input=self.input)
#
#         node = LmpActionNode(self.brain.llm)
#         response = await node.execute_answer(prompt)
#         self.answer_node = response
#         self.answer = self.input.answer = extract_final_answer(response)
#
#         for _ in range(3):  # try using llm 3 times to extract answer
#             if not self.answer:
#                 # try using llm to extract answer
#                 node = LmpActionNode(self.brain.llm)
#                 response = await node.execute_answer("extract final answer from result")
#                 self.answer = self.input.answer = response
#             else:
#                 break
#         self.raw_answer = self.input.answer_raw = response
#         return self.answer


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


# @register_worker_minion
# class MultiPlanMinion(WorkerMinion):
#     "This Strategy will first generate multiple plan, and then compare each plan, see which one is more promising to produce good result, first try most promising plan, then to less promising plan."
#     pass


@register_worker_minion
class PlanMinion(WorkerMinion):
    "Divide and Conquer Strategy, Divide the problem into smaller subproblems, solve each subproblem independently, and then merge the results for the final solution."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_prompt = PLAN_PROMPT
        self.plan = None
        self.execution_state: Dict[str, Any] = {}

    def write_json_to_cache(self, file, data):
        # Ensure that the data is serializable to JSON
        if file:
            try:
                with open(file, "w") as file:
                    json.dump(data, file, indent=4)  # Write the JSON data to the file with indentation for readability
                print(f"Data successfully written to {self.input.cache_plan}")
            except (TypeError, IOError) as e:
                print(f"An error occurred: {e}")

    def validate_json_plan(self, json_plan):
        # Convert tasks to a graph and perform a topological sort
        G = convert_tasks_to_graph(json_plan)

        try:
            sorted_tasks = list(nx.topological_sort(G))
        except nx.NetworkXUnfeasible:
            raise ValueError("Error: The task graph contains cycles, which is not allowed.")

        # Map task_id to the task dictionary for quick access
        task_map = {task.get("task_id", None) or task["id"]: task for task in json_plan}

        # Track the output keys
        output_keys = set()
        errors = []

        for task_id in sorted_tasks:
            task = task_map[task_id]
            dependent_keys = task.get("dependent", [])

            # Check if all dependent keys are present in previous output keys
            for dependent in dependent_keys:
                dependent_key = dependent.get("dependent_key")
                if dependent_key not in output_keys:
                    errors.append(
                        f"Error in task '{task_id}': Dependent key '{dependent_key}' not found in previous tasks."
                    )

            # Add the current task's output_key to the set of output keys
            output_key = task.get("output_key")
            if output_key:
                output_keys.add(output_key)
        if errors:
            raise ValueError("\n".join(errors))
        self.task_graph = G
        return "All tasks are valid!"

    #@retry(stop=stop_after_attempt(5), wait=wait_none())  # Retries up to 5 times
    async def get_plan_with_retry(self, cache_filename=None):
        if self.input.cache_plan:
            # Attempt to load the plan from the cache
            import json

            try:
                if os.path.exists(cache_filename):
                    with open(cache_filename, "r") as file:
                        plan = json.load(file)
                        logger.info(f"loading cache plan from {cache_filename}")

                        return plan
                else:
                    logger.info("Cache file not found. Fetching plan with retry.")
            except (IOError, json.JSONDecodeError) as e:
                logger.info(f"Error loading plan from cache: {e}. Fetching plan with retry.")

        for i in range(5):
            error = ""
            choose_template = Template(self.plan_prompt + f"Previous Error:{error}")

            # filter out smart, since we don't want to choose smart following smart again
            # also filter out ScoreMinion
            filtered_registry = {key: value for key, value in MINION_REGISTRY.items()}
            filled_template = choose_template.render(minions=filtered_registry, input=self.input)

            #tools = (self.input.tools or []) + (self.brain.tools or [])
            response = await LmpActionNode(llm=self.brain.llm).execute(filled_template, tools=None)

            json = extract_longest_json_from_string(response)

            try:
                self.validate_json_plan(json)
                self.write_json_to_cache(self.input.cache_plan, json)
                return json
            except ValueError as e:
                error = str(e)
                logger.error(f"Validation error: {error}. Retrying...")
        raise ValueError(f"Failed to validate plan after 5 attempts. Last error: {error}")

    async def execute_tasks_in_order(self, graph):
        sorted_tasks = list(nx.topological_sort(graph))
        start_index = self.input.execution_state.current_task_index
        total_tasks = len(sorted_tasks)
        
        logger.info(f"📋 Plan execution: {total_tasks} tasks total, starting from index {start_index}")

        for index, task_id in enumerate(sorted_tasks[start_index:], start=start_index):
            logger.info(f"📋 Plan progress: executing task {index + 1}/{total_tasks} (task_id: {task_id})")
            
            for task in self.plan:
                if task["task_id"] == task_id:
                    task_minion = TaskMinion(brain=self.brain, input=self.input, task=task)
                    result = await task_minion.execute()
                    self.input.symbols[task["output_key"]] = Symbol(
                        result, task["output_type"], task["output_description"]
                    )

                    self.input.update_execution_state(current_task_index=index + 1, last_completed_task=task_id)
                    self.save_execution_state()
                    
                    logger.info(f"📋 Plan progress: task {index + 1}/{total_tasks} completed, stored in symbol '{task['output_key']}'")
                    break

        logger.info(f"📋 Plan execution completed: all {total_tasks} tasks finished")
        self.answer = self.input.answer = result
        return self.answer

    async def execute(self):
        self.load_execution_state()
        if not self.plan:
            self.plan = await self.get_plan_with_retry(cache_filename=self.input.cache_plan)
            self.task_graph = convert_tasks_to_graph(self.plan)
        await self.execute_tasks_in_order(self.task_graph)
        return self.answer

    def save_execution_state(self):
        """保存执行状态"""
        if self.input.save_state:
            self.input.save_state(f"state_{self.input.query_id}.pkl")

    def load_execution_state(self):
        """加载执行状态"""
        if self.input.save_state:
            loaded_input = Input.load_state(f"state_{self.input.query_id}.pkl")
            if loaded_input:
                self.input = loaded_input

    def pause(self):
        """暂停执行并保存当前状态"""
        self.save_execution_state()

    async def resume(self):
        """从上次保存的状态恢复执行"""
        self.load_execution_state()
        await self.execute()
    
    async def execute_stream(self):
        """流式执行方法 - PlanMinion 暂不支持真正的流式输出，回退到普通执行"""
        result = await self.execute()
        yield str(result)


# @register_worker_minion
# class MathPlanMinion(PlanMinion):
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.plan_prompt = MATH_PLAN_PROMPT

class TaskMinion(WorkerMinion):
    def __init__(self, task=None, **kwargs):
        super().__init__(**kwargs)
        self.input.task = task
        self.task = task

    async def choose_minion_and_run(self):
        # Log the start of task execution
        task_id = self.task.get("task_id", "unknown")
        task_instruction = self.task.get("instruction", "")
        task_description = self.task.get("task_description", "")
        logger.info(f"🎯 Starting execution of task [{task_id}]: {task_instruction}")
        if task_description:
            logger.info(f"📝 Task description: {task_description}")
        
        choose_template = Template(TASK_ROUTE_PROMPT)

        # filter out smart, since we don't want choose smart following smart again
        # also filter out ScoreMinion
        # 当选择meta plan的时候，把plan去掉，否则task又走一遍planminion了
        filtered_registry = {key: value for key, value in WORKER_MINIONS.items()
                           if key not in ['plan', 'math_plan']}
        filled_template = choose_template.render(minions=filtered_registry, input=self.input, task=self.task)

        tools = (self.input.tools or []) + (self.brain.tools or [])
        meta_plan = await LmpActionNode(llm=self.brain.llm).execute(filled_template, response_format=MetaPlan, tools=None)

        name = meta_plan.name
        name = most_similar_minion(name, filtered_registry.keys())
        klass = filtered_registry[name]
        
        # Log the chosen minion
        logger.info(f"🤖 Task [{task_id}] selected minion: {name} ({klass.__name__})")
        
        minion = klass(input=self.input, brain=self.brain, task=self.task)

        # 确保至少执行一次
        logger.info(f"⚡ Executing task [{task_id}] with {name}...")
        result = await minion.execute()
        self.answer = self.task["answer"] = result
        self.input.symbols[self.task["output_key"]] = result
        
        # Log task completion
        # output_key = self.task.get("output_key", "unknown")
        # logger.info(f"✅ Task [{task_id}] completed. Output key: {output_key}")
        # logger.info(f"📊 Task [{task_id}] result: {str(result)[:200]}")  # Limit result display to 200 chars
        print("#####TASK OUTPUT#####")
        print(f"{self.task['output_key']}:{result}")

        # 如果需要检查，则进行额外的检查循环
        if int(self.input.task_check) > 0:
            logger.info(f"🔍 Task [{task_id}] entering check loop ({self.input.task_check} iterations)")
            for iteration in range(int(self.input.task_check)):
                logger.info(f"🔍 Task [{task_id}] check iteration {iteration + 1}/{self.input.task_check}")
                check_minion = CheckMinion(input=self.input, brain=self.brain)
                check_result = await check_minion.execute()
                
                if check_result and check_result["correct"]:
                    logger.info(f"✅ Task [{task_id}] passed check on iteration {iteration + 1}")
                    return self.answer
                else:
                    logger.info(f"❌ Task [{task_id}] failed check on iteration {iteration + 1}, retrying...")
                    
                # 如果检查失败，添加反馈信息到input中
                # if check_result:
                #     self.input.feedback = check_result.get("feedback", "")
                #     self.input.error = check_result.get("error", "")
                #     logger.info(f"Check failed on iteration {iteration + 1}. Feedback: {self.input.feedback}")
                    
                # 使用反馈信息重新执行
                logger.info(f"🔄 Task [{task_id}] re-executing with {name}...")
                result = await minion.execute()
                self.answer = self.task["answer"] = result
                self.input.symbols[self.task["output_key"]] = result
                logger.info(f"📊 Task [{task_id}] retry result: {str(result)[:200]}")
                print("#####TASK OUTPUT#####")
                print(f"{self.task['output_key']}:{result}")

                # 清除反馈信息，为下一次迭代做准备
                self.input.feedback = ""
                self.input.error = ""
        
        logger.info(f"🏁 Task [{task_id}] execution finished")
        return self.answer

    async def execute(self):
        return await self.choose_minion_and_run()
    
    async def execute_stream(self):
        """流式执行方法 - TaskMinion 暂不支持真正的流式输出，回退到普通执行"""
        result = await self.choose_minion_and_run()
        yield str(result)


@register_worker_minion
class PythonMinion(WorkerMinion):
    "This problem requires writing code to solve it, write python code to solve it"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.python_env = self.brain.python_env

    async def execute(self):
        # Check post_processing setting, giving precedence to worker_config
        post_processing = None
        if self.worker_config and 'post_processing' in self.worker_config:
            post_processing = self.worker_config['post_processing']
        elif self.input.post_processing:
            post_processing = self.input.post_processing

        if self.input.query_type == "calculate":
            return await self.execute_calculation()
        elif post_processing == "extract_python" or self.input.query_type == "code_solution":
            return await self.execute_code_solution()
        elif self.input.query_type == "generate":
            return await self.execute_generation()
        else:
            return await self.execute_calculation()  # 默认行为

    async def execute_calculation(self):
        error = ""
        for i in range(5):
            node = LmpActionNode(llm=self.brain.llm)

            if not self.task:
                prompt = Template(
                    PYTHON_PROMPT
                    + PYTHON_EXECUTE_PROMPT
                    + WORKER_PROMPT
                    + """

also please check previous error, do the modification according to previous error if there's previous error.
Previous error:
{{error}}
                """
                )
                prompt = prompt.render(input=self.input, error=error)
            else:
                prompt = Template(
                    PYTHON_PROMPT
                    + PYTHON_EXECUTE_PROMPT
                    + WORKER_PROMPT
                    + TASK_INPUT
                    + """

 also please check previous error, do the modification according to previous error if there's previous error.
 Previous error:
 {{error}}"""
                )
                prompt = prompt.render(input=self.input, task=self.task, error=error)

            tools = (self.input.tools or []) + (self.brain.tools or [])
            code = await node.execute(prompt, tools=None)

            code = extract_python(code, self.input.entry_point)
            print(code)

            self.answer_code = self.input.answer_code = code

            self.input.run_id = self.input.run_id or uuid.uuid4()
            
            # Check if python_env has step or __call__ method
            if hasattr(self.python_env, 'step'):

                result = self.python_env.step(code)
                obs = result[0]  # obs
                
                if obs["error"]:
                    error = obs["error"]
                    logger.error(error)
                    self.answer = self.input.answer = f"output:{obs['output']}, error:{obs['error']}"
                    continue  # try again?
                output, error = obs["output"], obs["error"]
                self.answer = self.input.answer = output #answer is only output
            else:
                # LocalPythonExecutor or AsyncPythonExecutor with __call__ method
                try:
                    # Check if it's an async executor (AsyncPythonExecutor)
                    if hasattr(self.python_env, '__call__') and asyncio.iscoroutinefunction(self.python_env.__call__):
                        # Async executor - await the call
                        output, logs, is_final_answer = await self.python_env(code)
                    else:
                        # Sync executor - regular call
                        output, logs, is_final_answer = self.python_env(code)
                        
                    if isinstance(output, Exception):
                        error = str(output)
                        logger.error(error)
                        self.answer = self.input.answer = f"error: {error}"
                        continue
                    else:
                        # Use logs as output if available, otherwise use output
                        result_text = logs if logs else str(output)
                        self.answer = self.input.answer = result_text
                        
                        # If this is a final answer, break the loop and return with terminated=True
                        if is_final_answer:
                            print(f"###final_answer###:{self.answer}")
                            return AgentResponse(
                                raw_response=self.answer,
                                answer=self.answer,
                                score=1.0,
                                terminated=True,
                                truncated=False,
                                info={'execution_successful': True, 'is_final_answer': True}
                            )
                except Exception as e:
                    error = str(e)
                    logger.error(error)
                    self.answer = self.input.answer = f"error: {error}"
                    continue
            
            print(f"###answer###:{self.answer}")
            # Return AgentResponse for successful execution
            return AgentResponse(
                raw_response=self.answer,
                answer=self.answer,
                score=1.0,
                terminated=False,
                truncated=False,
                info={'execution_successful': True}
            )

        # Return AgentResponse even if all attempts failed
        return AgentResponse(
            raw_response=self.answer,
            answer=self.answer,
            score=0.0,
            terminated=False,
            truncated=False,
            info={'execution_failed': True}
        )

    async def execute_code_solution(self):
        error = ""
        for i in range(5):
            node = LmpActionNode(llm=self.brain.llm)
            
            if self.task:
                # Task mode: use TASK_INPUT template
                prompt = Template(
                    PYTHON_PROMPT
                    + WORKER_PROMPT
                    + TASK_INPUT
                    + """
                    Generate a complete Python solution for the given task.
                    This may include one or more functions, classes, or a full module as needed.
                    Do not include any explanations or comments, just the code.
                    If you define the solution as a function, remember to invoke it
                    
                    Previous error (if any):
                    {{error}}
                    """
                )
                prompt = prompt.render(input=self.input, task=self.task, error=error)
            else:
                # Normal mode: use original prompt
                prompt = Template(
                    PYTHON_PROMPT
                    + WORKER_PROMPT
                    + """
                    Generate a complete Python solution for the given problem.
                    This may include one or more functions, classes, or a full module as needed.
                    Do not include any explanations or comments, just the code.
                    If you define the solution as a function, remember to invoke it
                    
                    Previous error (if any):
                    {{error}}
                    """
                )
                prompt = prompt.render(input=self.input, error=error)

            tools = (self.input.tools or []) + (self.brain.tools or [])
            code = await node.execute(prompt, tools=None)
            code = extract_python(code, self.input.entry_point)
            self.answer = self.input.answer = code
            
            # Return AgentResponse instead of just the answer
            return AgentResponse(
                raw_response=self.answer,
                answer=self.answer,
                score=1.0,
                terminated=False,
                truncated=False,
                info={'code_generated': True}
            )

    async def execute_generation(self):
        error = ""
        for i in range(5):
            node = LmpActionNode(llm=self.brain.llm)
            
            if self.task:
                # Task mode: use TASK_INPUT template
                prompt = Template(
                    PYTHON_PROMPT
                    + WORKER_PROMPT
                    + TASK_INPUT
                    + """
                    Create the necessary file structure and contents for the given task.
                    Include file paths and their contents.
                    
                    Previous error (if any):
                    {{error}}
                    """
                )
                prompt = prompt.render(input=self.input, task=self.task, error=error)
            else:
                # Normal mode: use original prompt
                prompt = Template(
                    PYTHON_PROMPT
                    + WORKER_PROMPT
                    + """
                    Create the necessary file structure and contents for the given task.
                    Include file paths and their contents.
                    
                    Previous error (if any):
                    {{error}}
                    """
                )
                prompt = prompt.render(input=self.input, error=error)

            tools = (self.input.tools or []) + (self.brain.tools or [])
            file_structure_text = await node.execute(prompt, tools=tools)
            file_structure = self.extract_file_structure(file_structure_text)
            self.save_files(file_structure)
            self.answer = self.input.answer = file_structure_text
            
            # Return AgentResponse instead of just the answer
            return AgentResponse(
                raw_response=self.answer,
                answer=self.answer,
                score=1.0,
                terminated=False,
                truncated=False,
                info={'files_generated': True, 'file_count': len(file_structure)}
            )

    def extract_file_structure(self, text):
        # 从LLM输出中提取项目结构和文件内容
        # 这需要根据LLM的出格式进行定
        # 返回一个字典键为文件路，值为文件内容
        structure = {}
        current_file = None
        for line in text.split("\n"):
            if line.startswith("File:"):
                current_file = line.split(":", 1)[1].strip()
                structure[current_file] = ""
            elif current_file:
                structure[current_file] += line + "\n"
        return structure

    def save_files(self, file_structure):
        # 将项目文件保存到磁盘
        for file_path, content in file_structure.items():
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
    
    async def execute_stream(self):
        """流式执行方法 - PythonMinion 暂不支持真正的流式输出，回退到普通执行"""
        result = await self.execute()
        if isinstance(result, AgentResponse):
            yield result.answer if result.answer else str(result.raw_response)
        else:
            yield str(result)

@register_worker_minion
class CodeMinion(PythonMinion):
    """
    Code Minion using smolagents-style approach:
    Thought -> Code -> Observation cycle with <end_code> support
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "Solve this problem by writing Python code. Use the 'Thought -> Code -> Observation' approach."
        self.max_iterations = 5

        # Initialize LocalPythonExecutor with tools like smolagents
        if hasattr(self, 'python_env') and isinstance(self.python_env, (LocalPythonExecutor, AsyncPythonExecutor)):
            # Send variables (state) to the python executor
            variables = getattr(self.input, 'symbols', {})
            self.python_env.send_variables(variables=variables)

            # Send tools to the python executor
            brain_tools = getattr(self.brain, 'tools', [])
            input_tools = getattr(self.input, 'tools', [])
            all_tools = {}

            # Convert tools to dict format expected by send_tools
            for tool in (brain_tools + input_tools):
                if hasattr(tool, 'name'):
                    # Tool object with name attribute
                    all_tools[tool.name] = tool
                elif callable(tool) and hasattr(tool, '__name__'):
                    # Function with __name__ attribute
                    all_tools[tool.__name__] = tool
                elif callable(tool):
                    # Generic callable, use str representation as fallback
                    tool_name = getattr(tool, '__name__', str(tool))
                    all_tools[tool_name] = tool

            self.python_env.send_tools(all_tools)

    def _get_last_tool_from_code(self, code: str):
        """
        Extract the last tool called in the code by parsing AST.

        Args:
            code: Python code string to parse

        Returns:
            Tool object if found, None otherwise
        """
        import ast
        try:
            tree = ast.parse(code)
            # Get the last statement
            if not tree.body:
                return None

            last_stmt = tree.body[-1]

            # Handle different types of last statements
            tool_name = None
            if isinstance(last_stmt, ast.Expr) and isinstance(last_stmt.value, ast.Call):
                # Last statement is a direct function call
                call = last_stmt.value
                if isinstance(call.func, ast.Name):
                    tool_name = call.func.id
                elif isinstance(call.func, ast.Attribute):
                    tool_name = call.func.attr
            elif isinstance(last_stmt, (ast.Assign, ast.AnnAssign)):
                # Last statement is an assignment, check the value
                value = last_stmt.value if isinstance(last_stmt, ast.Assign) else last_stmt.value
                if isinstance(value, ast.Call):
                    call = value
                    if isinstance(call.func, ast.Name):
                        tool_name = call.func.id
                    elif isinstance(call.func, ast.Attribute):
                        tool_name = call.func.attr
            elif isinstance(last_stmt, ast.Await):
                # Handle await expressions
                if isinstance(last_stmt.value, ast.Call):
                    call = last_stmt.value
                    if isinstance(call.func, ast.Name):
                        tool_name = call.func.id
                    elif isinstance(call.func, ast.Attribute):
                        tool_name = call.func.attr

            # Look up tool from python_env's custom_tools
            if tool_name and hasattr(self.python_env, 'custom_tools'):
                return self.python_env.custom_tools.get(tool_name)

            return None
        except Exception as e:
            logger.debug(f"Failed to extract tool from code: {e}")
            return None

    def _format_output_for_observation(self, output: Any, code: str) -> str:
        """
        Format output for observation, using tool's format_for_observation if available.

        Args:
            output: The output from code execution
            code: The code that was executed

        Returns:
            Formatted output string
        """
        # Try to get the last tool used
        tool = self._get_last_tool_from_code(code)

        if tool and hasattr(tool, 'format_for_observation'):
            try:
                return tool.format_for_observation(output)
            except Exception as e:
                logger.debug(f"Failed to format output with tool.format_for_observation: {e}")
                # Fall back to default formatting

        # Default formatting
        return str(output) if output is not None else ""
        
    def construct_current_turn_messages(self, query, tools=[], task=None, error="", current_turn_attempts=[]):
        """Construct OpenAI messages format for current turn execution
        
        Args:
            query: Can be string, content blocks, or full messages list
            tools: Available tools list
            task: Task information
            error: Error information from previous attempts within current turn
            current_turn_attempts: current_turn_attempts

        Returns:
            List[Dict]: OpenAI messages format for current turn
        """
        # Get available tools description
        available_tools = []
        for tool in tools:
            if hasattr(tool, 'name') and hasattr(tool, 'description'):
                tool_desc = f"- {tool.name}: {tool.description}"

                # Add readonly information if available
                if hasattr(tool, 'readonly') and tool.readonly:
                    tool_desc += " [READONLY - This tool only reads data and does not modify system state]"

                # Add parameter information and usage example for tools
                tool_params = None
                if hasattr(tool, 'parameters') and tool.parameters:
                    if 'properties' in tool.parameters:
                        tool_params = tool.parameters['properties']
                elif hasattr(tool, 'inputs') and tool.inputs:
                    tool_params = tool.inputs

                if tool_params:
                    params = tool_params
                    param_list = []
                    for param_name, param_info in params.items():
                        param_type = param_info.get('type', 'any')
                        param_desc = param_info.get('description', '')
                        param_list.append(f"{param_name} ({param_type}): {param_desc}")
                    tool_desc += f"\n  Parameters: {', '.join(param_list)}"
                available_tools.append(tool_desc)
        
        tools_description = "\n".join(available_tools) if available_tools else "- print: Output information to the user"
        
        # Construct system message
        prompt = f"""You are an expert assistant who can solve any task using code blobs. You will be given a task to solve as best you can.
To do so, you have been given access to a list of tools. Each tool is actually a Python function which you can call by writing Python code. You can use the tool by writing Python code that calls the function.

You are provided with the following tools:
{tools_description}

**Important Notes for Asynchronous Operations:**
- You are already in an async context - DON'T use `asyncio.run()`
- Use `await` directly at the top level in your code: `result = await async_function()`
- When calling async tools or functions, always use `await` to get the actual result
- No need to wrap your code in async functions - just use `await` directly

**Important Notes for Tool Usage:**
- ALWAYS use keyword arguments when calling tools, never use positional arguments
- Example: `await tool_name(param1="value1", param2="value2")` ✓
- Never: `await tool_name("value1", "value2")` ✗
- All tool parameters must be explicitly named

You will be given a task to solve as best you can. To solve the task, you must plan and execute Python code step by step until you have solved the task.

Here is the format you should follow:
**Thought:** Your reasoning about what to do next
**Code:** 
```python
# Your Python code here
```<end_code>

**Observation:** [This will be filled automatically with the execution result]

Continue this Thought/Code/Observation cycle until you solve the task completely."""

        messages = [{"role": "user", "content": prompt}]
        
        # Construct user message content
        user_content_parts = []
        
        # Add task or problem description
        if task:
            task_text = f"""**Task:** {task.get('instruction', '')}
**Description:** {task.get('task_description', '')}"""
            
            # Add dependent outputs if available
            if task.get("dependent"):
                dependent_info = "\n**Dependent outputs:**\n"
                for dependent in task["dependent"]:
                    dependent_key = dependent.get("dependent_key")
                    if dependent_key in self.input.symbols:
                        symbol = self.input.symbols[dependent_key]
                        dependent_info += f"- {dependent_key}: {symbol.output}\n"
                task_text += dependent_info
            
            user_content_parts.append({"type": "text", "text": task_text})
        else:
            # Handle different query formats
            if isinstance(query, str):
                user_content_parts.append({"type": "text", "text": f"**Problem:** {query}"})
            elif isinstance(query, list):
                # Add problem header
                user_content_parts.append({"type": "text", "text": "**Problem:**"})
                # Add multimodal content
                for item in query:
                    if isinstance(item, dict):
                        # Already formatted content block
                        user_content_parts.append(item)
                    elif isinstance(item, str):
                        # Plain text
                        user_content_parts.append({"type": "text", "text": item})
                    else:
                        # Convert other types to text
                        user_content_parts.append({"type": "text", "text": str(item)})
        
        # Add error information if available
        if error:
            error_text = f"""

**Previous Error:** 
{error}

Please fix the error and try again."""
            user_content_parts.append({"type": "text", "text": error_text})
        
        # Add conversation history if available
        if current_turn_attempts:
            history_text = "\n\n**Previous attempts:**\n" + "\n".join(current_turn_attempts)
            user_content_parts.append({"type": "text", "text": history_text})
        
        # Add final instruction
        user_content_parts.append({"type": "text", "text": "\n\nLet's start! Remember to end your code blocks with <end_code>."})
        
        # Add user message
        messages.append({
            "role": "user", 
            "content": user_content_parts
        })
        
        return messages

    def construct_messages_with_history(self, query, tools=[], task=None, error="", previous_turns_history=None):
        """Construct messages including previous turns history
        
        Args:
            query: Can be string, content blocks, or full messages list
            tools: Available tools list
            task: Task information
            error: Error information from previous attempts within current turn
            previous_turns_history: ConversationHistory object containing previous turns (from agent.state.history)
            
        Returns:
            List[Dict]: OpenAI messages format including previous turns history
        """
        # Construct current turn messages (includes error handling for current turn attempts)
        current_turn_messages = self.construct_current_turn_messages(query, tools, task, error, self.current_turn_attempts)
        
        # Simple logic: previous_turns_history + current_turn_messages
        if previous_turns_history and len(previous_turns_history) > 0:
            # Convert ConversationHistory to list of dicts
            history_messages = previous_turns_history.to_list()
            
            # Find system message if exists in current turn
            system_messages = []
            non_system_messages = []
            
            for msg in current_turn_messages:
                if msg.get("role") == "system":
                    system_messages.append(msg)
                else:
                    non_system_messages.append(msg)
            
            # Construct final order: system + previous_turns_history + current_turn_messages
            messages = system_messages + history_messages + non_system_messages
        else:
            messages = current_turn_messages
        
        return messages

    def _extract_query_text(self, query):
        """Extract text content from query (handle both string and messages format)
        
        Args:
            query: Can be string or messages list (supports both OpenAI messages format and content blocks format)
            
        Returns:
            str: Extracted text content
        """
        if isinstance(query, str):
            return query
        elif isinstance(query, list):
            text_parts = []
            for msg in query:
                if isinstance(msg, dict):
                    # Check if it's a content block format: {"type": "text", "content": "..."}
                    if msg.get("type") == "text" and "content" in msg:
                        text_parts.append(msg.get("content", ""))
                    # Check if it's a content block format with "text" field: {"type": "text", "text": "..."}
                    elif msg.get("type") == "text" and "text" in msg:
                        text_parts.append(msg.get("text", ""))
                    # Check if it's OpenAI messages format: {"role": "user", "content": "..."}
                    elif "role" in msg and "content" in msg:
                        content = msg["content"]
                        if isinstance(content, str):
                            text_parts.append(f"{msg.get('role', 'user')}: {content}")
                        elif isinstance(content, list):
                            # Extract text from nested content list
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    # Handle both "text" and "content" fields in nested items
                                    text_content = item.get("text") or item.get("content", "")
                                    if text_content:
                                        text_parts.append(f"{msg.get('role', 'user')}: {text_content}")
                    # Handle plain string items in the list
                elif isinstance(msg, str):
                    text_parts.append(msg)
            return "\n".join(text_parts) if text_parts else str(query)
        else:
            return str(query)
    
    def _get_history(self):
        """Get previous turns history from brain.state if available
        
        Returns:
            ConversationHistory: Previous conversation turns (from agent.state.history)
        """
        if hasattr(self.brain, 'state') and self.brain.state and hasattr(self.brain.state, 'history'):
            # Return the history (ConversationHistory object)
            return self.brain.state.history
        
        # Import here to avoid circular imports
        from minion.types.history import History
        return History()
    
    def _append_history(self, messages):
        """Append new messages to conversation history in brain.state if available
        
        Args:
            messages: List of OpenAI message format dicts or single message dict
        """
        if hasattr(self.brain, 'state') and self.brain.state and hasattr(self.brain.state, 'history'):
            # Add to agent state history (ConversationHistory object)
            if isinstance(messages, list):
                # Extend with multiple messages
                self.brain.state.history.extend(messages)
            else:
                # Append single message
                self.brain.state.history.append(messages)
    
    async def execute(self):
        """Execute with smolagents-style Thought -> Code -> Observation cycle"""
        
        # Determine the query to use
        if self.task:
            query = self.task.get("instruction", "") or self.task.get("task_description", "")
        else:
            query = self.input.query

        self.current_turn_attempts = []
        
        error = ""
        previous_turns_history = self._get_history()  # From agent.state.history (previous turns)
        tools = self.brain.tools + self.input.tools
        
        for iteration in range(self.max_iterations):
            # Construct messages for this iteration including previous turns history
            messages = self.construct_messages_with_history(query, tools, self.task, error, previous_turns_history)
            
            # Get LLM response
            node = LmpActionNode(llm=self.brain.llm)
            tools = (self.input.tools or []) + (self.brain.tools or [])
            
            # Add stop sequences for code execution
            stop_sequences = ["<end_code>"]
            
            try:
                response = await node.execute(messages, tools=tools, stop=stop_sequences)
                if response and not response.strip().endswith("<end_code>"):
                    response += "<end_code>"
            except FinalAnswerException as e:
                # 收到 final_answer 工具调用，直接返回结果
                final_answer = e.answer
                self.answer = self.input.answer = final_answer
                print(f"Final answer exception detected: {final_answer}")

                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                # 返回 AgentResponse并标记为终止
                return AgentResponse(
                    raw_response=final_answer,  # raw_response是正确的属性名
                    answer=final_answer,
                    is_final_answer=True,
                    score=1.0,
                    terminated=True,
                    truncated=False,
                    info={'final_answer_exception': True}
                )

            # Extract and execute code
            code_blocks = self.extract_code_blocks(response)
            self.current_turn_attempts.append(f"**Assistant Response {iteration + 1}:** {response}")
            if not code_blocks:
                # No code found, add LLM response to current turn and return

                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                
                self.answer = self.input.answer = response
                # Return AgentResponse for non-code response
                return AgentResponse(
                    raw_response=response,
                    answer=self.answer,
                    score=0.5,
                    terminated=True,
                    is_final_answer=True,
                    truncated=False,
                    info={'no_code_found': True}
                )

            # Execute the first code block
            code = code_blocks[0]
            print(f"Executing code:\n{code}")
            
            # Execute the code using python_env
            try:
                # Check if it's an async executor (AsyncPythonExecutor)
                if hasattr(self.python_env, '__call__') and asyncio.iscoroutinefunction(self.python_env.__call__):
                    # Async executor - await the call
                    output, logs, is_final_answer = await self.python_env(code)
                else:
                    # Sync executor - regular call (LocalPythonExecutor)
                    output, logs, is_final_answer = self.python_env(code)
                
                # Check if there was an error (output could be Exception)
                if isinstance(output, Exception):
                    error = str(output)
                    logger.error(f"Code execution error: {error}")
                    observation = f"**Observation:** Error occurred:\n{error}"
                    self.current_turn_attempts.append(observation)
                    # Try again with error feedback
                    continue
                else:
                    # Success!
                    # Format the observation with both output and logs
                    observation_parts = []
                    if logs:
                        observation_parts.append(f"Logs:\n{logs}")
                    if output is not None:
                        # Use tool's format_for_observation if available
                        formatted_output = self._format_output_for_observation(output, code)
                        observation_parts.append(f"Output: {formatted_output}")

                    observation = f"**Observation:** Code executed successfully:\n" + "\n".join(observation_parts)
                    self.current_turn_attempts.append(observation)
                    
                    # Use the final answer from LocalPythonExecutor if available
                    if is_final_answer:
                        self.answer = self.input.answer = output
                        print(f"Final answer detected: {self.answer}")

                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error,
                                                                                  self.current_turn_attempts))
                        # Return AgentResponse with final answer flag
                        return AgentResponse(
                            raw_response=output,
                            answer=output,
                            is_final_answer=True,
                            score=1.0,
                            terminated=True,
                            truncated=False,
                            info={'final_answer_detected': True}
                        )
                    
                    # Otherwise check if this looks like a final answer
                    result_text = logs if logs else str(output)
                    if self.is_final_answer(result_text):
                        self.answer = self.input.answer = result_text
                        print(f"Final answer: {self.answer}")

                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error,
                                                                                  self.current_turn_attempts))
                        # Return AgentResponse with final answer flag
                        return AgentResponse(
                            raw_response=result_text,
                            answer=result_text,
                            is_final_answer=True,
                            score=1.0,
                            terminated=True,
                            truncated=False,
                            info={'final_answer_heuristic': True}
                        )
                    
                    # If we have a good result, we can return it
                    if iteration == self.max_iterations - 1:
                        self.answer = self.input.answer = result_text

                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error,
                                                                                  self.current_turn_attempts))
                        # Return AgentResponse for final iteration
                        return AgentResponse(
                            raw_response=self.answer,
                            answer=self.answer,
                            score=0.8,
                            terminated=False,
                            is_final_answer=False,
                            truncated=True,
                            info={'max_iterations_reached': True}
                        )
                    
                    # Continue for more iterations if needed
                    error = ""

                    
            except FinalAnswerException as e:
                # 特殊处理 FinalAnswerException
                final_answer = e.answer
                self.answer = self.input.answer = final_answer
                print(f"Final answer exception detected: {final_answer}")

                self._append_history(
                    self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                # 返回 AgentResponse并标记为终止
                return AgentResponse(
                    raw_response=final_answer,  # raw_response是正确的属性名
                    answer=final_answer,
                    is_final_answer=True,
                    score=1.0,
                    terminated=True,
                    truncated=False,
                    info={'final_answer_exception': True}
                )
            except Exception as e:
                error = str(e)
                logger.error(f"Execution error: {error}")
                observation = f"**Observation:** Execution failed:\n{error}"
                self.current_turn_attempts.append(observation)
                continue
        
        # If we've exhausted all iterations, return the last response
        self.answer = self.input.answer = response
        # Return AgentResponse for exhausted iterations
        self._append_history(self.construct_current_turn_messages(query,tools,self.task,error,self.current_turn_attempts))
        return AgentResponse(
            raw_response=self.answer,
            answer=self.answer,
            score=0.3,
            terminated=False,
            is_final_answer=False,
            truncated=True,
            info={'all_iterations_failed': True}
        )
    
    def extract_code_blocks(self, text):
        """Extract Python code blocks from text, supporting <end_code> format"""
        code_blocks = []
        
        # Simple pattern: look for code blocks ending with <end_code>
        if '<end_code>' in text:
            # Find code blocks that end with <end_code>
            end_code_pattern = r'```(?:python|py)?\s*\n(.*?)<end_code>'
            matches = re.findall(end_code_pattern, text, re.DOTALL)
            for match in matches:
                cleaned = match.strip()
                # Remove trailing ``` if present
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3].strip()
                if cleaned:
                    code_blocks.append(cleaned)
        
        return code_blocks
    
    def is_final_answer(self, output):
        """Check if the output looks like a final answer"""
        # Only use explicit final answer indicators, not general numeric output
        final_indicators = [
            "final answer:",
            "final result:",
            "final solution:",
            "the answer is:",
            "result is:",
            "solution is:"
        ]
        
        output_lower = output.lower()
        for indicator in final_indicators:
            if indicator in output_lower:
                return True
        
        # Remove the overly broad numeric check that was causing false positives
        # Only rely on explicit final_answer() function calls detected by LocalPythonExecutor
        
        return False
    
    async def execute_stream(self):
        """流式执行方法 - 支持真正的流式输出，包括 Thought/Code/Observation 事件"""
        from minion.main.action_step import StreamChunk

        # Determine the query to use
        if self.task:
            query = self.task.get("instruction", "") or self.task.get("task_description", "")
        else:
            query = self.input.query

        self.current_turn_attempts = []

        error = ""
        previous_turns_history = self._get_history()
        tools = self.brain.tools + self.input.tools

        for iteration in range(self.max_iterations):
            # Emit step start event
            yield StreamChunk(
                content=f"Step {iteration + 1}/{self.max_iterations}",
                chunk_type="step_start",
                metadata={"iteration": iteration, "max_iterations": self.max_iterations}
            )

            # Construct messages for this iteration
            messages = self.construct_messages_with_history(query, tools, self.task, error, previous_turns_history)

            # Get LLM response with streaming
            node = LmpActionNode(llm=self.brain.llm)
            tools = (self.input.tools or []) + (self.brain.tools or [])
            stop_sequences = ["<end_code>"]

            try:
                # Stream LLM response
                response = ""
                stream_generator = await node.execute(messages, tools=tools, stop=stop_sequences, stream=True)

                async for chunk in stream_generator:
                    if hasattr(chunk, 'content'):
                        chunk_content = chunk.content
                    else:
                        chunk_content = str(chunk)

                    response += chunk_content
                    # Yield text chunk as it comes in
                    yield StreamChunk(
                        content=chunk_content,
                        chunk_type="thinking",
                        metadata={"iteration": iteration, "partial": True}
                    )

                if response and not response.strip().endswith("<end_code>"):
                    response += "<end_code>"

            except FinalAnswerException as e:
                final_answer = e.answer
                self.answer = self.input.answer = final_answer

                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                yield AgentResponse(
                    raw_response=final_answer,
                    answer=final_answer,
                    is_final_answer=True,
                    score=1.0,
                    terminated=True,
                    truncated=False,
                    info={'final_answer_exception': True}
                )
                return

            # Extract and execute code
            code_blocks = self.extract_code_blocks(response)
            self.current_turn_attempts.append(f"**Assistant Response {iteration + 1}:** {response}")

            if not code_blocks:
                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                self.answer = self.input.answer = response
                yield AgentResponse(
                    raw_response=response,
                    answer=self.answer,
                    score=0.5,
                    terminated=True,
                    is_final_answer=True,
                    truncated=False,
                    info={'no_code_found': True}
                )
                return

            # Execute the first code block
            code = code_blocks[0]

            # Emit code_start event
            yield StreamChunk(
                content=code,
                chunk_type="code_start",
                metadata={"iteration": iteration, "code_preview": code[:100] + "..." if len(code) > 100 else code}
            )

            # Execute the code using python_env
            try:
                if hasattr(self.python_env, '__call__') and asyncio.iscoroutinefunction(self.python_env.__call__):
                    output, logs, is_final_answer = await self.python_env(code)
                else:
                    output, logs, is_final_answer = self.python_env(code)

                if isinstance(output, Exception):
                    error = str(output)
                    # Emit code_result with error
                    yield StreamChunk(
                        content=error,
                        chunk_type="code_result",
                        metadata={"success": False, "error": error, "iteration": iteration}
                    )
                    observation = f"**Observation:** Error occurred:\n{error}"
                    self.current_turn_attempts.append(observation)
                    continue
                else:
                    # Format observation
                    observation_parts = []
                    if logs:
                        observation_parts.append(f"Logs:\n{logs}")
                    if output is not None:
                        formatted_output = self._format_output_for_observation(output, code)
                        observation_parts.append(f"Output: {formatted_output}")

                    observation_content = "\n".join(observation_parts)

                    # Emit code_result with success
                    yield StreamChunk(
                        content=observation_content,
                        chunk_type="code_result",
                        metadata={"success": True, "iteration": iteration, "has_logs": bool(logs)}
                    )

                    observation = f"**Observation:** Code executed successfully:\n{observation_content}"
                    self.current_turn_attempts.append(observation)

                    if is_final_answer:
                        self.answer = self.input.answer = output
                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                        yield AgentResponse(
                            raw_response=output,
                            answer=output,
                            is_final_answer=True,
                            score=1.0,
                            terminated=True,
                            truncated=False,
                            info={'final_answer_detected': True}
                        )
                        return

                    result_text = logs if logs else str(output)
                    if self.is_final_answer(result_text):
                        self.answer = self.input.answer = result_text
                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                        yield AgentResponse(
                            raw_response=result_text,
                            answer=result_text,
                            is_final_answer=True,
                            score=1.0,
                            terminated=True,
                            truncated=False,
                            info={'final_answer_heuristic': True}
                        )
                        return

                    if iteration == self.max_iterations - 1:
                        self.answer = self.input.answer = result_text
                        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                        yield AgentResponse(
                            raw_response=self.answer,
                            answer=self.answer,
                            score=0.8,
                            terminated=False,
                            is_final_answer=False,
                            truncated=True,
                            info={'max_iterations_reached': True}
                        )
                        return

                    error = ""

            except FinalAnswerException as e:
                final_answer = e.answer
                self.answer = self.input.answer = final_answer
                self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
                yield AgentResponse(
                    raw_response=final_answer,
                    answer=final_answer,
                    is_final_answer=True,
                    score=1.0,
                    terminated=True,
                    truncated=False,
                    info={'final_answer_exception': True}
                )
                return
            except Exception as e:
                error = str(e)
                logger.error(f"Execution error: {error}")
                # Emit code_result with error
                yield StreamChunk(
                    content=error,
                    chunk_type="code_result",
                    metadata={"success": False, "error": error, "iteration": iteration}
                )
                observation = f"**Observation:** Execution failed:\n{error}"
                self.current_turn_attempts.append(observation)
                continue

        # If we've exhausted all iterations
        self.answer = self.input.answer = response
        self._append_history(self.construct_current_turn_messages(query, tools, self.task, error, self.current_turn_attempts))
        yield AgentResponse(
            raw_response=self.answer,
            answer=self.answer,
            score=0.3,
            terminated=False,
            is_final_answer=False,
            truncated=True,
            info={'all_iterations_failed': True}
        )

#do we need this minion?
class CodeProblemMinion(PlanMinion):
    "This is a coding problem which requires stragety thinking to solve it, you will first explore the stragety space then solve it"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "This is a coding problem which requires stragety thinking to solve it, you will first explore the stragety space then solve it"


#the following for moderate, route and identify etc.
class ModeratorMinion(Minion):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.execution_state: Dict[str, Any] = {}

    async def execute_pre_processing(self):
        """Execute pre-processing steps if configured"""
        if not hasattr(self.input, 'execution_config'):
            return
            
        pre_processing_steps = self.input.execution_config.get('pre_processing', [])
        if not pre_processing_steps:
            return
            
        # Ensure pre_processing_steps is a list
        if isinstance(pre_processing_steps, str):
            pre_processing_steps = [pre_processing_steps]
            
        # Get pre-processing minion registry
        from minion.main.minion import PRE_PROCESSING_REGISTRY
        
        # Execute each pre-processing step in sequence
        for step in pre_processing_steps:
            pre_processing_class = PRE_PROCESSING_REGISTRY.get(step)
            if not pre_processing_class:
                logger.warning(f"Pre-processing minion {step} not found")
                continue
            self.execution_state["current_pre_processing"] = step
            self.save_execution_state()

            # Execute pre-processing
            pre_processing_minion = pre_processing_class(input=self.input, brain=self.brain)
            await pre_processing_minion.execute()
            
            # Update execution state

        self.execution_state["current_pre_processing"] = None
        self.save_execution_state()

    async def invoke_minion(self, minion_name, worker_config=None):
        self.input.run_id = uuid.uuid4()  # a new run id for each run
        self.input.route = minion_name
        worker = RouteMinion(input=self.input, brain=self.brain, worker_config=worker_config, selected_llm=self.selected_llm)
        agent_response = await worker.execute()

        # Apply post-processing if specified
        if self.input.post_processing:
            processed_answer = self.input.apply_post_processing(agent_response.raw_response)
            # Update AgentResponse with processed answer but keep other info
            agent_response.raw_response = processed_answer

        self.answer = agent_response.answer
        self.agent_response = agent_response
        return worker, agent_response

    async def choose_minion_and_run(self):
        # Check if we have ensemble configuration
        if hasattr(self.input, 'execution_config') and self.input.execution_config.get('type') == "ensemble":
            return await self.execute_ensemble()
        else:
            return await self.execute_single()

    async def execute_ensemble(self):
        if 'workers' not in self.input.execution_config:
            return await self.execute_single()

        # Get the result strategy
        strategy_config = self.input.execution_config.get("result_strategy", {"name": "majority_voting"})
        strategy_name = strategy_config["name"]
        strategy_class = RESULT_STRATEGY_REGISTRY.get(strategy_name, RESULT_STRATEGY_REGISTRY["majority_voting"])
        
        workers = []  # List to store actual worker instances
        agent_responses = []  # List to store AgentResponse objects
        
        for worker_config in self.input.execution_config["workers"]:
            minion_name = worker_config["name"]
            count = worker_config["count"]
            post_processing = worker_config.get("post_processing")

            for i in range(count):
                self.execution_state["current_minion"] = minion_name
                self.execution_state["current_iteration"] = i
                self.save_execution_state()

                worker, agent_response = await self.invoke_minion(minion_name, worker_config)
                workers.append(worker)
                agent_responses.append(agent_response)

        # Process results using the selected strategy
        strategy = strategy_class(
            input=self.input, 
            brain=self.brain, 
            workers=workers
        )
        final_result = await strategy.execute()
        self.answer = self.input.answer = final_result
        
        # Check if any of the responses indicates termination
        should_terminate = any(resp.terminated or resp.is_final_answer for resp in agent_responses)
        best_response = max(agent_responses, key=lambda x: x.score) if agent_responses else None
        
        # Return AgentResponse with ensemble result
        return AgentResponse(
            response=final_result,
            score=best_response.score if best_response else 1.0,
            terminated=should_terminate,
            truncated=any(resp.truncated for resp in agent_responses),
            final_answer=final_result if should_terminate else None,
            is_final_answer=should_terminate,
            info={'ensemble_count': len(agent_responses), 'strategy': strategy_name}
        )

    async def execute_single(self):
        worker, agent_response = await self.invoke_minion(self.input.route)
        return agent_response

    async def execute(self):
        self.load_execution_state()

        if self.input.execution_state.current_minion:
            # Resume from previous state, assume pre_processing already been done
            if hasattr(self.input, 'execution_config') and self.input.execution_config.get('type') == "ensemble":
                agent_response = await self.execute_ensemble()
            else:
                agent_response = await self.execute_single()
        else:
            # Start new execution

            # Execute pre-processing first
            await self.execute_pre_processing()

            agent_response = await self.choose_minion_and_run()

        # Clean up python env
        self.brain.cleanup_python_env(input=self.input)
        
        # Update answer and return the AgentResponse from the minion
        self.answer = agent_response.answer
        return agent_response

    def save_execution_state(self):
        """保存执行状态"""
        if self.input.save_state:
            self.input.save_state(f"state_{self.input.query_id}.pkl")

    def load_execution_state(self):
        """加载执行状态"""
        if self.input.save_state:
            loaded_input = Input.load_state(f"state_{self.input.query_id}.pkl")
            if loaded_input:
                self.input = loaded_input

    def pause(self):
        """暂停执行并保存当前状态"""
        self.save_execution_state()

    async def resume(self):
        """从上次保存的状态恢复执行"""
        self.load_execution_state()
        await self.execute()
    
    async def execute_stream(self):
        """流式执行方法"""
        self.load_execution_state()

        if self.input.execution_state.current_minion:
            # Resume from previous state, assume pre_processing already been done
            if hasattr(self.input, 'execution_config') and self.input.execution_config.get('type',None) == "ensemble":
                # 集成模式暂不支持流式输出，回退到普通执行
                agent_response = await self.execute_ensemble()
                yield agent_response.answer if hasattr(agent_response, 'answer') else str(agent_response)
                return
            else:
                async for chunk in self._execute_single_stream():
                    yield chunk
        else:
            # Start new execution
            # Execute pre-processing first
            await self.execute_pre_processing()
            
            async for chunk in self._choose_minion_and_run_stream():
                yield chunk

        # Clean up python env
        self.brain.cleanup_python_env(input=self.input)
    
    async def _execute_single_stream(self):
        """单个 worker 的流式执行"""
        worker = RouteMinion(input=self.input, brain=self.brain)
        if hasattr(worker, 'execute_stream'):
            async for chunk in worker.execute_stream():
                yield chunk
        else:
            # 回退到普通执行
            agent_response = await worker.execute()
            yield agent_response.answer if hasattr(agent_response, 'answer') else str(agent_response)
    
    async def _choose_minion_and_run_stream(self):
        """选择并运行 minion 的流式版本"""
        # Check if we have ensemble configuration
        if hasattr(self.input, 'execution_config') and self.input.execution_config.get('type') == "ensemble":
            # 集成模式暂不支持流式输出，回退到普通执行
            agent_response = await self.execute_ensemble()
            yield agent_response.answer if hasattr(agent_response, 'answer') else str(agent_response)
        else:
            async for chunk in self._execute_single_stream():
                yield chunk


class IdentifyMinion(Minion):
    async def execute(self):
        prompt = Template(IDENTIFY_PROMPT)
        prompt = prompt.render(input=self.input)

        node = LmpActionNode(self.get_llm())
        #tools = (self.input.tools or []) + (self.brain.tools or [])
        identification = await node.execute(prompt, response_format=Identification, tools=None)
        
        self.input.complexity = identification.complexity
        self.input.query_range = identification.query_range
        self.input.difficulty = identification.difficulty
        self.input.field = identification.field
        self.input.subfield = identification.subfield

        qa_minion = QaMinion(input=self.input, brain=self.brain)
        await qa_minion.execute()

        self.answer = "identified the input query"
        return self.answer


class QaMinion(Minion):
    async def execute(self):
        if self.input.dataset and not self.input.dataset_description:
            prompt = Template(QA_PROMPT_JINJA)
            prompt = prompt.render(question=f"what's {self.input.dataset}")

            node = LmpActionNode(self.get_llm())
            #tools = (self.input.tools or []) + (self.brain.tools or [])
            answer = await node.execute_answer(prompt, tools=None)
            
            self.answer = self.input.dataset_description = answer
            return self.answer

class RouteMinion(Minion):
    def __init__(self, worker_config=None, **kwargs):
        super().__init__(worker_config=worker_config,**kwargs)
        self.execution_state: Dict[str, Any] = {}
        self.current_minion = None
        self.worker_config = worker_config #worker config from ModeratorMinion

    async def get_minion_class_and_name(self):
        """选择要使用的 minion 类和名称"""
        if self.input.execution_state.chosen_minion:
            # 从上次状态恢复
            name = self.input.execution_state.chosen_minion
            klass = MINION_REGISTRY.get(camel_case_to_snake_case(name), CotMinion) #todo: tmp fix here, actually is other place's bug to store "CotMinion"
            return klass, name
        
        # 新的执行流程
        route = self.input.route
        if self.worker_config and 'name' in self.worker_config:
            route = self.worker_config["name"]
            
        if route and route.startswith("optillm-"):
            klass = OptillmMinion
            approach = route.split("-", 1)[1]
            logger.info(f"Using OptillmMinion with approach: {approach}")
            return klass, route
        elif route:
            filtered_registry = {key: value for key, value in MINION_REGISTRY.items()}
            #route = most_similar_minion(route, filtered_registry.keys())
            logger.info(f"Use enforced route: {route}")
            klass = filtered_registry[route]
            return klass, route
        else:
            # 智能选择逻辑
            choose_template = Template(SMART_PROMPT_TEMPLATE)
            filtered_registry = {key: value for key, value in WORKER_MINIONS.items()}
            filled_template = choose_template.render(minions=filtered_registry, input=self.input)

            # 如果brain.llms中有route配置，则依次尝试每个LLM
            if hasattr(self.brain, 'llms') and 'route' in self.brain.llms:
                for llm in self.brain.llms['route']:
                    try:
                        node = LmpActionNode(llm)
                        #tools = (self.input.tools or []) + (self.brain.tools or [])
                        meta_plan = await node.execute(filled_template, response_format=MetaPlan, tools=None)
                        
                        name = meta_plan.name
                        if name in filtered_registry:
                            logger.info(f"Choosing Route: {name} using LLM: {llm.config.model}")
                            return filtered_registry[name], name
                        else:
                            # 尝试找到最相似的名称
                            #similar_name = most_similar_minion(name, filtered_registry.keys())
                            logger.warning(f"Recommended worker {name} not found, trying next LLM")
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to get route using LLM {llm.config.model}: {str(e)}")
                        continue
                
                # 如果所有route LLM都失败了，记录错误
                logger.error("All route LLMs failed to recommend a route, fallback to using self.brain.llm to recommend a route")
            
            # 如果没有route配置或所有route LLM都失败，使用默认的brain.llm或selected_llm
            try:
                # 优先使用selected_llm，如果没有则使用brain.llm
                llm_to_use = self.selected_llm if self.selected_llm else self.brain.llm
                node = LmpActionNode(llm_to_use)
                #tools = (self.input.tools or []) + (self.brain.tools or [])
                meta_plan = await node.execute(filled_template, response_format=MetaPlan, tools=None)
                
                name = meta_plan.name
                if name in filtered_registry:
                    logger.info(f"Choosing Route: {name} using default brain.llm")
                    return filtered_registry[name], name
                else:
                    # 尝试找到最相似的名称
                    #similar_name = most_similar_minion(name, filtered_registry.keys())
                    similar_name = "cot"
                    #logger.warning(f"Recommended route {name} not found, using similar route: {similar_name}")
                    logger.warning(f"Recommended route {name} not found, using cot")
                    return filtered_registry[similar_name], similar_name
            except Exception as e:
                logger.error(f"Failed to get route using default brain.llm: {str(e)}")
                # 如果所有尝试都失败，返回默认的CotMinion
                logger.info("Falling back to default CotMinion")
                return CotMinion, "cot"

    async def execute(self):
        self.load_execution_state()
        
        # 获取 minion 类和名称
        klass, name = await self.get_minion_class_and_name()
        
        # 确定最大迭代次数
        max_iterations = 3
        if self.input.execution_state.current_iteration:
            max_iterations = max_iterations - self.input.execution_state.current_iteration
            
        # 执行并改进
        agent_response = await self.invoke_minion_and_improve(klass, name, max_iterations=max_iterations)
        
        return agent_response

    async def invoke_minion(self, klass, improve=False):
        if isinstance(klass, str):
            klass = MINION_REGISTRY.get(klass, CotMinion)

        self.input.update_execution_state(
            current_minion=klass.__name__,
            chosen_minion=klass.__name__
        )

        self.current_minion = klass(input=self.input, brain=self.brain, worker_config=self.worker_config, selected_llm=self.selected_llm)
        self.add_followers(self.current_minion)
        if improve:
            minion_result = await self.current_minion.improve()
        else:
            minion_result = await self.current_minion.execute()

        # Check if minion returned AgentResponse or just answer
        if isinstance(minion_result, AgentResponse):
            self.agent_response = minion_result
            answer_raw = minion_result.raw_response
        else:
            # Fallback for minions that don't return AgentResponse yet
            self.agent_response = AgentResponse(
                raw_response=minion_result,
                answer=minion_result,
                score=1.0,
                terminated=False,
                truncated=False,
                info={}
            )
            answer_raw = minion_result

        # Apply post-processing if specified
        post_processing = None
        if self.worker_config and 'post_processing' in self.worker_config:
            post_processing = self.worker_config['post_processing']
        elif self.input.post_processing:
            post_processing = self.input.post_processing

        if post_processing:
            processed_response = self.input.apply_post_processing(answer_raw, post_processing)
        else:
            processed_response = answer_raw

        # Only update raw_response, preserve answer and is_final_answer
        self.agent_response.raw_response = processed_response
        
        # Update input state for compatibility
        self.answer = self.input.answer = self.agent_response.answer
        self.answer_raw = self.input.answer_raw = processed_response
        
        return self.agent_response

    async def invoke_minion_and_improve(self, klass, name, max_iterations=3):
        self.input.update_execution_state(current_iteration=0)
        self.save_execution_state()

        agent_response = await self.invoke_minion(klass)
        self.answer = agent_response.answer

        await self.update_stats(name, self.answer, self.answer_raw)

        check = self.input.check
        if self.worker_config and 'check' in self.worker_config:
            check = self.worker_config["check"]

        if not check:
            return agent_response

        for iteration in range(int(check)):
            self.input.update_execution_state(current_iteration=iteration)
            self.save_execution_state()

            check_router_minion = CheckRouterMinion(input=self.input, brain=self.brain, worker_config=self.worker_config)
            check_result = await check_router_minion.execute()

            self.input.update_execution_state(check_result=check_result)
            self.save_execution_state()

            if check_result and check_result["correct"]:
                return agent_response

            # If the check fails, try invoking the minion again
            agent_response = await self.invoke_minion(klass, improve=True)
            self.answer = self.input.answer = agent_response.answer
            await self.update_stats(name, self.answer, self.answer_raw)

        return agent_response

    def save_execution_state(self):
        """保存执行状态"""
        if self.input.save_state:
            self.input.save_state(f"state_{self.input.query_id}.pkl")

    def load_execution_state(self):
        """加载执行状态"""
        if self.input.save_state:
            loaded_input = Input.load_state(f"state_{self.input.query_id}.pkl")
            if loaded_input:
                self.input = loaded_input

    def pause(self):
        """暂停执行并保存当前状态"""
        self.save_execution_state()

    async def resume(self):
        """从上次保存的状态恢复执行"""
        self.load_execution_state()
        await self.execute()
    
    async def execute_stream(self):
        """流式执行方法"""
        self.load_execution_state()
        
        # 获取 minion 类和名称
        klass, name = await self.get_minion_class_and_name()
        
        # 流式执行不支持改进循环，直接执行一次
        async for chunk in self._invoke_minion_stream(klass):
            yield chunk
    
    async def _invoke_minion_stream(self, klass):
        """流式调用 minion"""
        if isinstance(klass, str):
            klass = MINION_REGISTRY.get(klass, CotMinion)

        self.input.update_execution_state(
            current_minion=klass.__name__,
            chosen_minion=klass.__name__
        )

        self.current_minion = klass(input=self.input, brain=self.brain, worker_config=self.worker_config)
        self.add_followers(self.current_minion)
        
        # 检查 minion 是否支持流式输出
        if hasattr(self.current_minion, 'execute_stream'):
            async for chunk in self.current_minion.execute_stream():
                yield chunk
        else:
            # 回退到普通执行
            minion_result = await self.current_minion.execute()
            if isinstance(minion_result, AgentResponse):
                yield minion_result.answer if minion_result.answer else str(minion_result.raw_response)
            else:
                yield str(minion_result)

    @staticmethod
    def serialize_function(func: Callable) -> str:
        """Serialize a function to a string."""
        return dill.dumps(func).hex()

    @staticmethod
    def deserialize_function(func_str: str) -> Callable:
        """Deserialize a function from a string."""
        return dill.loads(bytes.fromhex(func_str))


@register_worker_minion
class OptillmMinion(WorkerMinion):
    """Minion that uses Optillm approaches"""
    
    _plugins_loaded = False  # Class variable to track if plugins have been loaded
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.approach = None
        
        # Load plugins if not already loaded
        if not OptillmMinion._plugins_loaded:
            from optillm import load_plugins
            load_plugins()
            OptillmMinion._plugins_loaded = True
        
    def parse_approach(self):
        """从route中解析optillm的approach和操作类型"""
        if not self.input.route or not self.input.route.startswith("optillm-"):
            raise ValueError("Invalid optillm route format")
            
        approach = self.input.route.split("-", 1)[1]
        operation = 'SINGLE'
        approaches = []
        
        if '&' in approach:
            operation = 'AND'
            approaches = approach.split('&')
        elif '|' in approach:
            operation = 'OR'
            approaches = approach.split('|')
        else:
            approaches = [approach]
            
        return operation, approaches
        
    async def execute(self):
        from optillm import execute_single_approach, execute_combined_approaches, load_plugins, \
            execute_parallel_approaches
        operation, approaches = self.parse_approach()
        
        # Determine the query to use
        if self.task:
            query = self.task.get("instruction", "") or self.task.get("task_description", "")
            # Add task context information
            if self.task.get("dependent"):
                dependent_info = "\n\nDependent outputs:\n"
                for dependent in self.task["dependent"]:
                    dependent_key = dependent.get("dependent_key")
                    if dependent_key in self.input.symbols:
                        symbol = self.input.symbols[dependent_key]
                        dependent_info += f"- {dependent_key}: {symbol.output}\n"
                query += dependent_info
        else:
            query = self.input.query
        
        if operation == 'SINGLE':
            response, tokens = execute_single_approach(
                approaches[0], 
                self.input.system_prompt, 
                query, 
                self.brain.llm.client_sync, 
                self.brain.llm.config.model
            )
        elif operation == 'AND':
            (response, tokens) = execute_combined_approaches(
                approaches,
                self.input.system_prompt,
                query,
                self.brain.llm.client_sync,
                self.brain.llm.config.model
            )
        elif operation == 'OR':
            response, tokens = execute_parallel_approaches(
                approaches,
                self.input.system_prompt,
                query,
                self.brain.llm.client_sync,
                self.brain.llm.config.model
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")

        self.answer = self.input.answer = response
        # Return AgentResponse instead of just the answer
        return AgentResponse(
            raw_response=response,
            answer=self.answer,
            score=1.0,
            terminated=False,
            truncated=False,
            info={'optillm_approach': approaches, 'operation': operation}
        )
    
    async def execute_stream(self):
        """流式执行方法 - OptillmMinion 暂不支持真正的流式输出，回退到普通执行"""
        result = await self.execute()
        if isinstance(result, AgentResponse):
            yield result.answer if result.answer else str(result.raw_response)
        else:
            yield str(result)






