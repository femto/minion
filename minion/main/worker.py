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
from .optillm import execute_single_approach
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_none

from minion.actions.action_node import ActionNode
from minion.configs.config import config
from minion.logs import logger
from minion.main.check import CheckMinion
from minion.main.input import Input
from minion.main.minion import (
    MINION_REGISTRY,
    MINION_ROUTE_DOWNSTREAM,
    Minion,
    register_route_downstream,
)
from minion.main.preprocessing import PreprocessingMinion
from minion.main.prompt import (
    ASK_PROMPT,
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
)
from minion.main.symbol_table import Symbol
from minion.main.task_graph import convert_tasks_to_graph
from minion.main.utils import most_similar_minion
from minion.actions.lmp_action_node import LmpActionNode
from minion.models.schemas import (
    MetaPlan,
    Identification,
    QuestionAndAnswer,
    EnsembleLogic,
    Plan
)
from minion.utils.answer_extraction import extract_final_answer

class WorkerMinion(Minion):
    pass

@register_route_downstream
class NativeMinion(WorkerMinion):
    """native minion, directly asks llm for answer"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = ""

    async def execute(self):
        context = {"messages": [{"role": "user", "content": ASK_PROMPT.format(input=self.input)}]}
        response = await self.execute_action(self.llm_action, context)
        self.answer = self.input.answer = extract_final_answer(response)
        self.raw_answer = self.input.answer_raw = response
        return self.answer


@register_route_downstream
class CotMinion(WorkerMinion):
    """Chain of Thought (CoT) Strategy, Ask the LLM to think step-by-step, explaining each part of the problem to enhance the accuracy of the answer. Please noted you can't access web or user's local computer, so if you need information from the web or from user's local computer, DON'T USE THIS STRATEGY."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "let's think step by step to solve this problem"

    async def execute(self):
        prompt = (COT_PROBLEM_INSTRUCTION + ASK_PROMPT).format(input=self.input)
        context = {"messages": [{"role": "user", "content": prompt}], "images": self.input.images}
        
        node = LmpActionNode(self.brain.llm)
        response = await node.execute(prompt)
        self.answer_node = node

        if self.input.query_type == "code_solution" or self.input.post_processing == "extract_python":
            #self.answer = self.extract_python_code(response) #or we don't do anything, let route minion extract the answer?
            self.answer = response #we don't do anything, let route minion extract the answer? so route minion has access to answer raw?
        else:
            self.answer = extract_final_answer(response)

        self.input.answer = self.answer
        self.answer_raw = self.input.answer_raw = response
        return self.answer_raw

    def extract_python_code(self, content):
        # Regex pattern to extract code inside ```python ``` blocks
        pattern = r"```python\s*(.*?)\s*```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

class DotMinion(WorkerMinion):
    """Diagram of Thought (DoT) Strategy"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "let's think step by step to solve this problem"

    async def execute(self):
        prompt = Template(DOT_PROMPT)
        prompt = prompt.render(input=self.input)
        
        node = LmpActionNode(self.brain.llm)
        response = await node.execute_answer(prompt)
        self.answer_node = response
        self.answer = self.input.answer = extract_final_answer(response)

        for _ in range(3):  # try using llm 3 times to extract answer
            if not self.answer:
                # try using llm to extract answer
                node = LmpActionNode(self.brain.llm)
                response = await node.execute_answer("extract final answer from result")
                self.answer = self.input.answer = response
            else:
                break
        self.raw_answer = self.input.answer_raw = response
        return self.answer


# https://x.com/_philschmid/status/1842846050320544016
class DcotMinion(WorkerMinion):
    """Dynamic Chain of Thought Strategy"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = ""

    async def execute(self):
        node = ActionNode(key="answer", expected_type=str, instruction="", example="")
        prompt = Template(DCOT_PROMPT)
        prompt = prompt.render(input=self.input)
        node = await node.fill(context=prompt, llm=self.brain.llm, schema="raw")
        self.answer_node = node
        self.answer = self.input.answer = extract_answer(node.content)

        self.raw_answer = self.input.answer_raw = node.content
        return self.answer  # maybe also adds score?


@register_route_downstream
class MultiPlanMinion(WorkerMinion):
    "This Strategy will first generate multiple plan, and then compare each plan, see which one is more promising to produce good result, first try most promising plan, then to less promising plan."
    pass


@register_route_downstream
class PlanMinion(WorkerMinion):
    "Divide and Conquer Strategy, Divide the problem into smaller subproblems, solve each subproblem independently, and then merge the results for the final solution."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_prompt = PLAN_PROMPT
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

    @retry(stop=stop_after_attempt(5), wait=wait_none())  # Retries up to 5 times
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

            plan = await ActionNode.from_pydantic(Plan).fill(context=filled_template, llm=self.brain.llm, schema="raw")

            json = extract_json_from_string(plan.content)

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


@register_route_downstream
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

        # if self.input.route:
        #     return filtered_registry[self.input.route]

        meta_plan = await ActionNode.from_pydantic(MetaPlan).fill(context=filled_template, llm=self.brain.llm)

        name = meta_plan.instruct_content.name

        name = most_similar_minion(name, filtered_registry.keys())
        klass = filtered_registry[name]
        minion = klass(input=self.input, brain=self.brain, task=self.task, task_execution=True)

        print("using task level check")
        for _ in range(3):
            result = await minion.execute()
            self.answer = self.task["answer"] = result
            self.input.symbols[self.task["output_key"]] = result
            print("#####OUTPUT#####")
            print(f"{self.task['output_key']}:{result}")
            check_minion = CheckMinion(input=self.input, brain=self.brain)
            check_result = await check_minion.execute()
            if check_result and check_result["correct"]:
                return self.answer

    async def execute(self):
        return await self.choose_minion_and_run()


@register_route_downstream
class PythonMinion(WorkerMinion):
    "This problem requires writing code to solve it, write python code to solve it"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.python_env_action = EnvironmentActionNode(self.brain.python_env.step)

    async def execute(self):
        if self.input.query_type == "calculate":
            return await self.execute_calculation()
        elif self.input.query_type == "code_solution":
            return await self.execute_code_solution()
        elif self.input.query_type == "generate":
            return await self.execute_generation()
        else:
            return await self.execute_calculation()  # 默认行为

    async def execute_calculation(self):
        error = ""
        for i in range(5):
            node = ActionNode(
                key="code",
                expected_type=str,
                instruction="the solution code",
                example="",
            )
            if not self.task_execution:
                prompt = Template(
                    PYTHON_PROMPT
                    + ASK_PROMPT_JINJA
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
                    + ASK_PROMPT_JINJA
                    + TASK_INPUT
                    + """

 also please check previous error, do the modification according to previous error if there's previous error.
 Previous error:
 {{error}}"""
                )
                prompt = prompt.render(input=self.input, task=self.task, error=error)

            node = await node.fill(context=prompt, llm=self.brain.llm, schema="raw")
            # code = node.instruct_content.code
            # print(code)

            def extract_code(text):
                # Regex pattern to extract code inside ```python ``` blocks
                pattern = r"```python(.*?)```"
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    # Return the extracted code, strip to remove leading/trailing newlines
                    return match.group(1).strip()
                return text

            # deepseek may still put ```python...``` in the returned json
            code = extract_code(node.content)
            self.answer_code = self.input.answer_code = code

            self.input.run_id = self.input.run_id or uuid.uuid4()
            context = {"code": f"<id>{self.input.query_id}/{self.input.run_id}</id>{code}"}
            result = await self.execute_action(self.python_env_action, context)
            obs = result[0]  # obs

            if obs["error"]:
                error = obs["error"]
                logger.error(error)
                continue  # try again?
            output, error = obs["output"], obs["error"]
            self.answer = self.input.answer = output
            # print("#####OUTPUT#####")
            # print(output)
            print(f"###solution###:{self.answer}")
            return self.answer  # obs
        self.answer = self.input.answer = ""
        return self.answer

    async def execute_code_solution(self):
        error = ""
        for i in range(5):
            node = ActionNode(
                key="code",
                expected_type=str,
                instruction="Generate the complete code solution",
                example="",
            )
            prompt = Template(
                PYTHON_PROMPT
                + ASK_PROMPT_JINJA
                + """
                Generate a complete Python solution for the given problem.
                This may include one or more functions, classes, or a full module as needed.
                Do not include any explanations or comments, just the code.
                
                Previous error (if any):
                {{error}}
                """
            )
            prompt = prompt.render(input=self.input, error=error)

            node = await node.fill(context=prompt, llm=self.brain.llm, schema="raw")
            code = self.extract_code(node.content)
            self.answer = self.input.answer = code
            return self.answer

    async def execute_generation(self):
        error = ""
        for i in range(5):
            node = ActionNode(
                key="files",
                expected_type=str,
                instruction="Generate the file structure and contents",
                example="",
            )
            prompt = Template(
                PYTHON_PROMPT
                + ASK_PROMPT_JINJA
                + """
                Create the necessary file structure and contents for the given task.
                Include file paths and their contents.
                
                Previous error (if any):
                {{error}}
                """
            )
            prompt = prompt.render(input=self.input, error=error)

            node = await node.fill(context=prompt, llm=self.brain.llm, schema="raw")
            file_structure = self.extract_file_structure(node.content)
            self.save_files(file_structure)
            self.answer = self.input.answer = "Files generated successfully"
            return self.answer

    def extract_code(self, text):
        # 提取代码的逻辑，保持不变
        pattern = r"```python(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def extract_file_structure(self, text):
        # 从LLM输出中提取项目结构和文件内容
        # 这需要根据LLM的出格式进行定���
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


@register_route_downstream
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

    async def invoke_minion(self, minion_name):
        self.input.run_id = uuid.uuid4()  # a new run id for each run
        self.input.route = minion_name
        route_minion = RouteMinion(input=self.input, brain=self.brain)
        answer_raw = await route_minion.execute()

        # Apply post-processing if specified
        if self.input.post_processing:
            processed_answer = self.input.apply_post_processing(answer_raw)
        else:
            processed_answer = answer_raw

        self.answer = self.input.answer = processed_answer
        return processed_answer

    async def choose_minion_and_run(self):
        # Check if we have ensemble configuration
        if hasattr(self.input, 'type') and self.input.type == "ensemble":
            return await self.execute_ensemble()
        else:
            return await self.execute_single()

    async def execute_ensemble(self):
        if not hasattr(self.input, 'workers'):
            return await self.execute_single()

        results = {}
        total_count = sum(worker["count"] for worker in self.input.workers)
        majority_count = total_count // 2 + 1

        for worker in self.input.workers:
            minion_name = worker["name"]
            count = worker["count"]
            post_processing = worker.get("post_processing")

            for i in range(count):
                self.execution_state["current_minion"] = minion_name
                self.execution_state["current_iteration"] = i
                self.save_execution_state()

                answer_raw = await self.invoke_minion(minion_name)
                
                # Apply post-processing if specified
                if post_processing:
                    self.input.post_processing = post_processing
                    processed_answer = self.input.apply_post_processing(answer_raw)
                else:
                    processed_answer = answer_raw

                if processed_answer in results:
                    results[processed_answer] += 1
                else:
                    results[processed_answer] = 1

                # Check for majority
                if results[processed_answer] >= majority_count:
                    self.answer = self.input.answer = processed_answer
                    return processed_answer

        # No majority reached, return most common result
        most_voted_result = max(results.items(), key=lambda x: x[1])[0]
        self.answer = self.input.answer = most_voted_result
        return most_voted_result

    async def execute_single(self):
        return await self.invoke_minion(self.input.route)

    async def execute(self):
        self.load_execution_state()

        if self.input.execution_state.current_minion:
            # Resume from previous state
            if hasattr(self.input, 'type') and self.input.type == "ensemble":
                await self.execute_ensemble()
            else:
                await self.execute_single()
        else:
            # Start new execution
            await self.choose_minion_and_run()

        # Clean up python env
        self.brain.cleanup_python_env(input=self.input)
        return self.answer

    def save_execution_state(self):
        """保存执行状态"""
        if self.input.save_state:
            self.input.exec_save_state(f"state_{self.input.query_id}.pkl")

    def load_execution_state(self):
        """加载执行状态"""
        if self.input.save_state:
            loaded_input = Input.exec_load_state(f"state_{self.input.query_id}.pkl")
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.execution_state: Dict[str, Any] = {}
        self.current_minion = None

    async def invoke_minion(self, klass):
        if isinstance(klass, str):
            klass = MINION_REGISTRY.get(klass, CotMinion)
            
        self.input.update_execution_state(
            current_minion=klass.__name__,
            chosen_minion=klass.__name__
        )
        
        self.current_minion = klass(input=self.input, brain=self.brain)
        self.add_followers(self.current_minion)
        await self.current_minion.execute()
        
        answer_raw = self.current_minion.answer
        
        # Apply post-processing if specified
        if self.input.post_processing:
            processed_answer = self.input.apply_post_processing(answer_raw)
        else:
            processed_answer = answer_raw
            
        self.answer = self.input.answer = processed_answer
        return processed_answer

    async def choose_minion_and_run(self):
        # 检查是否是optillm路由
        if self.input.route and self.input.route.startswith("optillm-"):
            klass = OptillmMinion
            approach = self.input.route.split("-", 1)[1]  # 提取 approach 名称
            logger.info(f"Using OptillmMinion with approach: {approach}")
        else:
            # 原有的minion选择逻辑
            choose_template = Template(SMART_PROMPT_TEMPLATE)
            filtered_registry = {key: value for key, value in MINION_REGISTRY.items()}
            filled_template = choose_template.render(minions=filtered_registry, input=self.input)

            node = LmpActionNode(self.brain.llm)
            meta_plan = await node.execute(filled_template, response_format=MetaPlan)

            name = self.input.route or meta_plan.name
            name = most_similar_minion(name, filtered_registry.keys())
            logger.info(f"Choosing Route: {name}")
            klass = filtered_registry[name]

        # 创建并执行选择的minion
        minion = klass(input=self.input, brain=self.brain)
        self.add_followers(minion)
        await minion.execute()

        self.answer = self.input.answer
        return self.answer

    async def invoke_minion_and_improve(self, klass, name, max_iterations=3):
        self.input.update_execution_state(current_iteration=0)
        self.save_execution_state()

        answer_raw = await self.invoke_minion(klass)

        self.answer = self.input.answer = answer_raw
        await self.update_stats(name, answer_raw)

        if not self.input.check:
            return self.answer

        for iteration in range(int(self.input.check)):
            self.input.update_execution_state(current_iteration=iteration)
            self.save_execution_state()

            check_minion = CheckMinion(input=self.input, brain=self.brain)
            check_result = await check_minion.execute()

            self.input.update_execution_state(check_result=check_result)
            self.save_execution_state()

            if check_result and check_result["correct"]:
                return self.answer

            # If the check fails, try invoking the minion again
            answer_raw = await self.invoke_minion(klass)
            self.answer = self.input.answer = answer_raw
            await self.update_stats(name, answer_raw)

        return self.answer

    async def execute(self):
        self.load_execution_state()

        if self.input.execution_state.chosen_minion:
            # 从上次状态恢复
            name = self.input.execution_state.chosen_minion
            klass = MINION_REGISTRY.get(name, CotMinion)
            iteration = self.input.execution_state.current_iteration
            await self.invoke_minion_and_improve(klass, name, max_iterations=3 - iteration)
        else:
            # 开始新的执行
            await self.choose_minion_and_run()

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

@register_route_downstream
class OptillmMinion(WorkerMinion):
    """Minion that uses Optillm approaches"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.approach = None
        
    def extract_approach(self):
        """从route中提取optillm的approach"""
        if self.input.route and self.input.route.startswith("optillm-"):
            self.approach = self.input.route.split("-", 1)[1]
            return True
        return False
        
    async def execute(self):
        if not self.extract_approach():
            raise ValueError("Invalid optillm route format")

        response, tokens = execute_single_approach(self.approach, self.input.system_prompt, self.input.query, self.brain.llm.client_ell, self.brain.llm.config.model)
        
        self.answer = self.input.answer = response

        return self.answer







