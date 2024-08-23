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
from difflib import SequenceMatcher
from typing import List

import networkx as nx
from jinja2 import Template
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_none

from metagpt.actions.action_node import ActionNode
from metagpt.logs import logger
from metagpt.minion.symbol_table import Symbol
from metagpt.minion.task_graph import convert_tasks_to_graph


def extract_json_from_string(text):
    # Regular expression pattern to match content between ```json and ```
    pattern = r"```json\s*([\s\S]*?)\s*```"

    # Search for the pattern in the input text
    match = re.search(pattern, text)

    if match:
        json_content = match.group(1)  # Extract the JSON content
        try:
            # Convert the JSON string to a Python object
            return json.loads(json_content)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON content.") from e
    else:
        raise ValueError("No JSON content found.")


def extract_final_answer(text):
    # Match for <final_answer> tag
    match_tag = re.search(r"<final_answer>\s*(.*?)\s*</final_answer>", text, re.DOTALL)
    if match_tag:
        return match_tag.group(1).strip()

    return None


def extract_number_from_string(price_str):
    if isinstance(price_str, int) or isinstance(price_str, float):
        return price_str

    price_str = price_str or ""
    # Remove commas from the string
    price_str = price_str.replace(",", "")

    try:
        # Regular expression to match all numeric values
        matches = re.findall(r"\d+(?:\.\d+)?", price_str)

        if len(matches) == 1:
            # Only one number found, return it as int or float
            number_str = matches[0]
            return float(number_str) if "." in number_str else int(number_str)
        elif len(matches) > 1:
            # More than one number found, handle accordingly
            logger.warning(f"Multiple numbers found in string: {matches}, str: {price_str}")
            return None
        else:
            return None  # Return None if no number is found
    except Exception as e:
        logger.error("extract_number_from_string failed: " + str(e) + f", str: {price_str}")
        return None  # Return None if there is an error


# Function to find the most similar minion
def most_similar_minion(input_name, minions):
    max_similarity = 0
    best_match = None

    for minion in minions:
        similarity = SequenceMatcher(None, input_name, minion).ratio()
        if similarity > max_similarity:
            max_similarity = similarity
            best_match = minion

    return best_match


class MetaPlan(BaseModel):
    name: str = Field(default="naive", description="The name of stragety.")
    score: float = Field(
        default=0,
        description="estimate score of choosing this stragety of success, 1.0 means perfect match,"
        "if we choose this stragety, we are most likely to solve this problem, 0.0 means a"
        "bad match, if we choose this stragety, we are most likely fail to solve this problem",
    )
    complexity: str = Field(
        default="",
        description="estimate this problem's difficulty, when the problem is simple,only required one or several steps to solve this problem,"
        "return low, when the problem difficulty is medium and require more steps to solve it, return medium,"
        "when the problem seemed quite difficult, generally should involve complex process and careful step planning to solve it,"
        "return high",
    )
    query_range: str = Field(
        default="",
        description="if it's a short range query that only require few steps, few context memory to complete the query, return short, "
        "otherwise multiple step, require long term range attention to store relevant long context memory,"
        "return long",
    )  # short range query, or multiple step range like writing a very long novel
    num_trials: int = Field(
        default=0,
        description="number of trials to try using the strategy to solve this problem, sometimes one strategy may fail, but we retry this strategy"
        "we'll succeed, so need need some number of trials",
    )
    is_finished: bool = Field(
        default=False, description="Whether current question already been answered by current answer"
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


COT_PROBLEM_INSTRUCTION = """
Let's approach this problem by breaking it down into distinct, logical steps. For each step, provide a clear explanation of the reasoning behind it. Consider any underlying assumptions, explore potential alternative approaches, and evaluate the consequences of each decision. Once you have thoroughly analyzed all aspects, synthesize the findings to reach a well-supported conclusion. Finally, ensure that your answer is directly accessible and requires no further interpretation by presenting it clearly and explicitly within the tags <final_answer></final_answer>.
"""
ASK_PROMPT = """context:
{input.short_context}
instruction:
{input.instruction}
query_type:
{input.query_type}
query:
{input.query}
"""

ASK_PROMPT_JINJA = """context:
{{input.short_context}}
instruction:
{{input.instruction}}
query_type:
{{input.query_type}}
query:
{{input.query}}
"""

MERGE_PROMPT = (
    """
Task: Given the following question:
"""
    + ASK_PROMPT_JINJA
    + """
Problem Statement:
The current answers are spread,. However, a single, coherent answer is required.
Current Answer:
{{answer}}

Objective:

Critically evaluate the information from all provided sources.
Identify key elements that directly address the query.
Synthesize these elements into a single, well-structured response.
Ensure the response is comprehensive, accurately reflecting the nuances of the context.
Final Answer:
Produce the final result in <final_answer></final_answer>, ensuring it represents a unified and logically consistent answer to the question.
"""
)

ASK_PROMPT_TASK_COMPLEXITY = """complexity:
{{input.complexity}}
query range:
{{input.query_range}}
"""

CHOOSE_WORKER_MINION_TEMPLATE = (
    """
List:
{% for key,minion in minions.items() %}
1. **ID:** {{ key }}  
   **Description:** 
   "{{ minion.__doc__ }}"
{% endfor %}

Please return strategy name for the question:
Please note, since the strategy name is used as class name, you must ensure the returned strategy name upper or lower case must match *EXACTLY* the name I provided here.

"""
    + ASK_PROMPT_JINJA
)

SMART_PROMPT_TEMPLATE = (
    """You are an advanced language model proficient in answering questions requiring world knowledge but facing challenges with math problems. When you encounter a math problem, you should employ a math strategy or python strategy to ensure a comprehensive and accurate solution.

"""
    + ASK_PROMPT_JINJA
)
ENSEMBLE_DESIGN_LOGIC_TEMPLATE = (
    """You are tasked with designing a robust ensemble logic to dynamically select and combine multiple strategies for solving complex problems. The goal is to create an adaptive system that maximizes the likelihood of success across a variety of scenarios.

Key Considerations:
Strategy Selection:

Complexity: Assess the problem's complexity (low, medium, high) and choose strategies accordingly. For high complexity and long query ranges, prioritize strategies that are designed to handle such challenges.
Query Range: Determine whether the problem requires short-term or long-term focus, and select strategies that align with these needs.
Score: Evaluate each strategy's effectiveness, prioritizing those with higher scores for immediate selection.
Adaptive Trials:

Optimization: Calculate the number of trials needed for each strategy. If a strategy shows potential but has a moderate success rate, increase the number of trials to improve the chances of success.
Trial Adjustment: As the ensemble logic progresses, adjust the number of trials based on real-time performance data.
Ensemble Logic:

Combination of Strategies: Develop an algorithm that effectively combines strategies to balance strengths and weaknesses. For instance, pair a high-score, low-complexity strategy with a strategy designed for high-complexity, long-range tasks to ensure coverage across all aspects of the problem.
Complementary Pairing: Consider how different strategies might complement each other, ensuring that the ensemble covers all possible scenarios.
Iteration and Feedback:

Monitoring Progress: Integrate a feedback loop that continuously monitors whether the problem has been solved (is_finished). If the problem remains unsolved, re-evaluate the current ensemble, adjust the combination of strategies, and optimize the number of trials.
Adaptive Response: Use feedback to dynamically refine the ensemble, making it more efficient and effective over time.

"""
    + ASK_PROMPT_JINJA
    + ASK_PROMPT_TASK_COMPLEXITY
    + """
JSON Output Specifications:
Once you have developed the ensemble logic, provide the final output as a JSON object with the following structure:

```json
{
    "name": "Ensemble Strategy Name",
    "description": "Detailed explanation of how the ensemble logic ensures the correct solution.",
    "params": {
        "selected_strategies": [
            {
                "name": "Strategy 1 Name",
                "score": "Strategy 1 Score",
                "complexity": "low/medium/high",
                "query_range": "short/long",
                "num_trials": "Number of trials for Strategy 1"
            },
            {
                "name": "Strategy 2 Name",
                "score": "Strategy 2 Score",
                "complexity": "low/medium/high",
                "query_range": "short/long",
                "num_trials": "Number of trials for Strategy 2"
            }
        ],
        "combination_logic": "Explanation of how the strategies are combined.",
        "adaptive_trials": "Method used to adjust the number of trials based on strategy performance.",
        "feedback_loop": "Mechanism for monitoring the success of the ensemble and making adjustments."
    }
}
```
This output structure will ensure that the ensemble logic is clearly defined, with each component detailed for clarity and effectiveness. By following this approach, you will create a system capable of tackling a wide range of problems, from simple to highly complex, ensuring the final solution is both robust and accurate.
"""
)
TASK_INPUT = """
Current Task Input:
instruction:
{{task.instruction}}
task type:
{{task.task_type}}
task parameters:
{% for key,minion in task.task_params.items() %}
1. **Name:** {{ key }}  
   **Value:** 
   "{{ minion }}"
{% endfor %}
hint:
{{task.hint}}
dependent key output:
{% for dependent in task.dependent %}
1. key: {{ dependent['dependent_key'] }}  
   key_type : {{dependent['dependent_type']}}
   output value: {{ input.symbols[dependent['dependent_key']].output }}
   output_type: {{ input.symbols[dependent['dependent_key']].output_type }}
   output_description: {{ input.symbols[dependent['dependent_key']].output_description }}
{% endfor %}
**PLEASE USE** dependent key output in your code to reuse result from previous tasks to solve current task at hand**
"""
# TASK_PROMPT = """
# """
TASK_ROUTE_PROMPT = (
    """Given the task's context, instructions, parameters, and provided hints, analyze the situation and evaluate multiple worker strategies. Identify potential outcomes for each strategy and select the most effective approach. Justify your choice by considering both immediate and long-term implications, as well as any trade-offs or risks associated with your decision. Additionally, explore how alternative strategies might alter the task's outcome and what contingencies could be prepared to address unforeseen challenges.
"""
    + CHOOSE_WORKER_MINION_TEMPLATE
    + ASK_PROMPT_JINJA
    + TASK_INPUT
)
PLAN_PROMPT = (
    """You are a strategic planner capable of designing and executing complex plans. When a user presents a task, your first step is to outline how each strategy will be utilized. Then, you implement the strategies to accomplish the task. Below is a list of strategies available to you:

"""
    + ASK_PROMPT_JINJA
    + """ 

Task:

Given the context, create a detailed plan or refine an existing plan to achieve a specified goal. A comprehensive plan should consist of one to {max_tasks} tasks. The following points outline the necessary steps:

    Detailed Task Construction: Each task in the plan must be described clearly and should include specific actions, conditions, and parameters that guide its execution. Avoid generic steps; instead, ensure that each task is actionable and contributes directly to the overall objective.

    Critical Evaluation of Dependencies: When refining or modifying an existing plan, critically analyze dependencies between tasks. If revising a single task, assess how it interacts with previous or subsequent tasks and ensure that it aligns with the overall flow of the plan. Modify only what is necessary, maintaining the integrity of the original structure unless fundamental changes are needed for optimization.

    Error Handling and Adaptation: In case of errors or obstacles in executing a task, revise the specific task to address the issue effectively. The revision should include precise instructions on how to overcome the challenge, minimizing disruption to the plan's progress.

    JSON Output Specifications: Provide the final plan as a list of JSON objects, ensuring each task includes the following attributes:
        task_id: A unique identifier for each task, preferably ordinal or descriptive.
        dependent_task_ids: A list of task IDs that are prerequisites for this task, indicating dependencies.
        instruction: A concise but clear description of the action required for this task.
        task_type: The type or category of the task.
        task_params: A JSON dictionary specifying the task's parameters and their corresponding values.
        output_key: A unique identifier for storing the output of the task, which can be referenced by subsequent tasks.
        output_type:  The type of the output, describe how subsequent task can use this output_key, can be str, number(int or float, fractions(if you require precision)), dict, file, url etc
        output_description:  Description of the output, describe what it is, how it's relevant to whole task, how subsequent task can use it.
        dependent: a list of dependent key produced by previous tasks and required by this task, containing a list of following subkeys:
            dependent_key: A unique identifier of dependent key of the task, produced by previous tasks.
            dependent_type: The type of dependent key, produced by previous tasks and required by this task, specify how this task can use this dependent_key, 
              like str, number(int or float or fractions(if you require precision)) then you can direct use, if file or url then you need to read from the file or url.
        Hint: (Optional) Provide a hint or brief guidance for carrying out the task effectively, particularly if the task involves complexity or potential challenges. This could include tips, best practices, or a brief outline of steps to ensure successful completion.

    Contextual Precision: Return a plan that is as specific and precise as possible. Avoid vague or ambiguous instructions. Ensure that task descriptions and parameters are well-defined to facilitate smooth execution and alignment with the overall goal.

By following these guidelines, ensure the plan is logical, thorough, and well-suited to achieving the desired outcome efficiently.
"""
)

PLAN_PROMPT_BY_CHOOSING = (
    """You are a strategic planner capable of designing and executing complex plans. When a user presents a task, your first step is to outline how each strategy will be utilized. Then, you implement the strategies to accomplish the task. Below is a list of strategies available to you:

Web: Begin by accessing the web to gather necessary information. Subsequently, use this information for further inference and decision-making.
Given the following question, identify the most appropriate strategy to employ. Ensure that the returned strategy name matches EXACTLY in upper or lower case as provided.
also for each strategy, please identify necessary params need to pass, like subquestion etc.

"""
    + CHOOSE_WORKER_MINION_TEMPLATE
)
DIVIDE_PROMPT = """
For the following question and existing answer, determine whether the answer already contains answer to the question without need for furthur processing, Otherwise if it needs furthur processing, This is the List of stragety that you can use:
List:

Naive:Native Strategy, Directly ask the LLM for an answer.
CoT:Chain of Thought (CoT) Strategy, Ask the LLM to think step-by-step, explaining each part of the problem to enhance the accuracy of the answer.
ToT:Tree of Thought (ToT) Strategy, Break the problem down into a tree structure, providing different suboptions for each step. Analyze each suboption, prioritizing the most promising paths. If a path leads to a solution, return that result; if not, backtrace and explore other suboptions.
Ee:Explore and Exploit Strategy, Utilize a memory of previous similar questions to choose the best result based on past metrics or explore new approaches to update the memory with better results if they surpass the original metric.
Math: This is a problem involve math, you need to use math tool to solve it
Python: This problem requires writing code to solve it, write python code to solve it

question:
{question}
Here's currently thought plan, Then return a list of strategy name for the question:
Please note, since the strategy name is used as class name, you must ensure the returned strategy name upper or lower case must match *EXACTLY* the name I provided here.
plan:
{plan}
"""

SCORE_PROMPT = """Given a complex question and its corresponding answer, analyze the answer to determine its correctness. Break down the analysis into the following steps:

1. Identify the key elements of the question.
2. Evaluate if the provided answer addresses each key element accurately.
3. Check for logical consistency and the presence of supporting evidence in the answer.
4. Consider alternative perspectives and if the answer sufficiently accounts for them.
5. Synthesize your findings to determine the overall correctness of the answer.
6. Assign a confidence score for the correctness of the answer, with 1.0 being completely correct and 0.0 being completely incorrect. Only output the score value.

"""

FINISH_PROMPT = (
    """
[Input Prompt] for the following question and existing answer, determine whether the answer already contains answer to the question without need for furthur processing, Otherwise if it needs furthur processing, This is the List of stragety that you can use:
"""
    + ASK_PROMPT
)
COMMON_ERROR = """
please remember I may have not some package installed, like sympy or numpy, so please add in the code like
```python
import os
os.system('python -m pip install sympy')
os.system('python -m pip install numpy')
```
"""
COMMON_SYMPY_ERROR = """
When using SymPy's solve function to address systems of equations, the default behavior is to return a list of solutions, typically as a list of expressions. However, when the goal is to represent each solution as a mapping of variables to their corresponding values, the dict=True parameter should be included. This alters the output to a list of dictionaries, where each dictionary contains key-value pairs corresponding to the variables and their respective solutions.

Consider a scenario where you are solving a system of equations, such as (equation1,equation2)(equation1,equation2), with respect to variables xx and yy. By using solve(equation1, equation2), (x, y), dict=True), the function will return a list of dictionaries, each representing a unique solution.

Now, critically analyze the implications of using the dict=True parameter when dealing with complex systems of equations that involve multiple variables. Consider the following aspects:

    Clarity in Solution Interpretation: How does the use of dictionaries enhance or hinder the understanding of the solution set, especially when dealing with a large number of variables? Discuss the advantages and potential drawbacks of this approach in interpreting the solutions.

    Impact on Systems with Multiple or No Solutions: Evaluate how the output format changes when the system has an infinite number of solutions or no solutions at all. What specific patterns or anomalies might you observe in the list of dictionaries in these cases? How does this format help in identifying whether the system is underdetermined (infinite solutions) or inconsistent (no solutions)?

    Strategies for Solution Validation: When the system yields multiple solutions, what strategies can be employed to effectively validate and interpret these solutions? Consider the role of additional constraints, such as requiring variables to be real, positive, integer, or natural numbers (using real=True, positive=True, etc., in the symbol declarations,
    like ```x, y = symbols('x y', real=True, positive=True)```). How do these constraints refine the solution set, and what should be your approach when multiple valid solutions exist?

    make sure symbols() constructor really contains real variables(symbols), DON'T put non-symbol like 'cos(theta)', 'sin(theta)' etc in symbols().
    
    some functions you may find useful:
    
    from sympy import S
    
    sympy.calculus.util.maximum(f, symbol, domain=S.Reals)
    Returns the maximum value of a function in the given domain of Reals.
    
    sympy.calculus.util.minimum(f, symbol, domain=S.Reals)
    Returns the minimum value of a function in the given domain of Reals.
    
    sympy.calculus.util.maximum(f, symbol, domain=S.Complexes)
    Returns the maximum value of a function in the given domain of Complexes.
    
    sympy.calculus.util.minimum(f, symbol, domain=S.Complexes)
    Returns the minimum value of a function in the given domain of Complexes.

    Please remember to add result = sympy.simplify(result) to simplify the expression before return
    
    Handling Complex Systems: Reflect on the practical application of these strategies in solving real-world problems. How can the dict=True approach assist in managing and interpreting the solutions to more intricate systems, especially when some solutions might not be immediately obvious or when certain solutions need to be excluded based on problem-specific criteria?

Finally, after solving the equations, ensure that any additional constraints or context-specific conditions are thoroughly considered. Discuss how examining each solution against these constraints can help in determining the most appropriate solution(s) for the given problem.
"""
PYTHON_PROMPT = (
    """
Write python code to solve the problem, also noted the python program must return a string print out answer and only answer,"""
    + COMMON_ERROR
    + COMMON_SYMPY_ERROR
    + """Please ensure all the variables are defined, don't use variables before defining them
                please ensure you correctly indent the code, and don't use // as comment
                """
)


def extract_content(text):
    pattern = r"\[CONTENT\](.*?)\[/CONTENT\]"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def snake_case_to_camel_case(snake_str: str, suffix: str = "Minion") -> str:
    # Split the snake case string by underscores and capitalize each word
    components = snake_str.split("_")
    # Capitalize each component and join them
    camel_case_str = "".join(x.capitalize() for x in components)
    # Add the suffix
    camel_case_with_suffix = camel_case_str + suffix
    return camel_case_with_suffix


def camel_case_to_snake_case(camel_str: str, suffix: str = "Minion") -> str:
    # Remove the suffix
    if camel_str.endswith(suffix):
        camel_str = camel_str[: -len(suffix)]

    # Find all places where a lowercase letter is followed by an uppercase letter
    snake_case_str = re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str).lower()
    return snake_case_str


# a dummy score that does nothing, always return 1 to shortcut the score process
class NoneScore:
    def __call__(self, **kwargs):
        return 1


class SubclassHookMeta(type):
    def __init__(cls, name, bases, clsdict):
        super().__init__(name, bases, clsdict)
        cls._subclassed_hook()


MINION_REGISTRY = {}
MINION_ROUTE_DOWNSTREAM = {}


def register_route_downstream(cls):
    # Register the class in the dictionary with its name as the key
    MINION_ROUTE_DOWNSTREAM[camel_case_to_snake_case(cls.__name__)] = cls
    return cls


class Minion(metaclass=SubclassHookMeta):
    def __init__(self, input=None, brain=None, id=None, score_func=None, task=None, task_execution=False):
        if brain is None:
            raise ValueError("The 'brain' parameter cannot be None.")

        self.id = id or uuid.uuid4()

        self.input = input
        self.brain = brain
        self.followers = []
        self.score_func = score_func
        self.task = task
        self.task_execution = task_execution

    def propagate_information(self, other):
        other.input = self.input
        other.brain = self.brain

    async def score(self):
        # if self.score_func is not None:
        #     return self.score_func(self)
        minion = ScoreMinion(input=self.input, brain=self.brain)
        return await minion.execute()

    @classmethod
    def _subclassed_hook(cls):
        if cls.__name__ != "Minion":
            MINION_REGISTRY[camel_case_to_snake_case(cls.__name__)] = cls
        # print(f"{cls.__name__} has been subclassed")

    def add_followers(self, follower):
        self.followers.append(follower)

    def __hash__(self):
        # Use a tuple of attributes to compute the hash value
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id
        return False

    def __repr__(self):
        return f"Minion({self.id})"

    async def is_finished(self):
        # check whether self is finished
        meta_planner = await ActionNode.from_pydantic(MetaPlan).fill(
            context=FINISH_PROMPT.format(input=self.input), llm=self.brain.llm
        )

        is_finished = meta_planner.instruct_content.is_finished
        return is_finished

    @property
    def clean_answer(self):
        answer = extract_content(self.answer_node.content)
        return answer

    async def execute(self):
        node = ActionNode(key="answer", expected_type=str, instruction="let's think step by step", example="")
        node = await node.fill(context=ASK_PROMPT.format(input=self.input), llm=self.brain.llm)
        self.answer_node = node
        self.answer = self.input.answer = node.instruct_content.answer
        return self.answer  # maybe also adds score?


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
        self.answer_raw = self.input.answer_raw = node.content
        return self.answer  # maybe also adds score?


@register_route_downstream
class MultiPlanMinion(Minion):
    "This Strategy will first generate multiple plan, and then compare each plan, see which one is more promising to produce good result, first try most promising plan, then to less promising plan."
    pass


@register_route_downstream
class PlanMinion(Minion):
    "Divide and Conquer Strategy, Divide the problem into smaller subproblems, solve each subproblem independently, and then merge the results for the final solution."

    def write_json_to_cache(self, file, data):
        # Ensure that the data is serializable to JSON
        try:
            with open(file, "w") as file:
                json.dump(data, file, indent=4)  # Write the JSON data to the file with indentation for readability
            print(f"Data successfully written to {self.input.cache_plan}")
        except (TypeError, IOError) as e:
            print(f"An error occurred: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_none())  # Retries up to 3 times with a 2-second wait between attempts
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

        choose_template = Template(PLAN_PROMPT)

        # filter out smart, since we don't want to choose smart following smart again
        # also filter out ScoreMinion
        filtered_registry = {
            key: value
            for key, value in MINION_REGISTRY.items()
            if key != "smart" and key != "score" and key != "plan" and key != "multi_plan"
        }
        filled_template = choose_template.render(minions=filtered_registry, input=self.input)

        plan = await ActionNode.from_pydantic(Plan).fill(context=filled_template, llm=self.brain.llm, schema="raw")

        json = extract_json_from_string(plan.content)
        self.write_json_to_cache(self.input.cache_plan, json)

        return json

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
        self.answer = self.input.answer = "task completed"

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
        self.num_trials = meta_plan.instruct_content.num_trials
        if self.num_trials < 1 or not isinstance(self.num_trials, int):
            self.num_trials = 1

        name = meta_plan.instruct_content.name

        # do we need task route?
        # if self.input.route:
        #    klass = filtered_registry[self.input.route]
        # else:
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
            self.answer_code = code
            print(self.answer_code)

            result = self.brain.python_env.step(code)
            obs = result[0]  # obs

            if obs["error"]:
                error = obs["error"]
                logger.error(error)
                continue  # try again?
            output, error = obs["output"], obs["error"]
            self.answer = self.input.answer = output
            # print("#####OUTPUT#####")
            # print(output)
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
    async def invoke_minion(self, klass):
        if isinstance(klass, str):
            klass = MINION_ROUTE_DOWNSTREAM.get(klass, CotMinion)
        minion = klass(input=self.input, brain=self.brain)
        self.add_followers(minion)
        await minion.execute()
        self.answer = self.input.answer = minion.answer
        return minion.answer

    def majority_voting(self, results):
        # Perform majority voting on the results
        counter = Counter(results)
        try:
            most_common_result, _ = counter.most_common(1)[0]
            return most_common_result
        except:
            return None

    async def choose_minion_and_run(self):
        design_ensemble = Template(ENSEMBLE_DESIGN_LOGIC_TEMPLATE)
        design_ensemble.render(input=self.input)

        if self.input.ensemble_logic:
            ensemble_logic = self.input.ensemble_logic["ensemble_strategy"]["ensemble_logic"]
            ensemble_minions = self.input.ensemble_logic["ensemble_strategy"]["ensemble_minions"]

            if ensemble_logic == "majority_voting":
                results = []
                for minion in ensemble_minions:
                    minion_name = minion["name"]
                    count = minion["count"]
                    for _ in range(count):  # skip route
                        result = await self.invoke_minion(minion_name)
                        if minion.get("post_processing", None) == "extract_number_from_string":
                            result = extract_number_from_string(result)
                        if result:
                            results.append(result)

                # Perform majority voting on the collected results
                final_result = self.majority_voting(results)
                self.answer = self.input.answer = final_result
                return final_result
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
        await self.choose_minion_and_run()
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

    def majority_voting(self, results):
        # Perform majority voting on the results
        counter = Counter(results)
        try:
            most_common_result, _ = counter.most_common(1)[0]
            return most_common_result
        except:
            return None

    async def choose_minion_and_run(self):
        choose_template = Template(SMART_PROMPT_TEMPLATE)

        filtered_registry = {key: value for key, value in MINION_ROUTE_DOWNSTREAM.items()}
        filled_template = choose_template.render(minions=filtered_registry, input=self.input)

        meta_plan = await ActionNode.from_pydantic(MetaPlan).fill(context=filled_template, llm=self.brain.llm)

        if self.input.route:
            logger.info(f"Use enforced route: {self.input.route}")
            klass = filtered_registry[self.input.route]
            minion = klass(input=self.input, brain=self.brain)
        else:
            name = meta_plan.instruct_content.name

            name = most_similar_minion(name, filtered_registry.keys())
            klass = filtered_registry[name]
            minion = klass(input=self.input, brain=self.brain)
        result = await minion.execute()
        self.answer = self.input.answer = result
        return result

    async def execute(self):
        await self.choose_minion_and_run()
        return self.answer
