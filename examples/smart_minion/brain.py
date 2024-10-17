#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import asyncio

import yaml

from metagpt.llm import LLM
from metagpt.minion.brain import Brain
from metagpt.minion.rpyc_python_env import RpycPythonEnv
from metagpt.minion.utils import replace_placeholders_with_env


async def smart_brain():
    import os

    from dotenv import load_dotenv

    # Load the .env file
    load_dotenv()
    llm = LLM()
    # Load the config file
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the path to the memory_config.yml file relative to the current script's location
    config_path = os.path.join(current_dir, "memory_config.yml")
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)

    # Replace placeholders with environment variables
    config = replace_placeholders_with_env(config)

    # Use the updated config in your application
    # print(config)

    # brain = Brain(memory_config=config, llm=llm)
    brain = Brain(python_env=RpycPythonEnv(port=3007), llm=llm)
    # brain = Brain( llm=llm)

    # obs, score, *_ = await brain.step(query="create a 2048 game")
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Every morning, Aya does a $9$ kilometer walk, and then finishes at the coffee shop. One day, she walks at $s$ kilometers per hour, and the walk takes $4$ hours, including $t$ minutes at the coffee shop. Another morning, she walks at $s+2$ kilometers per hour, and the walk takes $2$ hours and $24$ minutes, including $t$ minutes at the coffee shop. This morning, if she walks at $s+\frac12$ kilometers per hour, how many minutes will the walk take, including the $t$ minutes at the coffee shop?",
    #     query_type="code_problem",
    # )
    # print(obs)

    # obs, score, *_ = await brain.step(query="Which one is larger, 9.11 or 9.8?", route="dot")
    # print(obs)

    # obs, score, *_ = await brain.step(query="How many 'r's in the word 'strawberry'?", route="dot")
    # print(obs)
    #
    # obs, score, *_ = await brain.step(query="what's the solution for  game of 24 for 4 3 9 8", route="dot")
    # print(obs)
    #
    # obs, score, *_ = await brain.step(query="what's the solution for  game of 24 for 2 5 11 8")
    # print(obs)
    #
    # obs, score, *_ = await brain.step(query="what's the solution for  game of 24 for 2 4 5 5")
    # print(obs)
    # obs, score, *_ = await brain.step(query="what's the solution for  game of 24 for 3 5 7 13")
    # print(obs)

    # obs, score, *_ = await brain.step(query="create a 2048 game")
    # print(obs)

    # obs, score, *_ = await brain.step(query="what's the solution for  game of 24 for 2 3 8 13")
    # print(obs)
    # obs, score, *_ = await brain.step(query="solve x=1/(1-beta^2*x) where beta=0.85")
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Every morning, Aya does a $9$ kilometer walk, and then finishes at the coffee shop. One day, she walks at $s$ kilometers per hour, and the walk takes $4$ hours, including $t$ minutes at the coffee shop. Another morning, she walks at $s+2$ kilometers per hour, and the walk takes $2$ hours and $24$ minutes, including $t$ minutes at the coffee shop. This morning, if she walks at $s+\frac12$ kilometers per hour, how many minutes will the walk take, including the $t$ minutes at the coffee shop?"
    #     , route="cot",cache_plan="plan_gpt4o"
    # )
    # print(obs)

    # Get the directory of the current file
    os.path.dirname(os.path.abspath(__file__))

    #     llm1 = LLM()
    #     LLM()
    #     llm1.config.temperature = 0.7
    #
    # cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.3.json")
    # obs, score, *_ = await brain.step(
    #     query="Alice and Bob play the following game. A stack of $n$ tokens lies before them. The players take turns with Alice going first. On each turn, the player removes $1$ token or $4$ tokens from the stack. The player who removes the last token wins. Find the number of positive integers $n$ less than or equal to $2024$ such that there is a strategy that guarantees that Bob wins, regardless of Alice’s moves.",
    #     route="native",
    #     dataset="aime 2024",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    # cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.7.json")
    #
    # obs, score, *_ = await brain.step(
    #     query="Find the largest possible real part of\[(75+117i)z+\frac{96+144i}{z}\]where $z$ is a complex number with $|z|=4$.",
    #     route="cot",
    #     dataset="aime 2024",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Real numbers $x$ and $y$ with $x,y>1$ satisfy $\log_x(y^x)=\log_y(x^{4y})=10.$ What is the value of $xy$?",
    #     route="cot",
    #     dataset="aime 2024",
    # )
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Kylar went to the store to buy glasses for his new apartment. One glass costs $5, but every second glass costs only 60% of the price. Kylar wants to buy 16 glasses. How much does he need to pay for them",
    #     route="cot",
    #     dataset="gsm8k",
    # )
    # print(obs)
    # llm.model = "z3-" + llm.model
    # cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.12.json")
    #
    # obs, score, *_ = await brain.step(
    #     query="Define $f(x)=|| x|-\tfrac{1}{2}|$ and $g(x)=|| x|-\tfrac{1}{4}|$. Find the number of intersections of the graphs of\[y=4 g(f(\sin (2 \pi x))) \quad\text{ and }\quad x=4 g(f(\cos (3 \pi y))).\]",
    #     route="cot",
    #     dataset="aime 2024",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    obs, score, *_ = await brain.step(
        query='''
from typing import List def has_close_elements(numbers: List[float], threshold: float) -> bool: """ Check if in given list of numbers, are any two numbers closer to each other than given threshold. >>> has_close_elements([1.0, 2.0, 3.0], 0.5) False >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) True """''',
        route="cot",
        query_type="code_solution",
    )
    print(obs)

    obs, score, *_ = await brain.step(
        query="""'''
    Given list of integers, return list in strange order.
    Strange sorting, is when you start with the minimum value,
    then maximum of the remaining integers, then minimum and so on.

    Examples:
    strange_sort_list([1, 2, 3, 4]) == [1, 4, 2, 3]
    strange_sort_list([5, 5, 5, 5]) == [5, 5, 5, 5]
    strange_sort_list([]) == []
    '''""",
        route="cot",
        query_type="code_solution",
    )
    print(obs)


#
#     # obs, score, *_ = await brain.step(
#     #     query="""33 op 6 = 60
#     #     48 op 96 = 144
#     #     1234 op 234 = ?""",
#     #     route="cot",
#     # )
#     # print(obs)
#
#     obs, score, *_ = await brain.step(
#         query="""I have 6 eggs
#
# I broke 2. I fried 2.
#
# I ate 2.
#
# How many are left?"""
#     )
#     print(obs)

# obs, score, *_ = await brain.step(
#     query="Write a 500000 characters novel named 'Reborn in Skyrim'. "
#     "Fill the empty nodes with your own ideas. Be creative! Use your own words!"
#     "I will tip you $100,000 if you write a good novel."
#     "since the novel is very long, you may need to divide into subtasks",
#     route="plan"
# )
# print(obs)
# cache_plan = os.path.join(current_file_dir, "aime", "alibaba.1.json")
# obs, score, *_ = await brain.step(
#     query="""
#     2024阿里巴巴全球数学竞赛
#
# 问题1
#
# 几位同学假期组成一个小组去某市旅游．该市有6座塔，它们的位置分别为A，B，C，D，B，F。
#
# 同学们自由行动一段时间后，每位同学都发现，自己在所在的位置只能看到位于A，B，C，D 处的四座塔，而看不到位于E 和F的塔。已知
#
# (1）同学们的位置和塔的位置均视为同一平面上的点，且这些点彼此不重合：
#
# (2) A，B，C，D，E，F中任意3点不共线：
#
# (3） 看不到塔的唯一可能就是视线被其它的塔所阻挡，例如，如果某位同学所在的位置P 和A，B 共线，且A 在线段PB上，那么该同学就看不到位于B 处的塔。
#
# 请问，这个旅游小组最多可能有多少名同学？
#
# (A)3 (B) 4 (C)6 (D) 12
#     """,
#     route="cot",cache_plan=cache_plan
# )
# print(obs)


asyncio.run(smart_brain())
