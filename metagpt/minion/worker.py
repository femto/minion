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
from typing import List

import networkx as nx
from jinja2 import Template
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_none

from metagpt.actions.action_node import ActionNode
from metagpt.logs import logger
from metagpt.minion.check import CheckMinion
from metagpt.minion.minion import (
    MINION_REGISTRY,
    MINION_ROUTE_DOWNSTREAM,
    Minion,
    register_route_downstream,
)
from metagpt.minion.prompt import (
    ASK_PROMPT,
    ASK_PROMPT_JINJA,
    COT_PROBLEM_INSTRUCTION,
    DOT_PROMPT,
    IDENTIFY_PROMPT,
    MERGE_PROMPT,
    PYTHON_PROMPT,
    QA_PROMPT_JINJA,
    SCORE_PROMPT,
    SMART_PROMPT_TEMPLATE,
    TASK_INPUT,
)
from metagpt.minion.symbol_table import Symbol
from metagpt.minion.task_graph import convert_tasks_to_graph
from metagpt.minion.utils import (
    extract_math_answer,
    extract_number_from_string,
    most_similar_minion,
)
from metagpt.utils.custom_decoder import CustomDecoder


def extract_json_from_string(text):
    # Regular expression pattern to match all content between ```json and ```
    pattern = r"```json\s*([\s\S]*?)\s*```"

    # Find all matches in the input text
    matches = re.findall(pattern, text)

    if matches:
        # Heuristic: Select the longest JSON block, assuming it's the most comprehensive
        longest_match = max(matches, key=len)

        try:
            # Decode the longest JSON block
            return CustomDecoder(strict=False).decode(longest_match)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON content in the selected block.") from e
    else:
        raise ValueError("No JSON content found.")


def extract_final_answer(text):
    # Match for <final_answer> tag
    match_tag = re.search(r"<final_answer>\s*(.*?)\s*</final_answer>", text, re.DOTALL)
    if match_tag:
        return match_tag.group(1).strip()

    return None


class MetaPlan(BaseModel):
    name: str = Field(default="naive", description="The name of stragety.")
    score: float = Field(
        default=0,
        description="estimate score of choosing this stragety of success, 1.0 means perfect match,"
        "if we choose this stragety, we are most likely to solve this problem, 0.0 means a"
        "bad match, if we choose this stragety, we are most likely fail to solve this problem",
    )
    # complexity: str = Field(
    #     default="",
    #     description="estimate this problem's difficulty, when the problem is simple,only required one or several steps to solve this problem,"
    #     "return low, when the problem difficulty is medium and require more steps to solve it, return medium,"
    #     "when the problem seemed quite difficult, generally should involve complex process and careful step planning to solve it,"
    #     "return high",
    # )
    # query_range: str = Field(
    #     default="",
    #     description="if it's a short range query that only require few steps, few context memory to complete the query, return short, "
    #     "otherwise multiple step, require long term range attention to store relevant long context memory,"
    #     "return long",
    # )  # short range query, or multiple step range like writing a very long novel
    # num_trials: int = Field(
    #     default=0,
    #     description="number of trials to try using the strategy to solve this problem, sometimes one strategy may fail, but we retry this strategy"
    #     "we'll succeed, so need need some number of trials",
    # )
    # is_finished: bool = Field(
    #     default=False, description="Whether current question already been answered by current answer"
    # )


class Identification(BaseModel):
    complexity: str = Field(
        default="",
        description="estimate this problem's difficulty, when the problem is simple,only required one or several steps to solve this problem,"
        "return low, when the problem difficulty is medium and require more steps to solve it, return medium,"
        "when the problem seemed quite difficult, generally should involve complex process and careful step planning to solve it,"
        "return high",
    )
    difficulty: str = Field(
        default="",
        description="Represents the educational difficulty level of the problem. Return elementary school/middle school/high school/undergraduate/graduate/postgraduate/olympiad etc.",
    )

    query_range: str = Field(
        default="",
        description="Determine the required range of attention for processing the query based on its complexity and the extent of contextual memory required. "
        "If the query can be completed in a few steps with minimal context, return 'short'. "
        "For tasks that require a moderate amount of contextual memory and processing, return 'medium'. "
        "For complex, multi-step queries necessitating extensive long-term contextual memory, return 'long'. "
        "For highly intricate queries, such as writing an entire novel or solving problems with multiple interdependent variables, return 'super long'.",
    )  # short range query, or multiple step range like writing a very long novel
    field: str = Field(
        default="",
        description="classify the problem within a relevant academic field such as Mathematics, Physics, Chemistry, Biology, Computer Science, Linguistics, Sociology, or Psychology. ",
    )
    subfield: str = Field(
        default="",
        description="Further refine the classification by identifying the appropriate subfield, such as Mathematical Analysis, Quantum Mechanics, Organic Chemistry, Molecular Biology, Artificial Intelligence, Semantics, or Social Psychology. ",
    )


class QuestionAndAnswer(BaseModel):
    answer: str = Field(
        default="",
        description="the answer to the question",
    )


class EnsembleLogic(BaseModel):
    name: str = Field(default="sc", description="the name of the ensemble logic")

    description: str = Field(
        default="",
        description="describe how to carry out the ensemble to make sure the answer is correct",
    )


class Plan(BaseModel):
    task_id: str = Field(
        default="some id",
        description="unique identifier for a task in plan, can be an ordinal",
    )
    dependent_task_ids: List[str] = Field(
        default_factory=list,
        description="ids of tasks prerequisite to this task",
    )
    instruction: str = Field(
        default="some instruction",
        description="what you should do in this task, one short phrase or sentence",
    )
    task_type: str = Field(
        default="some task type",
        description="type of this task",
    )
    task_params: str = Field(
        default="{}",
        description="a json dictionary of task parameters and values",
    )


@register_route_downstream
class CotMinion(Minion):
    """Chain of Thought (CoT) Strategy, Ask the LLM to think step-by-step, explaining each part of the problem to enhance the accuracy of the answer. Please noted you can't access web or user's local computer, so if you need information from the web or from user's local computer, DON'T USE THIS STRATEGY."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "let's think step by step to solve this problem"

    async def execute(self):
        node = ActionNode(key="answer", expected_type=str, instruction="let's think step by step", example="")
        node = await node.fill(
            context=(COT_PROBLEM_INSTRUCTION + ASK_PROMPT).format(input=self.input), llm=self.brain.llm, schema="raw"
        )
        self.answer_node = node
        self.answer = self.input.answer = extract_final_answer(node.content)

        for _ in range(3):  # try using llm 3 times to extract answer
            if not self.answer:
                # try using llm to extract answer
                node = ActionNode(
                    key="answer", expected_type=str, instruction="extract final answer from result", example=""
                )
                node = await node.fill(context=node.content, llm=self.brain.llm, schema="json")
                self.answer = self.input.answer = node.instruct_content.answer
            else:
                break
        self.raw_answer = self.input.raw_answer = node.content
        return self.answer  # maybe also adds score?


@register_route_downstream
class DotMinion(Minion):
    """Diagram of Thought (DoT) Strategy"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "let's think step by step to solve this problem"

    async def execute(self):
        node = ActionNode(key="answer", expected_type=str, instruction="let's think step by step", example="")
        prompt = Template(DOT_PROMPT)
        prompt = prompt.render(input=self.input)
        node = await node.fill(context=prompt, llm=self.brain.llm, schema="raw")
        self.answer_node = node
        self.answer = self.input.answer = extract_final_answer(node.content)

        for _ in range(3):  # try using llm 3 times to extract answer
            if not self.answer:
                # try using llm to extract answer
                node = ActionNode(
                    key="answer", expected_type=str, instruction="extract final answer from result", example=""
                )
                node = await node.fill(context=node.content, llm=self.brain.llm, schema="json")
                self.answer = self.input.answer = node.instruct_content.answer
            else:
                break
        self.raw_answer = self.input.raw_answer = node.content
        return self.answer  # maybe also adds score?


@register_route_downstream
class MultiPlanMinion(Minion):
    "This Strategy will first generate multiple plan, and then compare each plan, see which one is more promising to produce good result, first try most promising plan, then to less promising plan."
    pass


@register_route_downstream
class PlanMinion(Minion):
    "Divide and Conquer Strategy, Divide the problem into smaller subproblems, solve each subproblem independently, and then merge the results for the final solution."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_prompt = PLAN_PROMPT

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

    async def execute(self):
        # log_dir = METAGPT_ROOT / "logs" / "plan"
        #
        # # Create the directory, including any necessary parent directories
        # log_dir.mkdir(parents=True, exist_ok=True)
        # filename = log_dir / f"json_plan_{self.id}.json"

        self.plan = await self.get_plan_with_retry(cache_filename=self.input.cache_plan)

        # save_json_to_file(self.plan, filename)

        self.task_graph = convert_tasks_to_graph(self.plan)
        # plot_graph(self.task_graph)
        await self.execute_tasks_in_order(self.task_graph)
        return self.answer

    async def execute_tasks_in_order(self, graph):
        # Perform topological sorting
        sorted_tasks = list(nx.topological_sort(graph))

        for task_id in sorted_tasks:
            # Execute the task (replace this with your actual task execution logic)
            for task in self.plan:
                if task["task_id"] == task_id:
                    task_minion = TaskMinion(brain=self.brain, input=self.input, task=task)
                    result = await task_minion.execute()
                    self.input.symbols[task["output_key"]] = Symbol(
                        result, task["output_type"], task["output_description"]
                    )
        self.answer = self.input.answer = result
        return self.answer


@register_route_downstream
class MathPlanMinion(PlanMinion):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_prompt = MATH_PLAN_PROMPT


class TaskMinion(Minion):
    def __init__(self, task=None, **kwargs):
        super().__init__(**kwargs)
        self.input.task = task
        self.task = task

    async def choose_minion_and_run(self):
        choose_template = Template(TASK_ROUTE_PROMPT)

        # filter out smart, since we don't want choose smart following smart again
        # also filter out ScoreMinion

        filtered_registry = {key: value for key, value in MINION_ROUTE_DOWNSTREAM.items()}
        filled_template = choose_template.render(minions=filtered_registry, input=self.input, task=self.task)

        # if self.input.route:
        #     return filtered_registry[self.input.route]

        meta_plan = await ActionNode.from_pydantic(MetaPlan).fill(context=filled_template, llm=self.brain.llm)

        name = meta_plan.instruct_content.name

        name = most_similar_minion(name, filtered_registry.keys())
        klass = filtered_registry[name]
        minion = klass(input=self.input, brain=self.brain, task=self.task, task_execution=True)
        result = await minion.execute()
        self.answer = self.task["answer"] = result
        self.input.symbols[self.task["output_key"]] = result
        print("#####OUTPUT#####")
        print(f"{self.task['output_key']}:{result}")

        return result

    async def execute(self):
        return await self.choose_minion_and_run()


@register_route_downstream
class PythonMinion(Minion):
    "This problem requires writing code to solve it, write python code to solve it"

    # """This problem is a simple math problem, can write code to solve it.
    # Then directly use python stragety to solve it, return python, don't return math.
    # Or this problem requires writing code to solve it, write python code to solve it
    # """

    async def execute(self):
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

            node = await node.fill(
                context=prompt,
                llm=self.brain.llm,
            )
            code = node.instruct_content.code
            print(code)

            def extract_code(text):
                # Regex pattern to extract code inside ```python ``` blocks
                pattern = r"```python(.*?)```"
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    # Return the extracted code, strip to remove leading/trailing newlines
                    return match.group(1).strip()
                return text

            # deepseek may still put ```python...``` in the returned json
            code = extract_code(code)
            self.answer_code = self.input.solution = code

            self.input.run_id = self.input.run_id or uuid.uuid4()
            result = self.brain.python_env.step(f"<id>{self.input.query_id}/{self.input.run_id}</id>{code}")
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


# class WebMinion(PythonMinion):
#     "This task require access web to get information, write python code to get the information"
#     def __init__(self, question, id=None):
#         super().__init__(question, id)
#         self.question = (
#             "This task require access web to get information, write python code to get the information, question:"
#             + self.question
#         )


@register_route_downstream
class MathMinion(PythonMinion):
    "This is a problem involve math, you need to use math tool to solve it"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "This is a math problem, write python code to solve it"


class CodeProblemMinion(PlanMinion):
    "This is a coding problem which requires stragety thinking to solve it, you will first explore the stragety space then solve it"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input.instruction = "This is a coding problem which requires stragety thinking to solve it, you will first explore the stragety space then solve it"


class ScoreMinion(Minion):
    def __init__(self, **kwargs):
        super(ScoreMinion, self).__init__(**kwargs)
        self.score = None  # clear self.score to avoid loop

    async def execute(self):
        # if self.input.score_func, handles that
        node = ActionNode(key="score", expected_type=float, instruction=SCORE_PROMPT, example="")
        node = await node.fill(
            context=ASK_PROMPT
            + """
                answer:
                {input.answer}
                """.format(
                input=self.input
            ),
            llm=self.brain.llm,
        )
        return node.instruct_content.score


class ModeratorMinion(Minion):
    async def invoke_minion(self, minion_name):
        self.input.run_id = uuid.uuid4()  # a new run id for each run
        self.input.route = minion_name

        route_minion = RouteMinion(input=self.input, brain=self.brain)
        result = await route_minion.execute()
        # if self.input.post_processing == "extract_number_from_string":
        #     result = extract_number_from_string(result)
        self.answer = self.input.answer = result
        return result

    def majority_voting(self, results):
        # Perform majority voting on the results
        counter = Counter(results)
        try:
            most_common_result, count = counter.most_common(1)[0]
            logger.info(f"Ensemble Result: {counter}")
            return most_common_result
        except:
            return None

    async def choose_minion_and_run(self):
        # choose golden ensemble
        # design_ensemble = Template(ENSEMBLE_DESIGN_LOGIC_TEMPLATE)
        # design_ensemble.render(input=self.input)
        identification = IdentifyMinion(input=self.input, brain=self.brain)
        await identification.execute()

        if self.input.ensemble_logic:
            ensemble_logic = self.input.ensemble_logic["ensemble_strategy"]["ensemble_logic"]
            ensemble_minions = self.input.ensemble_logic["ensemble_strategy"]["ensemble_minions"]

            if ensemble_logic["type"] == "majority_voting":
                # calculate majority_count
                total = 0
                for minion in ensemble_minions:
                    count = minion["count"]
                    weight = minion.get("weight", 1)
                    total += count * weight
                majority_count = total // 2 + 1

                results = {}

                for minion in ensemble_minions:
                    minion_name = minion["name"]
                    count = minion["count"]

                    for _ in range(count):
                        raw_answer = await self.invoke_minion(minion_name)

                        if minion.get("post_processing", None) == "extract_number_from_string":
                            result = extract_number_from_string(raw_answer)
                        elif minion.get("post_processing", None) == "extract_math_answer":
                            result = extract_math_answer(raw_answer)
                        else:
                            result = raw_answer

                        weight = minion.get("weight", 1)

                        await self.update_stats(minion_name, result, raw_answer)

                        if True:  # result: todo: consider how to handle result is None case
                            # Update the results dictionary
                            if result in results:
                                results[result] += weight
                            else:
                                results[result] = weight

                            # short circuit logic, check if this result has reached the majority count
                            if (
                                self.input.ensemble_logic["ensemble_strategy"].get("short_circuit", True)
                                and results[result] >= majority_count
                            ):
                                self.answer = self.input.answer = result
                                return result  # Majority found, return it

                # No result reached majority; find the result with the highest weight
                most_weight = max(results.values())
                most_weight_result = max(results, key=results.get)

                if most_weight < majority_count:
                    print(
                        f"Warning: No result reached the majority count,most_weight is {most_weight}, most_weight_result is {most_weight_result}"
                    )

                # Return the result with the highest weight
                self.answer = self.input.answer = most_weight_result
                return self.answer
        else:
            route_minion = RouteMinion(input=self.input, brain=self.brain)
            result = await route_minion.execute()
            # if self.input.post_processing == "extract_number_from_string":
            #     result = extract_number_from_string(result)
            self.answer = self.input.answer = result
            return result

    async def merge_result(self, answer):
        merge_prompt = Template(MERGE_PROMPT)
        filled_merge_prompt = merge_prompt.render(input=self.input, answer=answer)

        node = ActionNode(
            key="answer",
            expected_type=float,
            instruction="merge the result according to question",
            example="",
            schema="raw",
        )
        node = await node.fill(context=filled_merge_prompt, llm=self.brain.llm)
        return extract_final_answer(node.content)

    async def execute(self):
        self.input.query_id = self.input.query_id or uuid.uuid4()
        await self.choose_minion_and_run()

        # clean up python env
        self.brain.cleanup_python_env(input=self.input)
        return self.answer


class IdentifyMinion(Minion):
    async def execute(self):
        prompt = Template(IDENTIFY_PROMPT)
        prompt = prompt.render(input=self.input)

        identification = await ActionNode.from_pydantic(Identification).fill(context=prompt, llm=self.brain.llm)

        self.input.complexity = identification.instruct_content.complexity
        self.input.query_range = identification.instruct_content.query_range
        self.input.difficulty = identification.instruct_content.difficulty
        self.input.field = identification.instruct_content.field
        self.input.subfield = identification.instruct_content.subfield

        qa_minion = QaMinion(input=self.input, brain=self.brain)
        await qa_minion.execute()

        self.answer = "identified the input query"
        return self.answer


class QaMinion(Minion):
    def __init__(self, hops=None, **kwargs):
        super().__init__(hops=hops, **kwargs)
        self.hops = hops

    async def execute(self):
        if self.input.dataset:
            prompt = Template(QA_PROMPT_JINJA)
            prompt = prompt.render(question=f"what's {self.input.dataset}")

            qa = await ActionNode.from_pydantic(QuestionAndAnswer).fill(context=prompt, llm=self.brain.llm)

            self.answer = self.input.dataset_description = qa.instruct_content.answer

            return self.answer


class RouteMinion(Minion):
    async def invoke_minion(self, klass):
        if isinstance(klass, str):
            klass = MINION_ROUTE_DOWNSTREAM.get(klass, CotMinion)
        minion = klass(input=self.input, brain=self.brain)
        self.add_followers(minion)
        await minion.execute()
        self.answer = self.input.answer = minion.answer
        return minion.answer

    async def choose_minion_and_run(self):
        choose_template = Template(SMART_PROMPT_TEMPLATE)

        filtered_registry = {key: value for key, value in MINION_ROUTE_DOWNSTREAM.items()}
        filled_template = choose_template.render(minions=filtered_registry, input=self.input)

        meta_plan = await ActionNode.from_pydantic(MetaPlan).fill(context=filled_template, llm=self.brain.llm)

        if self.input.route:
            name = self.input.route
            logger.info(f"Use enforced route: {self.input.route}")
            klass = filtered_registry[self.input.route]
            minion = klass(input=self.input, brain=self.brain)
        else:
            name = meta_plan.instruct_content.name

            name = most_similar_minion(name, filtered_registry.keys())
            logger.info(f"Choosing Route: {name}")
            klass = filtered_registry[name]
            minion = klass(input=self.input, brain=self.brain)

        result = await self.invoke_minion_and_improve(minion, name, 3)
        return result

    async def invoke_minion_and_improve(self, minion, name, count=3):
        if count:
            result = await minion.execute()
            self.answer = self.input.answer = result
            await self.update_stats(name, result, result)
            check_minion = CheckMinion(input=self.input, brain=self.brain)
            result = await check_minion.execute()
            if not result["correct"]:
                return await self.invoke_minion_and_improve(minion, name, count - 1)
        return self.answer

    async def execute(self):
        self.input.query_id = self.input.query_id or uuid.uuid4()
        self.input.run_id = self.input.run_id or uuid.uuid4()
        await self.choose_minion_and_run()
        return self.answer