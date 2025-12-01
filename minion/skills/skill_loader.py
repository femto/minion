#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill Loader - discovers and loads skills from standard directories.
"""

import os
from pathlib import Path
from typing import List, Optional
import logging

from .skill import Skill
from .skill_registry import SkillRegistry, get_skill_registry

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    Discovers and loads skills from standard directories.

    Search paths (in priority order):
    1. .claude/skills (project-level)
    2. .minion/skills (project-level)
    3. ~/.claude/skills (user-level)
    4. ~/.minion/skills (user-level)

    Project-level skills override user-level skills with the same name.
    """

    # Default skill directory names
    SKILL_DIRS = [
        ".claude/skills",
        ".minion/skills",
    ]

    SKILL_FILE = "SKILL.md"

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the skill loader.

        Args:
            project_root: Root directory of the project. Defaults to current directory.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.home_dir = Path.home()

    def get_search_paths(self) -> List[tuple[Path, str]]:
        """
        Get all skill search paths with their location type.

        Returns:
            List of (path, location_type) tuples
        """
        paths = []

        # Project-level paths (higher priority)
        for skill_dir in self.SKILL_DIRS:
            project_path = self.project_root / skill_dir
            paths.append((project_path, "project"))

        # User-level paths (lower priority)
        for skill_dir in self.SKILL_DIRS:
            user_path = self.home_dir / skill_dir
            paths.append((user_path, "user"))

        return paths

    def discover_skills(self, skills_dir: Path) -> List[Path]:
        """
        Discover all skill directories within a skills directory.

        A skill directory must contain a SKILL.md file.

        Args:
            skills_dir: Directory containing skill subdirectories

        Returns:
            List of paths to SKILL.md files
        """
        if not skills_dir.exists() or not skills_dir.is_dir():
            return []

        skill_files = []

        for item in skills_dir.iterdir():
            if item.is_dir():
                skill_md = item / self.SKILL_FILE
                if skill_md.exists():
                    skill_files.append(skill_md)
                else:
                    # Check for nested skill directories (e.g., document-skills/pdf)
                    for nested_item in item.iterdir():
                        if nested_item.is_dir():
                            nested_skill_md = nested_item / self.SKILL_FILE
                            if nested_skill_md.exists():
                                skill_files.append(nested_skill_md)

        return skill_files

    def load_skill(self, skill_md_path: Path, location: str) -> Optional[Skill]:
        """
        Load a single skill from its SKILL.md file.

        Args:
            skill_md_path: Path to the SKILL.md file
            location: Location type (project, user, managed)

        Returns:
            Skill instance or None if loading fails
        """
        try:
            skill = Skill.from_skill_md(skill_md_path, location)
            if skill:
                logger.debug(f"Loaded skill: {skill.name} from {skill_md_path}")
            else:
                logger.warning(f"Failed to parse skill: {skill_md_path}")
            return skill
        except Exception as e:
            logger.error(f"Error loading skill from {skill_md_path}: {e}")
            return None

    def load_all(self, registry: Optional[SkillRegistry] = None) -> SkillRegistry:
        """
        Load all skills from all search paths into the registry.

        Args:
            registry: Optional registry to load into. Creates new if not provided.

        Returns:
            SkillRegistry containing all loaded skills
        """
        if registry is None:
            registry = get_skill_registry()

        for search_path, location in self.get_search_paths():
            skill_files = self.discover_skills(search_path)

            for skill_md_path in skill_files:
                skill = self.load_skill(skill_md_path, location)
                if skill:
                    registered = registry.register(skill)
                    if registered:
                        logger.info(f"Registered skill: {skill.name} ({location})")
                    else:
                        logger.debug(f"Skipped skill {skill.name} - already registered from higher priority location")

        return registry

    def reload(self, registry: Optional[SkillRegistry] = None) -> SkillRegistry:
        """
        Reload all skills, clearing the existing registry first.

        Args:
            registry: Optional registry to reload. Uses global if not provided.

        Returns:
            SkillRegistry containing all reloaded skills
        """
        if registry is None:
            registry = get_skill_registry()

        registry.clear()
        return self.load_all(registry)


def load_skills(project_root: Optional[Path] = None) -> SkillRegistry:
    """
    Convenience function to load all skills.

    Args:
        project_root: Root directory of the project

    Returns:
        SkillRegistry containing all loaded skills
    """
    loader = SkillLoader(project_root)
    return loader.load_all()


def get_available_skills() -> List[Skill]:
    """
    Get list of all available skills.

    Loads skills if the registry is empty.

    Returns:
        List of available skills
    """
    registry = get_skill_registry()

    if len(registry) == 0:
        load_skills()

    return registry.list_all()
