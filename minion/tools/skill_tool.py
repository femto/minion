#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill Tool - executes skills within the conversation.

This tool allows Claude to invoke skills that provide specialized knowledge
and workflows for specific tasks.
"""

from typing import Any, Dict, Optional

from minion.tools import BaseTool


class SkillTool(BaseTool):
    """
    Tool for executing skills within the main conversation.

    Skills are modular packages that extend Claude's capabilities by providing
    specialized knowledge, workflows, and tools. When a skill is invoked,
    its instructions are loaded into the conversation context.
    """

    name: str = "Skill"
    description: str = """Execute a skill within the main conversation.

Skills are folders of instructions, scripts, and resources that Claude loads
dynamically to improve performance on specialized tasks.

Usage:
- Invoke skills using this tool with the skill name only (no arguments)
- When you invoke a skill, its prompt will expand and provide detailed instructions
- Only use skills listed in <available_skills> in the system prompt

Important:
- Only use skills that are listed as available
- Do not invoke a skill that is already running
"""

    inputs: dict = {
        "skill": {
            "type": "string",
            "description": "The skill name to execute (e.g., 'pdf', 'xlsx', 'docx')"
        }
    }
    output_type: str = "object"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._registry = None

    @property
    def registry(self):
        """Get the skill registry, loading skills if needed."""
        if self._registry is None:
            from minion.skills import SkillRegistry, load_skills
            self._registry = load_skills()
        return self._registry

    def forward(self, skill: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a skill by loading its instructions into the conversation.
        This is the synchronous entry point required by BaseTool.

        Args:
            skill: Name of the skill to execute

        Returns:
            Dict containing the skill prompt and metadata
        """
        return self.execute_skill(skill)

    def execute_skill(self, skill: str) -> Dict[str, Any]:
        """
        Execute a skill by loading its instructions into the conversation.

        Args:
            skill: Name of the skill to execute

        Returns:
            Dict containing the skill prompt and metadata
        """
        # Check if skill exists
        skill_obj = self.registry.get(skill)

        if skill_obj is None:
            available = [s.name for s in self.registry.list_all()]
            return {
                "success": False,
                "error": f"Unknown skill: {skill}",
                "available_skills": available[:10],  # Show first 10
                "hint": "Use one of the available skills listed above"
            }

        # Get the skill prompt
        prompt = skill_obj.get_prompt()

        # Build response with skill content
        return {
            "success": True,
            "skill_name": skill_obj.name,
            "skill_description": skill_obj.description,
            "skill_location": skill_obj.location,
            "skill_path": str(skill_obj.path),  # Absolute path for resolving relative resources
            "prompt": prompt,
            "message": f'The "{skill_obj.name}" skill is loading',
            "allowed_tools": skill_obj.allowed_tools,
        }

    async def execute(self, skill: str, **kwargs) -> Dict[str, Any]:
        """
        Async wrapper for execute_skill.

        Args:
            skill: Name of the skill to execute

        Returns:
            Dict containing the skill prompt and metadata
        """
        return self.execute_skill(skill)

    def validate_skill(self, skill: str) -> tuple[bool, Optional[str]]:
        """
        Validate that a skill exists and can be executed.

        Args:
            skill: Name of the skill to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not skill:
            return False, "Skill name is required"

        if not self.registry.exists(skill):
            available = [s.name for s in self.registry.list_all()]
            return False, f"Unknown skill: {skill}. Available: {', '.join(available[:5])}"

        return True, None

    def get_available_skills_prompt(self, char_budget: int = 10000) -> str:
        """
        Generate a prompt listing available skills for the system message.

        Args:
            char_budget: Maximum characters for skills list

        Returns:
            Formatted skills prompt
        """
        return self.registry.generate_skills_prompt(char_budget)


def generate_skill_tool_prompt() -> str:
    """
    Generate the complete skill tool prompt including available skills.

    This is used to generate the skill tool description in the system prompt.

    Returns:
        Complete skill tool prompt
    """
    from minion.skills import load_skills

    registry = load_skills()
    skills = registry.list_all()

    if not skills:
        return """Execute a skill within the main conversation.

No skills are currently available. Skills can be added to:
- .claude/skills/ (project-level)
- ~/.claude/skills/ (user-level)
- .minion/skills/ (project-level)
- ~/.minion/skills/ (user-level)
"""

    skills_xml = "\n".join(skill.to_xml() for skill in skills)

    return f"""Execute a skill within the main conversation.

<skills_instructions>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke skills using this tool with the skill name only (no arguments)
- When you invoke a skill, you will see <command-message>The "{{name}}" skill is loading</command-message>
- The skill's prompt will expand and provide detailed instructions on how to complete the task
- Base directory provided in output for resolving bundled resources (references/, scripts/, assets/)

Important:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already running
</skills_instructions>

<available_skills>
{skills_xml}
</available_skills>
"""
