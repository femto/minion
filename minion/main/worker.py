#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
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
    WORKER_PROMPT,
)
from minion.main.symbol_table import Symbol
from minion.main.task_graph import convert_tasks_to_graph
from minion.utils.utils import most_similar_minion, camel_case_to_snake_case
from minion.actions.lmp_action_node import LmpActionNode
from minion.models.schemas import (
    MetaPlan,
    Identification,
    QuestionAndAnswer,
    EnsembleLogic,
    Plan
)
from minion.utils.answer_extraction import extract_final_answer, extract_longest_json_from_string, extract_python, \
    extract_answer

class WorkerMinion(Minion):
    pass

class RawMinion(WorkerMinion):
    """Raw minion that directly queries LLM without any prompt processing or modifications"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = ""

    async def execute(self):
        node = LmpActionNode(self.brain.llm)
        response = await node.execute(self.input.query, system_prompt=self.input.system_prompt)

        self.answer_raw = self.input.answer_raw = response
        self.answer = self.input.answer = response
        return self.answer

@register_worker_minion
class NativeMinion(WorkerMinion):
    """native minion, directly asks llm for answer"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = ""

    async def execute(self):
        prompt = Template(WORKER_PROMPT)
        prompt = prompt.render(input=self.input)
        
        node = LmpActionNode(self.brain.llm)
        response = await node.execute(prompt)
        self.raw_answer = self.input.answer_raw = response
        self.answer = self.input.answer = response
        return self.answer


@register_worker_minion
class CotMinion(WorkerMinion):
    """Chain of Thought (CoT) Strategy, Ask the LLM to think step-by-step, explaining each part of the problem to enhance the accuracy of the answer. Please noted you can't access web or user's local computer, so if you need information from the web or from user's local computer, DON'T USE THIS STRATEGY."""

    def __init__(self, worker_config=None, **kwargs):
        super().__init__(worker_config=worker_config, **kwargs)
        self.worker_config = worker_config
        self.input.instruction = "let's think step by step to solve this problem"

    async def execute(self):
        prompt = Template(COT_PROBLEM_INSTRUCTION + WORKER_PROMPT)
        prompt = prompt.render(input=self.input)

        node = LmpActionNode(self.brain.llm)
        response = await node.execute(prompt)
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
            self.answer = extract_final_answer(response)

        self.input.answer = self.answer
        self.answer_raw = self.input.answer_raw = response
        return self.answer_raw

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
        prompt = Template(DCOT_PROMPT)
        prompt = prompt.render(input=self.input)
        
        node = LmpActionNode(self.brain.llm)
        response = await node.execute(prompt)
        
        self.answer_node = node
        self.answer = self.input.answer = extract_answer(response)
        self.answer_raw = self.input.answer_raw = response
        
        return self.answer


@register_worker_minion
class MultiPlanMinion(WorkerMinion):
    "This Strategy will first generate multiple plan, and then compare each plan, see which one is more promising to produce good result, first try most promising plan, then to less promising plan."
    pass


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

            response = await LmpActionNode(llm=self.brain.llm).execute(filled_template)

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

        for index, task_id in enumerate(sorted_tasks[start_index:], start=start_index):
            for task in self.plan:
                if task["task_id"] == task_id:
                    task_minion = TaskMinion(brain=self.brain, input=self.input, task=task)
                    result = await task_minion.execute()
                    self.input.symbols[task["output_key"]] = Symbol(
                        result, task["output_type"], task["output_description"]
                    )

                    self.input.update_execution_state(current_task_index=index + 1, last_completed_task=task_id)
                    self.save_execution_state()

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


@register_worker_minion
class MathPlanMinion(PlanMinion):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_prompt = MATH_PLAN_PROMPT


class TaskMinion(WorkerMinion):
    def __init__(self, task=None, **kwargs):
        super().__init__(**kwargs)
        self.input.task = task
        self.task = task

    async def choose_minion_and_run(self):
        choose_template = Template(TASK_ROUTE_PROMPT)

        # filter out smart, since we don't want choose smart following smart again
        # also filter out ScoreMinion
        filtered_registry = {key: value for key, value in MINION_REGISTRY.items()}
        filled_template = choose_template.render(minions=filtered_registry, input=self.input, task=self.task)

        meta_plan = await LmpActionNode(llm=self.brain.llm).execute(filled_template, response_format=MetaPlan)

        name = meta_plan.name
        name = most_similar_minion(name, filtered_registry.keys())
        klass = filtered_registry[name]
        minion = klass(input=self.input, brain=self.brain, task=self.task)

        # 确保至少执行一次
        result = await minion.execute()
        self.answer = self.task["answer"] = result
        self.input.symbols[self.task["output_key"]] = result
        print("#####OUTPUT#####")
        print(f"{self.task['output_key']}:{result}")

        # 如果需要检查，则进行额外的检查循环
        if int(self.input.task_check) > 0:
            for iteration in range(int(self.input.task_check)):
                check_minion = CheckMinion(input=self.input, brain=self.brain)
                check_result = await check_minion.execute()
                
                if check_result and check_result["correct"]:
                    return self.answer
                    
                # 如果检查失败，添加反馈信息到input中
                # if check_result:
                #     self.input.feedback = check_result.get("feedback", "")
                #     self.input.error = check_result.get("error", "")
                #     logger.info(f"Check failed on iteration {iteration + 1}. Feedback: {self.input.feedback}")
                    
                # 使用反馈信息重新执行
                result = await minion.execute()
                self.answer = self.task["answer"] = result
                self.input.symbols[self.task["output_key"]] = result
                print("#####OUTPUT#####")
                print(f"{self.task['output_key']}:{result}")

                # 清除反馈信息，为下一次迭代做准备
                self.input.feedback = ""
                self.input.error = ""

        return self.answer

    async def execute(self):
        return await self.choose_minion_and_run()


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
                    + WORKER_PROMPT
                    + TASK_INPUT
                    + """

 also please check previous error, do the modification according to previous error if there's previous error.
 Previous error:
 {{error}}"""
                )
                prompt = prompt.render(input=self.input, task=self.task, error=error)

            code = await node.execute(prompt)

            code = extract_python(code, self.input.entry_point)
            print(code)

            self.answer_code = self.input.answer_code = code

            self.input.run_id = self.input.run_id or uuid.uuid4()
            context = {"code": f"<id>{self.input.query_id}/{self.input.run_id}</id>{code}"}
            # Execute the code in the Python environment using step()
            # The context contains the code with query/run ID tags
            result = self.python_env.step(context["code"])
            obs = result[0]  # obs

            if obs["error"]:
                error = obs["error"]
                logger.error(error)
                continue  # try again?
            output, error = obs["output"], obs["error"]
            self.answer = self.input.answer = output #answer is only output
            # print("#####OUTPUT#####")
            # print(output)
            print(f"###solution###:{self.answer}")
            return self.answer  # obs
        self.answer = self.input.answer = ""
        return self.answer

    async def execute_code_solution(self):
        error = ""
        for i in range(5):
            node = LmpActionNode(llm=self.brain.llm)
            prompt = Template(
                PYTHON_PROMPT
                + WORKER_PROMPT
                + """
                Generate a complete Python solution for the given problem.
                This may include one or more functions, classes, or a full module as needed.
                Do not include any explanations or comments, just the code.
                
                Previous error (if any):
                {{error}}
                """
            )
            prompt = prompt.render(input=self.input, error=error)

            code = await node.execute(prompt)
            code = extract_python(code, self.input.entry_point)
            self.answer = self.input.answer = code
            return self.answer

    async def execute_generation(self):
        error = ""
        for i in range(5):
            node = LmpActionNode(llm=self.brain.llm)
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

            file_structure_text = await node.execute(prompt)
            file_structure = self.extract_file_structure(file_structure_text)
            self.save_files(file_structure)
            self.answer = self.input.answer = "Files generated successfully"
            return self.answer

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


@register_worker_minion
class MathMinion(PythonMinion):
    "This is a problem involve math, you need to use math tool to solve it"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.query_type = "calculate"
        self.input.instruction = "This is a math problem, write python code to solve it"


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
        worker = RouteMinion(input=self.input, brain=self.brain, worker_config=worker_config)
        answer = await worker.execute()

        # Apply post-processing if specified
        if self.input.post_processing:
            processed_answer = self.input.apply_post_processing(answer)
        else:
            processed_answer = answer
        self.answer = processed_answer
        return worker, processed_answer

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
        
        for worker_config in self.input.execution_config["workers"]:
            minion_name = worker_config["name"]
            count = worker_config["count"]
            post_processing = worker_config.get("post_processing")

            for i in range(count):
                self.execution_state["current_minion"] = minion_name
                self.execution_state["current_iteration"] = i
                self.save_execution_state()

                worker, _ = await self.invoke_minion(minion_name, worker_config)
                workers.append(worker)

        # Process results using the selected strategy
        strategy = strategy_class(
            input=self.input, 
            brain=self.brain, 
            workers=workers
        )
        final_result = await strategy.execute()
        self.answer = self.input.answer = final_result
        return final_result

    async def execute_single(self):
        return await self.invoke_minion(self.input.route)

    async def execute(self):
        self.load_execution_state()

        if self.input.execution_state.current_minion:
            # Resume from previous state, assume pre_processing already been done
            if hasattr(self.input, 'execution_config') and self.input.execution_config['type'] == "ensemble":
                await self.execute_ensemble()
            else:
                await self.execute_single()
        else:
            # Start new execution

            # Execute pre-processing first
            await self.execute_pre_processing()

            await self.choose_minion_and_run()

        # Clean up python env
        self.brain.cleanup_python_env(input=self.input)
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


class IdentifyMinion(Minion):
    async def execute(self):
        prompt = Template(IDENTIFY_PROMPT)
        prompt = prompt.render(input=self.input)

        node = LmpActionNode(self.brain.llm)
        identification = await node.execute(prompt, response_format=Identification)
        
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

            node = LmpActionNode(self.brain.llm)
            answer = await node.execute_answer(prompt)
            
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
                        meta_plan = await node.execute(filled_template, response_format=MetaPlan)
                        
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
            
            # 如果没有route配置或所有route LLM都失败，使用默认的brain.llm
            try:
                node = LmpActionNode(self.brain.llm)
                meta_plan = await node.execute(filled_template, response_format=MetaPlan)
                
                name = meta_plan.name
                if name in filtered_registry:
                    logger.info(f"Choosing Route: {name} using default brain.llm")
                    return filtered_registry[name], name
                else:
                    # 尝试找到最相似的名称
                    similar_name = most_similar_minion(name, filtered_registry.keys())
                    logger.warning(f"Recommended route {name} not found, using similar route: {similar_name}")
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
        await self.invoke_minion_and_improve(klass, name, max_iterations=max_iterations)
        
        return self.answer

    async def invoke_minion(self, klass, improve=False):
        if isinstance(klass, str):
            klass = MINION_REGISTRY.get(klass, CotMinion)

        self.input.update_execution_state(
            current_minion=klass.__name__,
            chosen_minion=klass.__name__
        )

        self.current_minion = klass(input=self.input, brain=self.brain, worker_config=self.worker_config)
        self.add_followers(self.current_minion)
        if improve:
            await self.current_minion.improve()
        else:
            await self.current_minion.execute()

        answer_raw = self.current_minion.answer

        # Apply post-processing if specified
        post_processing = None
        if self.worker_config and 'post_processing' in self.worker_config:
            post_processing = self.worker_config['post_processing']
        elif self.input.post_processing:
            post_processing = self.input.post_processing

        if post_processing:
            processed_answer = self.input.apply_post_processing(answer_raw, post_processing)
        else:
            processed_answer = answer_raw

        self.answer = self.input.answer = processed_answer
        self.answer_raw = self.input.answer_raw = answer_raw
        return processed_answer

    async def invoke_minion_and_improve(self, klass, name, max_iterations=3):
        self.input.update_execution_state(current_iteration=0)
        self.save_execution_state()

        processed_answer = await self.invoke_minion(klass)

        #self.answer = self.input.answer = answer_raw
        await self.update_stats(name,self.answer, self.answer_raw)

        check = self.input.check
        if self.worker_config and 'check' in self.worker_config:
            check = self.worker_config["check"]

        if not check:
            return self.answer

        for iteration in range(int(check)):
            self.input.update_execution_state(current_iteration=iteration)
            self.save_execution_state()

            check_router_minion = CheckRouterMinion(input=self.input, brain=self.brain, worker_config=self.worker_config)
            check_result = await check_router_minion.execute()

            self.input.update_execution_state(check_result=check_result)
            self.save_execution_state()

            if check_result and check_result["correct"]:
                return self.answer

            # If the check fails, try invoking the minion again
            answer_raw = await self.invoke_minion(klass, improve=True)
            self.answer = self.input.answer = answer_raw
            await self.update_stats(name, self.answer, self.answer_raw)

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
        if not OptillmMinion._optillm_loaded:
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
        
        if operation == 'SINGLE':
            response, tokens = execute_single_approach(
                approaches[0], 
                self.input.system_prompt, 
                self.input.query, 
                self.brain.llm.client_sync, 
                self.brain.llm.config.model
            )
        elif operation == 'AND':
            (response, tokens) = execute_combined_approaches(
                approaches,
                self.input.system_prompt,
                self.input.query,
                self.brain.llm.client_sync,
                self.brain.llm.config.model
            )
        elif operation == 'OR':
            response, tokens = execute_parallel_approaches(
                approaches,
                self.input.system_prompt,
                self.input.query,
                self.brain.llm.client_sync,
                self.brain.llm.config.model
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")

        self.answer = self.input.answer = response
        return self.answer






