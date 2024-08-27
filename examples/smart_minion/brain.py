#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import asyncio
import os
import re

import yaml

from metagpt.llm import LLM
from metagpt.minion.brain import Brain


def replace_placeholders_with_env(config):
    # Define a regex pattern to match placeholders like "${ENV_VAR}"
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replace_in_value(value):
        if isinstance(value, str):
            # Search for the placeholder pattern
            match = pattern.search(value)
            if match:
                env_var = match.group(1)
                return os.getenv(env_var, value)  # Replace with env var if available, otherwise keep the original value
        return value

    def recursive_replace(obj):
        if isinstance(obj, dict):
            return {key: recursive_replace(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [recursive_replace(item) for item in obj]
        else:
            return replace_in_value(obj)

    return recursive_replace(config)


async def smart_brain():
    import os

    from dotenv import load_dotenv

    # Load the .env file
    load_dotenv()

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

    brain = Brain(memory_config=config)

    # obs, score, *_ = await brain.step(query="create a 2048 game")
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Every morning, Aya does a $9$ kilometer walk, and then finishes at the coffee shop. One day, she walks at $s$ kilometers per hour, and the walk takes $4$ hours, including $t$ minutes at the coffee shop. Another morning, she walks at $s+2$ kilometers per hour, and the walk takes $2$ hours and $24$ minutes, including $t$ minutes at the coffee shop. This morning, if she walks at $s+\frac12$ kilometers per hour, how many minutes will the walk take, including the $t$ minutes at the coffee shop?",
    #     query_type="code_problem",
    # )
    # print(obs)
    #
    # obs, score, *_ = await brain.step(query="what's the solution for  game of 24 for 4 3 9 8")
    # print(obs)
    #
    # obs, score, *_ = await brain.step(query="what's the solution for  game of 24 for 2 5 11 8")
    # print(obs)

    # obs, score, *_ = await brain.step(query="what's the solution for  game of 24 for 2 4 5 5")
    # print(obs)
    # obs, score, *_ = await brain.step(query="solve x=1/(1-beta^2*x) where beta=0.85")
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Every morning, Aya does a $9$ kilometer walk, and then finishes at the coffee shop. One day, she walks at $s$ kilometers per hour, and the walk takes $4$ hours, including $t$ minutes at the coffee shop. Another morning, she walks at $s+2$ kilometers per hour, and the walk takes $2$ hours and $24$ minutes, including $t$ minutes at the coffee shop. This morning, if she walks at $s+\frac12$ kilometers per hour, how many minutes will the walk take, including the $t$ minutes at the coffee shop?"
    #     , route="cot",cache_plan="plan_gpt4o"
    # )
    # print(obs)

    # Get the directory of the current file
    current_file_dir = os.path.dirname(os.path.abspath(__file__))

    llm1 = LLM()
    LLM()
    llm1.config.temperature = 0.7

    cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.3.json")
    obs, score, *_ = await brain.step(
        query="Alice and Bob play the following game. A stack of $n$ tokens lies before them. The players take turns with Alice going first. On each turn, the player removes $1$ token or $4$ tokens from the stack. The player who removes the last token wins. Find the number of positive integers $n$ less than or equal to $2024$ such that there is a strategy that guarantees that Bob wins, regardless of Alice’s moves.",
        route="cot",
        dataset="aime 2024",
        cache_plan=cache_plan,
    )
    print(obs)

    cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.7.json")

    obs, score, *_ = await brain.step(
        query="Find the largest possible real part of\[(75+117i)z+\frac{96+144i}{z}\]where $z$ is a complex number with $|z|=4$.",
        route="cot",
        dataset="aime 2024",
        cache_plan=cache_plan,
    )
    print(obs)

    # obs, score, *_ = await brain.step(
    #     query="""33 op 6 = 60
    #     48 op 96 = 144
    #     1234 op 234 = ?""",
    #     route="cot",
    # )
    # print(obs)

    obs, score, *_ = await brain.step(
        query="""I have 6 eggs

I broke 2. I fried 2.

I ate 2.

How many are left?"""
    )
    print(obs)

    obs, score, *_ = await brain.step(
        query="Write a 500000 characters novel named 'Reborn in Skyrim'. "
        "Fill the empty nodes with your own ideas. Be creative! Use your own words!"
        "I will tip you $100,000 if you write a good novel."
        "since the novel is very long, you may need to divide into subtasks"
    )
    print(obs)

    obs, score, *_ = await brain.step(
        query="""
        2024阿里巴巴全球数学竞赛

    问题1

    几位同学假期组成一个小组去某市旅游．该市有6座塔，它们的位置分别为A，B，C，D，B，F。

    同学们自由行动一段时间后，每位同学都发现，自己在所在的位置只能看到位于A，B，C，D 处的四座塔，而看不到位于E 和F的塔。已知

    (1）同学们的位置和塔的位置均视为同一平面上的点，且这些点彼此不重合：

    (2) A，B，C，D，E，F中任意3点不共线：

    (3） 看不到塔的唯一可能就是视线被其它的塔所阻挡，例如，如果某位同学所在的位置P 和A，B 共线，且A 在线段PB上，那么该同学就看不到位于B 处的塔。

    请问，这个旅游小组最多可能有多少名同学？

    (A)3 (B) 4 (C)6 (D) 12
        """
    )
    print(obs)


asyncio.run(smart_brain())
