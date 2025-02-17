NATIVE_PROBLEM_INSTRUCTION = """
respond to the following query within the tags <final_answer></final_answer>.
"""
COT_PROBLEM_INSTRUCTION = """
Let's approach this problem by systematically breaking it down into distinct, logical steps. For each step, provide a clear explanation of the reasoning behind it, considering any underlying assumptions, potential biases, and alternative approaches. Explore how different assumptions or methodologies might lead to varying outcomes and critically assess the consequences of each decision. Additionally, consider the broader implications of these decisions within the context of the problem. Once all aspects have been thoroughly analyzed, synthesize the findings to reach a well-supported conclusion. Clearly express your final conclusion, ensuring that it is directly accessible and requires no further interpretation by presenting it explicitly within the tags <final_answer></final_answer>. Finally, include a verbalized confidence level for your conclusion (e.g., "Confidence: 60% / Medium") to convey your level of certainty in the analysis and decision-making process.
"""

ASK_PROMPT_JINJA = """
Current Problem:
{%- if input.short_context %}
context:
{{input.short_context}}
{%- endif %}
{%- if input.instruction %}
instruction:
{{input.instruction}}
{%- endif %}
{%- if input.query_type %}
query_type:
{{input.query_type}}
{%- endif %}

query:
{{input.query}}
"""
ASK_ADDITIONAL_INFO_JINJA = """
{%- if input.info %}
{% for key, value in input.info.items() %}
{{ key }}: {{ value }}
{% endfor %}
{% endif %}
"""
ASK_PROMPT_META_JINJA = """
complexity:
{{input.complexity}}
query_range:
{{input.query_range}}
field:
{{input.field}}
subfield:
{{input.subfield}}
dataset:
{{input.dataset}}
dataset_description:
{{input.dataset_description}}
"""

# New template for worker minions that need access to info
WORKER_PROMPT = (
    ASK_PROMPT_JINJA
    + ASK_ADDITIONAL_INFO_JINJA
    
)

MERGE_PROMPT = (
    """
    Task: Given the following question:
    """
    + ASK_PROMPT_JINJA
    + ASK_ADDITIONAL_INFO_JINJA
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
    + ASK_ADDITIONAL_INFO_JINJA
    + ASK_PROMPT_META_JINJA
)
IDENTIFY_PROMPT = (
    """
    Given a specific problem, start by identifying and assessing both its complexity (low, medium, high) and its difficulty (high school, undergraduate, graduate, Olympiad). The complexity addresses the overall intricacy of the problem, while the difficulty considers the challenge relative to different educational stages.
    
    Based on this dual assessment, select strategies that are most effective for addressing the problem's complexity and difficulty, particularly for those requiring handling intricate challenges over extended range (short-term or long-term). Next, determine whether the problem demands a short-term or long-term focus and choose strategies best suited to these temporal requirements.
    
    Afterward, classify the problem within a relevant field such as Mathematics, Physics, Chemistry, Biology, Computer Science, Linguistics, Sociology, or Psychology. Further refine the classification by identifying the appropriate subfield such as Mathematical Analysis, Quantum Mechanics, Organic Chemistry, Molecular Biology, Artificial Intelligence, Semantics, or Social Psychology.
    
    Finally, consider how the problem's complexity, difficulty, and range may influence the selection of strategies within the chosen field and subfield. Explore potential interdisciplinary approaches that could enhance problem-solving effectiveness, especially where integrating knowledge from various domains could provide innovative solutions.
    """
    + ASK_PROMPT_JINJA
)

QA_PROMPT_JINJA = """
Question:
{{question}}
"""

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
    + ASK_PROMPT_META_JINJA
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
task description:
{{task_description}}
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
    + ASK_PROMPT_META_JINJA
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

    JSON Output Specifications: Provide the final plan as a list of JSON objects, ensuring each task includes the following attributes,
    Output a list of jsons following the format:
    ```json
        [
    {
        "task_id": "unique identifier for a task in plan, can be an ordinal",
        "dependent_task_ids": ["ids of tasks prerequisite to this task"],
        "instruction": "what you should do in this task, one short phrase or sentence",
        "task_type": "type of this task, should be one of Available Task Types",
        "task_description": "A detailed description of the task, including what the task entails, the specific steps to perform it, and how to approach it. Describe how the task should utilize the outputs from the prerequisite tasks (listed in dependent_task_ids), and how its own output will be structured and used in subsequent tasks.",
        "output_key": "unique identifier for storing the output of the task",
        "output_type": "type of the output, e.g., str, number, file, url, etc.",
        "output_description": "description of the output, its relevance, and usage in subsequent tasks",
        "output_example": "example of the output and how it can be used by subsequent tasks",
        "dependent": [
            {
                "dependent_key": "unique identifier of the dependent key produced by previous tasks",
                "dependent_type": "type of dependent key, specify how this task can use this dependent_key"
            }
        ],
        "hint": "optional guidance or tips for completing the task effectively"
    },
    ...
]
```


    Contextual Precision: Return a plan that is as specific and precise as possible. Avoid vague or ambiguous instructions. Ensure that task descriptions and parameters are well-defined to facilitate smooth execution and alignment with the overall goal.

Ensure the plan is concise, with each step being essential and logically connected, leading seamlessly from one task to the next for efficient achievement of the desired outcome. Please do not include any "check solution" tasks, as I will provide those later.
"""
)
MATH_PLAN_PROMPT = (
    """
        You are an expert in mathematical problem-solving, capable of developing and executing detailed solution strategies for complex math problems. When a user presents a math problem, your first step is to outline the problem-solving approach by breaking down the problem into manageable steps. Then, you implement these steps to derive the solution. Below is a list of steps to guide you in constructing a robust mathematical solution plan:
    
    Math Problem:
    
    Given the mathematical context, create a detailed solution plan or refine an existing approach to solve the specified problem. The comprehensive plan should consist of one to {max_steps} steps. The following points outline the necessary components:
    
    Detailed Problem Breakdown: Each step in the solution plan must be described with clarity, including the specific mathematical operations, theorems, or algorithms to be applied. Avoid generic descriptions; instead, ensure that each step is actionable and directly contributes to finding the solution. Explain the reasoning behind each step and how it progresses towards the final answer.
    
    Critical Analysis of Dependencies: When refining or modifying an existing solution approach, critically analyze the dependencies between steps. If revising a particular step, assess how it interacts with preceding or subsequent steps, ensuring alignment with the overall logical flow. Modify only what is necessary, maintaining the integrity of the original method unless fundamental changes are required for optimization.
    
    Error Handling and Strategy Adaptation: In case of errors or difficulties during a step, revise the approach to address the issue effectively. The revision should include precise instructions on how to adjust the method, whether by choosing an alternative mathematical technique or reconsidering the initial assumptions, minimizing disruption to the solution process.
    
    Mathematical Output Specifications: Provide the final solution plan as a series of JSON objects, ensuring each step includes the following attributes:
    JSON Output Specifications: Provide the final plan as a list of JSON objects, ensuring each task includes the following attributes,
        Output a list of jsons following the format:
        ```json
            [
        {
            "task_id": "unique identifier for a task in plan, can be an ordinal",
            "dependent_task_ids": ["ids of tasks prerequisite to this task"],
            "instruction": "what you should do in this task, one short phrase or sentence",
            "task_type": "type of this task, should be one of Available Task Types",
            "task_description": "A detailed description of the task, including what the task entails, the specific steps to perform it, and how to approach it. Describe how the task should utilize the outputs from the prerequisite tasks (listed in dependent_task_ids), and how its own output will be structured and used in subsequent tasks.",
            "output_key": "unique identifier for storing the output of the task",
            "output_type": "type of the output, e.g., str, number, file, url, etc.",
            "output_description": "description of the output, its relevance, and usage in subsequent tasks",
            "output_example": "example of the output and how it can be used by subsequent tasks",
            "dependent": [
                {
                    "dependent_key": "unique identifier of the dependent key produced by previous tasks",
                    "dependent_type": "type of dependent key, specify how this task can use this dependent_key"
                }
            ],
            "hint": "optional guidance or tips for completing the task effectively"
        },
        ...
    ]
    ```
    
    Note: *PLEASE CORRECT* escape the json, say \(z\) is incorrect, you must say \\(z\\).
    
    Contextual Precision: Ensure the solution plan is as specific and precise as possible. Avoid vague or ambiguous instructions. Ensure that each step and its parameters are well-defined to facilitate smooth execution and alignment with the overall solution.
    
    Ensure the plan is concise, with each step being essential and logically connected, leading seamlessly from one task to the next for efficient achievement of the desired outcome. Please do not include any "check solution" tasks, as I will provide those later.
        """
    + ASK_PROMPT_JINJA
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

    some functions for find extreme value you may find useful:

    from sympy import S

    sympy.calculus.util.maximum(f, symbol, domain=S.Reals)
    Returns the maximum value of a function in the given domain of Reals.

    sympy.calculus.util.minimum(f, symbol, domain=S.Reals)
    Returns the minimum value of a function in the given domain of Reals.

    when finding extreme value(maximum/minimum), better find it on the domain of S.Reals,
    because it's harder to find maximum/minimum on complexes without constraint,
    convert the extreme value finding problem to only rely on parameters of S.Reals.

    Please remember to add result = sympy.simplify(result) to simplify the expression before return

    Handling Complex Systems: Reflect on the practical application of these strategies in solving real-world problems. How can the dict=True approach assist in managing and interpreting the solutions to more intricate systems, especially when some solutions might not be immediately obvious or when certain solutions need to be excluded based on problem-specific criteria?

Finally, after solving the equations, ensure that any additional constraints or context-specific conditions are thoroughly considered. Discuss how examining each solution against these constraints can help in determining the most appropriate solution(s) for the given problem.
"""
PYTHON_PROMPT = (
    """
    Write python code to solve the problem, also noted the python program must print out answer"""
    + COMMON_ERROR
    + COMMON_SYMPY_ERROR
    + """Please ensure all the variables are defined, don't use variables before defining them
                please ensure you correctly indent the code, and don't use // as comment
                """
)
#try not to use sympy
PYTHON_PROMPT = (
    """
    Write python code to solve the problem, also noted the python program must print out answer"""
    #+ COMMON_ERROR
    #+ COMMON_SYMPY_ERROR
    + """Please ensure all the variables are defined, don't use variables before defining them
                please ensure you correctly indent the code, and don't use // as comment
                """
)
EXISTING_ANSWER_PROMPT = """
{% if input.full_output %}
Full Output:
{{ input.full_output }}
{% endif %}

{% if input.answer_code %}
Answer Code:
{{ input.answer_code }}
{% endif %}

Answer:
{% if input.answer is mapping %}
{% for key, value in input.answer.items() %}
{{ key }}:
{% if value is string %}
{{ value }}
{% elif value is sequence and value is not string %}
{% for item in value %}
- {{ item }}
{% endfor %}
{% else %}
{{ value }}
{% endif %}
{% endfor %}
{% else %}
{{ input.answer }}
{% endif %}
"""
CHECK_PROMPT = f"""Given the following problem details:

{ASK_PROMPT_JINJA}
{ASK_ADDITIONAL_INFO_JINJA}

{EXISTING_ANSWER_PROMPT}

Critically assess the answer against the problem requirements. Does it follow the instructions, match the query type, and address the context effectively? Evaluate the correctness and relevance of the answer, highlighting any logical inconsistencies, gaps, or errors. Suggest improvements or alternative approaches if necessary, ensuring a thorough analysis.

Your feedback should be structured as follows:
<root>
    <feedback>
    Provide a detailed assessment of the answer here, focusing on alignment with the problem's requirements, clarity, accuracy, and any suggested improvements.
    </feedback>
    <correct>true/false</correct>
    <score>1 for a correct/perfect match, 0 for an incorrect/mismatch, or a fractional score for partial correctness.</score>
</root>

"""

#another check prompt, maybe this one is better?
CHECK_PROMPT1 = f"""Given the following problem details:

{ASK_PROMPT_JINJA}
{ASK_ADDITIONAL_INFO_JINJA}

{EXISTING_ANSWER_PROMPT}

Given the complete solution process and final answer above, evaluate:

1. Process Validation:
- Are the thinking steps logical and complete?
- Are mathematical derivations correct?
- Are units handled properly?
- Is step counting accurate?

2. Answer Validation:
- Does the final answer follow from the steps?
- Is it numerically correct?
- Are units correct?

Your feedback should be structured as:
<root>
    <process_check>
        Evaluate the solution process
    </process_check>
    <answer_check>
        Evaluate the final answer
    </answer_check>
    <correct>true/false</correct>
    <score>score value</score>
</root>

"""

DOT_PROMPT = (
    """
# Diagram of Thought Iterative Reasoning Prompt

You are an AI language model employing iterative reasoning through three distinct roles, each encapsulated within specific XML tags:

- `<proposer>...</proposer>`
- `<critic>...</critic>`
- `<summarizer>...</summarizer>`

## Roles and Responsibilities

### \<proposer\>

- **Objective**: Propose one or more reasoning steps towards solving the given problem.
- **Instructions**:
  - Generate clear and concise propositions that advance the reasoning process.
  - Build upon previous valid propositions and consider any critiques provided.
- **Output Format**: Enclose your reasoning within `<proposer>` tags.

### \<critic\>

- **Objective**: Critically evaluate the proposer's reasoning steps.
- **Instructions**:
  - Analyze the propositions for logical consistency and accuracy.
  - Provide detailed natural language critiques highlighting any errors or areas for improvement.
- **Output Format**: Enclose your critiques within `<critic>` tags.

### \<summarizer\>

- **Objective**: Synthesize the validated propositions into a coherent chain-of-thought leading to the final solution.
- **Instructions**:
  - Review the DAG of propositions and critiques.
  - Extract and organize the valid reasoning steps.
  - Determine if the reasoning is complete and present the final answer if so.
- **Output Format**: Enclose your summary within `<summarizer>` tags.

## Process Flow

1. **Iteration Begins**: The `<proposer>` presents one or more reasoning steps.
2. **Critical Evaluation**: The `<critic>` analyzes these steps, providing natural language critiques and suggesting refinements.
3. **Assessment and Synthesis**: The `<summarizer>` reviews the validated propositions and critiques to determine if the final answer can be reached.
4. **Repeat**: This cycle continues, with the `<proposer>` refining or adding propositions based on the `<critic>`'s feedback, until the `<summarizer>` confirms that the reasoning is complete.

## Formatting Guidelines

- **Clarity**: Ensure each reasoning step and critique is easy to understand.
- **Logical Progression**: Each proposition should logically follow from previous ones, considering any critiques.
- **Tags**: Always encapsulate your output within the correct XML tags.
- **Natural Language**: Use detailed explanations in critiques to provide meaningful feedback.

## Example Interaction

```xml
<proposer>
[Proposer's reasoning step 1]
</proposer>
<critic>
[Critic's detailed natural language critique 1]
</critic>
<proposer>
[Proposer's reasoning step 2]
</proposer>
<critic>
[Critic's detailed natural language critique 2]
</critic>
<summarizer>
[Summarizer's synthesis and assessment]
</summarizer>
```
"""
    + ASK_PROMPT_JINJA
)

# adapted from https://x.com/_philschmid/status/1842846050320544016
DCOT_PROMPT = (
    """
You are an AI assistant designed to solve complex problems by dynamically reasoning through multiple perspectives, employing reflection, and adapting your approach as new information emerges. Your task is to solve the problem step by step, incorporating deep reasoning, critical reflection, and strategic adjustments throughout the process.

Thinking and Perspective Exploration:

Enclose all thoughts within <thinking> tags. Examine the problem from multiple angles, exploring alternative approaches and considering possible solutions or errors.
Be open to unconventional thinking, challenging assumptions, and exploring edge cases or rare conditions.
Step-by-Step Breakdown:

Use <step> tags to break down the solution into clear, logical steps. Start with a 50-step budget, requesting more if the problem demands additional complexity.
After each step, indicate the remaining budget with <count> tags and evaluate whether the approach is on track. Adjust if needed.
Reflection and Progress Evaluation:

After every 3 steps, perform a detailed self-reflection using <reflection> tags. Critically assess your progress, and consider potential biases, assumptions, and alternative viewpoints.
Assign a reward score between 0.0 and 1.0 after each reflection, using the following criteria:
0.8+: Continue the current approach.
0.5-0.7: Consider minor adjustments or refinements.
Below 0.5: Reevaluate the approach and consider backtracking or starting fresh with an alternate strategy.
Dynamic Reasoning Adjustments:

If a low reward score is assigned, justify backtracking or changing your approach within <thinking> tags. Be explicit about your reasoning and decision-making process.
If you are uncertain, simulate different potential paths and compare outcomes before choosing the optimal approach.
Mathematical and Formal Reasoning:

For mathematical problems, show all work in detail using LaTeX for formal notation. Provide detailed proofs or calculations to support your conclusions.
Multi-Solution Comparison:

Whenever feasible, explore multiple methods to reach the solution. Compare their effectiveness within <reflection> tags and assess their strengths and weaknesses.
Synthesizing the Final Answer:

Once all steps are complete and you've settled on the best approach, synthesize your final answer using <answer> tags. Provide a concise, well-reasoned summary of your solution, explaining why it is the most effective.
Final Reflection and Reward:

Conclude with a final reflection on the overall solution. Discuss the effectiveness of your approach, the challenges faced, and any learning opportunities encountered along the way.
Assign a final reward score (0.0 to 1.0) based on the overall quality of your solution.
Exploration of Broader Implications:

When applicable, consider the broader implications of your solution. What insights can be drawn from the process? Are there larger principles or concepts that apply?

By incorporating multi-step reasoning, critical reflection, and adaptive problem-solving, you will dynamically develop the best solution while learning from each phase of the process.
"""
    + ASK_PROMPT_JINJA
)

PROBLEM_REFLECT_PROMPT = """Please analyze the following problem and provide a detailed reflection:

Problem Description:
{{input.query}}

Please provide:
1. Key concepts and requirements
2. Potential challenges and edge cases
3. Similar problems you've encountered
4. Suggested approach and methodology
5. Any assumptions that need to be validated

Your reflection should help guide the solution process.
"""

EXAMPLE_REASONING_PROMPT = """
Given the following input with examples:

{{ input.query }}

Please analyze the examples and provide reasoning about:
1. The key patterns or principles demonstrated in the examples
2. How these examples relate to the main problem
3. What insights can be derived from these examples
4. How these insights might guide the solution approach

Reasoning:
"""

IMPROVE_PROMPT = f"""Given the following problem details:

{ASK_PROMPT_JINJA}
{ASK_ADDITIONAL_INFO_JINJA}

Current answer:
{{ input.answer }}

Feedback for improvement:
{{ input.feedback }}

Based on the above feedback, please provide an improved answer. The improved answer should:
1. Address all points mentioned in the feedback
2. Maintain the strengths of the original answer
3. Be clear, accurate, and well-structured
4. Be complete and self-contained

Return only the improved answer without any explanations or comments.
"""

IMPROVE_CODE_PROMPT = """You are a code improvement expert. Your task is to improve the given code based on the test cases.

Current code:
{code}

Test cases:
{test_cases}

AI-generated test cases:
{ai_test_cases}

Entry point function: {entry_point}

Please improve the code to make it pass all test cases. The improved code should:
1. Be more robust and handle edge cases
2. Follow best practices and be well-structured
3. Be efficient and maintainable
4. Pass all test cases

Return only the improved code without any explanations or comments."""
