#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import uuid
from datetime import datetime
from typing import Any, Dict

from jinja2 import Template
from mem0 import Memory
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, retry_if_exception_type

from minion import config
from minion.actions.lmp_action_node import LmpActionNode
from minion.main.input import Input
from minion.main.python_env import PythonEnv
from minion.main.local_python_env import LocalPythonEnv
from minion.main.local_python_executor import LocalPythonExecutor
from minion.main.async_python_executor import AsyncPythonExecutor
from minion.utils.utils import process_image
from minion.main.worker import ModeratorMinion
from minion.providers import create_llm_provider
from minion.types.agent_response import AgentResponse

class Mind(BaseModel):
    id: str = "UnnamedMind"
    description: str = ""
    brain: Any = None  # Brain

    async def step(self, input):
        moderator = ModeratorMinion(input=input, brain=self.brain)
        agent_response = await moderator.execute()
        
        # 直接返回ModeratorMinion的AgentResponse，保持所有状态信息
        return agent_response


class Brain:
    def __init__(
        self,
        id=None,
        memory=None,
        memory_config=None,
        llm=create_llm_provider(config.models.get("default")),
        llms={},
        python_env=None,
        stats_storer=None,
        tools=None,  # 新增: 支持工具集
    ):
        self.id = id or uuid.uuid4()
        self.minds = {}
        self.add_mind(
            Mind(
                id="left_mind",
                description="""
I'm the left mind, adept at logical reasoning and analytical thinking. I excel in tasks involving mathematics, language, and detailed analysis. My capabilities include:

Solving complex mathematical problems
Understanding and processing language with precision
Performing logical reasoning and critical thinking
Analyzing and synthesizing information systematically
Engaging in tasks that require attention to detail and structure""",
            )
        )
        self.add_mind(
            Mind(
                id="right_mind",
                description="""
I'm the right mind, flourishing in creative and artistic tasks. I thrive in activities that involve imagination, intuition, and holistic thinking. My capabilities include:

Creating and appreciating art and music
Engaging in creative problem-solving and innovation
Understanding and interpreting emotions and expressions
Recognizing patterns and spatial relationships
Thinking in a non-linear and abstract manner""",
            )
        )

        self.add_mind(
            Mind(
                id="hippocampus_mind",
                description="""I'm the hippocampus mind, specializing in memory formation, organization, and retrieval. I play a crucial role in both the storage of new memories and the recall of past experiences. My capabilities include:

Forming and consolidating new memories
Organizing and structuring information for easy retrieval
Facilitating the recall of past experiences and learned information
Connecting new information with existing knowledge
Supporting navigation and spatial memory""",
            )
        )

        # self.add_mind(Mind(id="hypothalamus", description="..."))
        self.mem = memory
        if not memory:
            if memory_config:
                self.mem = memory = Memory.from_config(memory_config)

        # Process default llm
        if isinstance(llm, str):
            self.llm = create_llm_provider(config.models.get(llm))
        else:
            self.llm = llm

        # Process llms dictionary
        self.llms = {}
        for key, value in llms.items():
            if isinstance(value, str):
                # Single model name
                self.llms[key] = create_llm_provider(config.models.get(value))
            elif isinstance(value, list):
                # List of model names or providers
                self.llms[key] = [
                    item if not isinstance(item, str) else create_llm_provider(config.models.get(item))
                    for item in value
                ]
            else:
                # Assume it's already a provider instance
                self.llms[key] = value

        # 设置工具集
        self.tools = tools or []
        
        # 默认使用 AsyncPythonExecutor，提供更好的异步支持
        self.python_env = python_env or AsyncPythonExecutor(additional_authorized_imports=["numpy", "pandas", "json", "csv", "multi_tool_use", "inspect"])

        self.stats_storer = stats_storer

    def add_tool(self, tool):
        """
        添加工具到Brain
        """
        self.tools.append(tool)

    def add_mind(self, mind):
        self.minds[mind.id] = mind
        mind.brain = self

    def process_image_input(self, input):
        if input.images:
            if isinstance(input.images, str):
                input.images = process_image(input.images)
            elif isinstance(input.images, list):
                input.images = [process_image(img) for img in input.images]
            else:
                raise ValueError("input.images should be either a string or a list of strings/images")
        return input.images

    async def step(self, state: Dict[str, Any] = None, **config_kwargs):
        # 处理state参数
        if state is None:
            state = {}
            
        # 从状态中提取参数
        input = state.get("input")
        query = config_kwargs.get("query", "")
        query_type = config_kwargs.get("query_type", "")
        system_prompt = config_kwargs.get("system_prompt")
        tools = config_kwargs.get("tools")
        messages = config_kwargs.get("messages")
        
        # 验证state中必须有input
        if input is None:
            if not query:
                raise ValueError("State must contain 'input' or query must be provided in config_kwargs")
            # 从 query 创建 Input，移除已使用的参数避免重复
            input_kwargs = config_kwargs.copy()
            input_kwargs.pop('query', None)
            input_kwargs.pop('query_type', None) 
            input_kwargs.pop('system_prompt', None)
            input_kwargs.pop('tools', None)
            input_kwargs.pop('messages', None)
            
            input = Input(query=query, query_type=query_type, query_time=datetime.utcnow(), **input_kwargs)
            state["input"] = input
        
        # 处理传入的tools
        current_tools = tools if tools is not None else state.get("tools", self.tools)
        
        # 如果传入了messages，优先使用messages
        if messages is not None:
            # 从messages中提取query和system_prompt
            if isinstance(messages, list):
                for msg in messages:
                    if isinstance(msg, dict):
                        if msg.get("role") == "user":
                            query = msg.get("content", query)
                        elif msg.get("role") == "system" and system_prompt is None:
                            system_prompt = msg.get("content", "")
            input = input or Input(query=query, query_type=query_type, query_time=datetime.utcnow(), **config_kwargs)
            input.query = query  # 覆盖query
        else:
            # 创建Input
            input = input or Input(query=query, query_type=query_type, query_time=datetime.utcnow(), **config_kwargs)
            
        input.query_id = input.query_id or uuid.uuid4()
        input.images = self.process_image_input(input)  # normalize image format to base64
        
        # 设置工具和系统提示
        input.tools = current_tools
        if system_prompt is not None:
            input.system_prompt = system_prompt

        # 选择心智
        mind_id = input.mind_id or await self.choose_mind(input)
        if mind_id == "left_mind":
            self.llm.config.temperature = 1
        elif mind_id == "right_mind":
            self.llm.config.temperature = 1
        mind = self.minds[mind_id]
        
        # 执行步骤，确保返回AgentResponse
        result = await mind.step(input)
        
        # 确保结果是AgentResponse格式
        if not isinstance(result, AgentResponse):
            result = AgentResponse.from_tuple(result)
            
        return result

    def cleanup_python_env(self, input):
        if hasattr(self.python_env, 'step'):
            # Legacy python env (LocalPythonEnv, RpycPythonEnv)
            self.python_env.step(f"<id>{input.query_id}</id>RESET_CONTAINER_SPECIAL_KEYWORD")
        else:
            # LocalPythonExecutor or AsyncPythonExecutor - reset by re-initializing state only
            if hasattr(self.python_env, 'send_variables'):
                self.python_env.send_variables(variables={})
            # Don't clear tools - they should persist across executions
            # Tools are only set when starting a new session with new tools

    async def choose_mind(self, input):
        mind_template = Template(
            """
I have minds:
{% for mind in minds %}
1. **ID:** {{ mind.id }}  
   **Description:** 
   "{{ mind.description }}"
{% endfor %}
According to the current user's query, 
which is of query type: {{ input.query_type }},
and user's query: {{ input.query }}
help me choose the right mind to process the query.
return the id of the mind, please note you *MUST* return exactly case same as I provided here, do not uppercase or downcase yourself.
"""
        )

        # Create the filled template
        filled_template = mind_template.render(minds=self.minds.values(), input=input)

        try:
            lmp_action_node = LmpActionNode(llm=self.llm)
            result = await lmp_action_node.execute_answer(filled_template)

            # Ensure the result is a valid mind ID
            if result not in self.minds:
                result = "left_mind"
                #raise ValueError(f"Invalid mind ID returned: {result}")

            return result
        except Exception as e:
            return "left_mind" #EXISTING_ANSWER_PROMPT for llama3.2 which can't return valid json


Mind.model_rebuild()