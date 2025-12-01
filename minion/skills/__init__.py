#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skills system for Minion

This module provides a skills system inspired by Claude Skills,
allowing users to define, load, and execute specialized AI skills.
"""

from minion.skills.skill import Skill
from minion.skills.skill_registry import (
    SkillRegistry,
    get_skill_registry,
    reset_skill_registry,
)
from minion.skills.skill_loader import (
    SkillLoader,
    load_skills,
    get_available_skills,
)

__all__ = [
    "Skill",
    "SkillRegistry",
    "get_skill_registry",
    "reset_skill_registry",
    "SkillLoader",
    "load_skills",
    "get_available_skills",
]
