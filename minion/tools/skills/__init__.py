#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Skills system for Minion

This module provides a skills system inspired by Claude Skills,
allowing users to define, load, and execute specialized AI skills.
"""

from minion.tools.skills.skill_loader import (
    Skill,
    SkillMetadata,
    SkillLoader
)
from minion.tools.skills.skill_tool import SkillTool
from minion.tools.skills.skills_manager import SkillsManager

__all__ = [
    "Skill",
    "SkillMetadata",
    "SkillLoader",
    "SkillTool",
    "SkillsManager",
]
