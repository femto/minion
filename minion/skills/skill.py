#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill data class representing a loaded skill.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml


@dataclass
class Skill:
    """Represents a loaded skill with its metadata and content."""

    name: str
    description: str
    content: str  # The markdown body (instructions)
    path: Path  # Path to the skill directory

    # Optional metadata from frontmatter
    license: Optional[str] = None
    allowed_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Source location type
    location: str = "project"  # project, user, managed

    @classmethod
    def from_skill_md(cls, skill_md_path: Path, location: str = "project") -> Optional["Skill"]:
        """
        Parse a SKILL.md file and create a Skill instance.

        Args:
            skill_md_path: Path to the SKILL.md file
            location: Where the skill was found (project, user, managed)

        Returns:
            Skill instance or None if parsing fails
        """
        if not skill_md_path.exists():
            return None

        content = skill_md_path.read_text(encoding='utf-8')
        frontmatter, body = cls._parse_frontmatter(content)

        if not frontmatter:
            return None

        name = frontmatter.get('name')
        description = frontmatter.get('description')

        if not name or not description:
            return None

        return cls(
            name=name,
            description=description,
            content=body.strip(),
            path=skill_md_path.parent,
            license=frontmatter.get('license'),
            allowed_tools=frontmatter.get('allowed-tools', []) or [],
            metadata=frontmatter.get('metadata', {}) or {},
            location=location,
        )

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from markdown content.

        Args:
            content: Raw markdown content with potential YAML frontmatter

        Returns:
            Tuple of (frontmatter dict, body content)
        """
        # Match YAML frontmatter pattern: starts with ---, ends with ---
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}, content

        yaml_content = match.group(1)
        body = match.group(2)

        try:
            frontmatter = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError:
            return {}, content

        return frontmatter, body

    def get_prompt(self) -> str:
        """
        Get the full prompt content for this skill.
        Includes the skill location header for resolving relative paths
        to bundled resources (references/, scripts/, assets/).

        Returns:
            Full prompt string with base directory header
        """
        header = f"""Loading: {self.name}
Base directory: {self.path}

"""
        return header + self.content

    def to_xml(self) -> str:
        """
        Format skill as XML for inclusion in prompts.

        Returns:
            XML formatted skill entry
        """
        return f"""<skill>
<name>{self.name}</name>
<description>{self.description}</description>
<location>{self.location}</location>
</skill>"""

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, location={self.location!r})"
