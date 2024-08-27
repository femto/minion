#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/9/13 12:29
@Author  : femto Zheng
@File    : brain.py
"""
import asyncio
import os

from metagpt.minion.brain import Brain


async def smart_brain():
    brain = Brain()

    # Get the directory of the current file
    current_file_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the path relative to the current file's directory
    # cache_plan = os.path.join(current_file_dir, 'dir', 'aime', 'plan_deepseek.json')

    # obs, score, *_ = await brain.step(
    #     query="Every morning, Aya does a $9$ kilometer walk, and then finishes at the coffee shop. One day, she walks at $s$ kilometers per hour, and the walk takes $4$ hours, including $t$ minutes at the coffee shop. Another morning, she walks at $s+2$ kilometers per hour, and the walk takes $2$ hours and $24$ minutes, including $t$ minutes at the coffee shop. This morning, if she walks at $s+\frac12$ kilometers per hour, how many minutes will the walk take, including the $t$ minutes at the coffee shop?",
    #     route="cot",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Real numbers $x$ and $y$ with $x,y>1$ satisfy $\log_x(y^x)=\log_y(x^{4y})=10.$ What is the value of $xy$?",
    #     route="cot",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Alice and Bob play the following game. A stack of $n$ tokens lies before them. The players take turns with Alice going first. On each turn, the player removes $1$ token or $4$ tokens from the stack. The player who removes the last token wins. Find the number of positive integers $n$ less than or equal to $2024$ such that there is a strategy that guarantees that Bob wins, regardless of Alice’s moves.",
    #     route="python",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Jen enters a lottery by picking $4$ distinct numbers from $S=\{1,2,3,\cdots,9,10\}.$ $4$ numbers are randomly chosen from $S.$ She wins a prize if at least two of her numbers were $2$ of the randomly chosen numbers, and wins the grand prize if all four of her numbers were the randomly chosen numbers. The probability of her winning the grand prize given that she won a prize is $\tfrac{m}{n}$ where $m$ and $n$ are relatively prime positive integers. Find $m+n$.",
    #     route="cot",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    # geometry, need vision
    # obs, score, *_ = await brain.step(
    #     query="Rectangles $ABCD$ and $EFGH$ are drawn such that $D,E,C,F$ are collinear. Also, $A,D,H,G$ all lie on a circle. If $BC=16,$ $AB=107,$ $FG=17,$ and $EF=184,$ what is the length of $CE$?",
    #     route="cot",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    # obs, score, *_ = await brain.step(
    #     query="Consider the paths of length $16$ that follow the lines from the lower left corner to the upper right corner on an $8\times 8$ grid. Find the number of such paths that change direction exactly four times, like in the examples shown below.",
    #     route="cot",
    #     cache_plan=cache_plan,
    # )
    # print(obs)

    cache_plan = os.path.join(current_file_dir, "aime", "plan_gpt4o.7.json")
    obs, score, *_ = await brain.step(
        query="Find the largest possible real part of\[(75+117i)z+\frac{96+144i}{z}\]where $z$ is a complex number with $|z|=4$.",
        route="math_plan",
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
