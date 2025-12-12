#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Planning worker minions - divide and conquer strategy
"""
import json
import os
from typing import Any, Dict

import networkx as nx
from jinja2 import Template

from minion.actions.lmp_action_node import LmpActionNode
from minion.logs import logger
from minion.main.base_workers import WorkerMinion
from minion.main.check import CheckMinion
from minion.main.input import Input
from minion.main.minion import (
    MINION_REGISTRY,
    WORKER_MINIONS,
    register_worker_minion,
)
from minion.main.prompt import (
    PLAN_PROMPT,
    TASK_ROUTE_PROMPT,
)
from minion.main.symbol_table import Symbol
from minion.main.task_graph import convert_tasks_to_graph
from minion.models.schemas import MetaPlan
from minion.utils.answer_extraction import extract_longest_json_from_string
from minion.utils.utils import most_similar_minion


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

            json_data = extract_longest_json_from_string(response)

            try:
                self.validate_json_plan(json_data)
                self.write_json_to_cache(self.input.cache_plan, json_data)
                return json_data
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


class CodeProblemMinion(PlanMinion):
    "This is a coding problem which requires stragety thinking to solve it, you will first explore the stragety space then solve it"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "This is a coding problem which requires stragety thinking to solve it, you will first explore the stragety space then solve it"
