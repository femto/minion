#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Skills Manager

Manages skills for agents, including loading, selection, and context injection.
"""

import ast
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from minion.tools.skills.skill_loader import Skill, SkillLoader

logger = logging.getLogger(__name__)


class SkillsManager:
    """Manages skills for an agent

    The SkillsManager is responsible for:
    1. Loading skills from filesystem
    2. Selecting relevant skills for tasks
    3. Building system prompt extensions with skill context
    4. Providing skill scripts for Python executor
    """

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        enabled_skills: Optional[List[str]] = None,
        auto_load: bool = True
    ):
        """Initialize skills manager

        Args:
            skills_dir: Directory containing skills (default: ~/.minion/skills)
            enabled_skills: List of skill names to enable (None = all available)
            auto_load: Automatically load skills on initialization
        """
        self.loader = SkillLoader(skills_dir)
        self.enabled_skills = set(enabled_skills) if enabled_skills else None
        self.skills: Dict[str, Skill] = {}

        if auto_load:
            self.load_all_skills()

    def load_all_skills(self):
        """Load all available skills

        If enabled_skills is specified, only load those skills.
        Otherwise, load all skills found in skills directory.
        """
        all_skills = self.loader.load_all_skills()

        # Filter by enabled_skills if specified
        if self.enabled_skills:
            self.skills = {
                name: skill
                for name, skill in all_skills.items()
                if name in self.enabled_skills
            }

            # Warn about missing skills
            missing = self.enabled_skills - set(self.skills.keys())
            if missing:
                logger.warning(f"Requested skills not found: {missing}")
        else:
            self.skills = all_skills

        logger.info(f"Loaded {len(self.skills)} skills: {list(self.skills.keys())}")

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name

        Args:
            name: Skill name

        Returns:
            Skill object or None if not found
        """
        return self.skills.get(name)

    def list_skills(self) -> List[str]:
        """List available skill names

        Returns:
            List of skill names
        """
        return list(self.skills.keys())

    def has_skills(self) -> bool:
        """Check if any skills are loaded

        Returns:
            True if skills are available
        """
        return len(self.skills) > 0

    def build_system_prompt_extension(
        self,
        task: Optional[str] = None,
        include_all: bool = False
    ) -> str:
        """Build system prompt extension with skill information

        Args:
            task: Optional task description for smart skill selection
            include_all: If True, include all skills regardless of relevance

        Returns:
            String to append to system prompt
        """
        if not self.skills:
            return ""

        # Select relevant skills based on task
        if include_all:
            relevant_skills = list(self.skills.keys())
        else:
            relevant_skills = self._select_relevant_skills(task)

        if not relevant_skills:
            return ""

        prompt = "\n\n# 📚 Available Skills\n\n"
        prompt += "You have access to specialized skills with pre-built functions and knowledge.\n\n"

        for skill_name in relevant_skills:
            skill = self.skills[skill_name]
            prompt += f"## Skill: {skill.metadata.name}\n\n"
            prompt += f"**Description:** {skill.metadata.description}\n\n"

            # List available functions from scripts
            if skill.scripts:
                prompt += "**Available Functions:**\n\n"
                for script_name in skill.list_scripts():
                    script_content = skill.get_script(script_name)
                    functions = self._extract_function_info(script_content)

                    if functions:
                        prompt += f"From `{script_name}`:\n"
                        for func_info in functions:
                            prompt += f"- `{func_info['signature']}`: {func_info['docstring']}\n"
                        prompt += "\n"

            # Add skill instructions (shortened)
            instructions = skill.instructions[:500]  # First 500 chars
            if len(skill.instructions) > 500:
                instructions += "..."

            prompt += f"**Usage Instructions:**\n{instructions}\n\n"

            # Add reference to full context
            if skill.references:
                prompt += f"**References:** {', '.join(skill.list_references())}\n\n"

            prompt += "---\n\n"

        prompt += "\n**How to Use Skills:**\n"
        prompt += "- Skills provide Python functions you can call directly in your code\n"
        prompt += "- Import functions naturally: `from skill_module import function_name`\n"
        prompt += "- All skill functions are available in your execution environment\n"
        prompt += "- Follow the skill instructions for best results\n"

        return prompt

    def get_skill_scripts_namespace(self) -> Dict[str, str]:
        """Get all skill scripts as executable code

        Returns:
            Dictionary mapping script names to their content
        """
        namespace = {}

        for skill_name, skill in self.skills.items():
            for script_name, script_content in skill.scripts.items():
                # Create a unique key for each skill script
                # Format: skill_name__script_name
                key = f"{skill_name}__{script_name}"
                namespace[key] = script_content

        return namespace

    def get_skill_scripts_as_modules(self) -> Dict[str, str]:
        """Get skill scripts formatted as importable modules

        Returns:
            Dictionary mapping module names to script content
        """
        modules = {}

        for skill_name, skill in self.skills.items():
            for script_name, script_content in skill.scripts.items():
                # Create module name: skill_<skill_name>_<script_name>
                module_name = f"skill_{skill_name.replace('-', '_')}_{script_name.replace('.py', '').replace('/', '_')}"

                # Add module docstring
                module_code = f'"""\nSkill: {skill.metadata.name}\nScript: {script_name}\n"""\n\n'
                module_code += script_content

                modules[module_name] = module_code

        return modules

    def _select_relevant_skills(self, task: Optional[str]) -> List[str]:
        """Select relevant skills based on task description

        Uses simple keyword matching. Can be enhanced with LLM in the future.

        Args:
            task: Task description

        Returns:
            List of relevant skill names
        """
        if not task:
            # If no task specified, return all skills
            return list(self.skills.keys())

        task_lower = task.lower()
        relevant = []

        for skill_name, skill in self.skills.items():
            # Check skill name
            if skill_name.lower() in task_lower:
                relevant.append(skill_name)
                continue

            # Check description
            if any(word in task_lower for word in skill.metadata.description.lower().split()):
                if skill_name not in relevant:
                    relevant.append(skill_name)
                    continue

            # Check tags
            for tag in skill.metadata.tags:
                if tag.lower() in task_lower:
                    if skill_name not in relevant:
                        relevant.append(skill_name)
                        break

        # If no specific match found, return all skills
        # (better to have too much context than too little)
        if not relevant:
            logger.info("No specific skill match found, including all skills")
            return list(self.skills.keys())

        logger.info(f"Selected relevant skills: {relevant}")
        return relevant

    def _extract_function_info(self, code: str) -> List[Dict[str, str]]:
        """Extract function information from Python code

        Args:
            code: Python source code

        Returns:
            List of dictionaries with function info:
                - name: Function name
                - signature: Full function signature
                - docstring: Function docstring (first line)
        """
        try:
            tree = ast.parse(code)
            functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Skip private functions
                    if node.name.startswith('_'):
                        continue

                    # Build signature
                    args = []
                    for arg in node.args.args:
                        arg_str = arg.arg

                        # Add type annotation if available
                        if arg.annotation:
                            arg_str += f": {ast.unparse(arg.annotation)}"

                        args.append(arg_str)

                    # Add return type if available
                    return_type = ""
                    if node.returns:
                        return_type = f" -> {ast.unparse(node.returns)}"

                    signature = f"{node.name}({', '.join(args)}){return_type}"

                    # Extract docstring (first line only)
                    docstring = ast.get_docstring(node)
                    if docstring:
                        docstring = docstring.split('\n')[0].strip()
                    else:
                        docstring = "No description"

                    functions.append({
                        'name': node.name,
                        'signature': signature,
                        'docstring': docstring
                    })

            return functions

        except Exception as e:
            logger.warning(f"Failed to parse code for function extraction: {e}")
            return []

    def reload_skills(self):
        """Reload all skills from filesystem

        Useful for development when skills are being modified.
        """
        logger.info("Reloading skills...")
        self.skills.clear()
        self.load_all_skills()

    def add_skill(self, skill: Skill):
        """Manually add a skill

        Args:
            skill: Skill object to add
        """
        self.skills[skill.metadata.name] = skill
        logger.info(f"Added skill: {skill.metadata.name}")

    def remove_skill(self, skill_name: str) -> bool:
        """Remove a skill

        Args:
            skill_name: Name of skill to remove

        Returns:
            True if skill was removed, False if not found
        """
        if skill_name in self.skills:
            del self.skills[skill_name]
            logger.info(f"Removed skill: {skill_name}")
            return True
        return False

    def get_skills_info(self) -> Dict[str, Dict[str, any]]:
        """Get information about all loaded skills

        Returns:
            Dictionary with skill information
        """
        info = {}

        for skill_name, skill in self.skills.items():
            info[skill_name] = {
                'name': skill.metadata.name,
                'description': skill.metadata.description,
                'version': skill.metadata.version,
                'author': skill.metadata.author,
                'tags': skill.metadata.tags,
                'scripts': skill.list_scripts(),
                'references': skill.list_references(),
                'requirements': skill.metadata.requirements
            }

        return info
