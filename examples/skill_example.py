#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill System Example - Using Skills with CodeAgent

Skills are modular packages that extend agent capabilities.
Install skills by copying to: .minion/skills/ or ~/.minion/skills/

See docs/skills.md for full documentation.
"""

import asyncio
from minion.agents import CodeAgent
from minion.tools import SkillTool, BashTool


async def main():
    """Example: Using skills with CodeAgent"""

    # Create agent with skill support
    agent = await CodeAgent.create(
        name="Skill-Enabled Agent",
        llm="sonnet",  # or your preferred model
        tools=[SkillTool(), BashTool()],
    )

    # The agent can now invoke skills
    # Skills are automatically discovered from .minion/skills/ and ~/.minion/skills/
    result = await agent.run_async("hello")
    print(result.content)
    # result = await agent.run_async("can you summary what does .minion/memory.pdf say")
    # print(result.content)


if __name__ == "__main__":
    asyncio.run(main())
