#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility worker minions - moderation, routing, identification, etc.
"""
import uuid
from typing import Any, Callable, Dict

import dill
from jinja2 import Template

from minion.actions.lmp_action_node import LmpActionNode
from minion.logs import logger
from minion.main.base_workers import WorkerMinion
from minion.main.check_route import CheckRouterMinion
from minion.main.input import Input
from minion.main.minion import (
    MINION_REGISTRY,
    WORKER_MINIONS,
    Minion,
    RESULT_STRATEGY_REGISTRY,
    register_worker_minion,
)
from minion.main.prompt import (
    IDENTIFY_PROMPT,
    QA_PROMPT_JINJA,
    SMART_PROMPT_TEMPLATE,
)
from minion.models.schemas import (
    MetaPlan,
    Identification,
)
from minion.types.agent_response import AgentResponse
from minion.utils.utils import camel_case_to_snake_case


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
        # Import here to avoid circular imports
        from minion.main.cot_workers import CotMinion

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
        # Import here to avoid circular imports
        from minion.main.cot_workers import CotMinion

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
        # Import here to avoid circular imports
        from minion.main.cot_workers import CotMinion

        self.load_execution_state()

        # 获取 minion 类和名称
        klass, name = await self.get_minion_class_and_name()

        # 流式执行不支持改进循环，直接执行一次
        async for chunk in self._invoke_minion_stream(klass):
            yield chunk

    async def _invoke_minion_stream(self, klass):
        """流式调用 minion"""
        # Import here to avoid circular imports
        from minion.main.cot_workers import CotMinion

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
