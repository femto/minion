#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the Skills System
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from minion.skills import (
    Skill,
    SkillRegistry,
    SkillLoader,
    load_skills,
    get_skill_registry,
    reset_skill_registry,
)
from minion.tools import SkillTool, BashTool


class TestSkill:
    """Tests for Skill class"""

    def test_parse_skill_md(self, tmp_path):
        """Test parsing SKILL.md file"""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: A test skill for unit testing
license: MIT
allowed-tools:
  - bash
  - file_read
---

# Test Skill Instructions

This is a test skill.
""")

        skill = Skill.from_skill_md(skill_md, location="project")

        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill for unit testing"
        assert skill.license == "MIT"
        assert "bash" in skill.allowed_tools
        assert skill.location == "project"
        assert "This is a test skill" in skill.content

    def test_invalid_skill_md(self, tmp_path):
        """Test parsing invalid SKILL.md"""
        skill_dir = tmp_path / "invalid-skill"
        skill_dir.mkdir()

        # Missing required fields
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: incomplete
---

No description provided.
""")

        skill = Skill.from_skill_md(skill_md)
        assert skill is None  # Should fail without description

    def test_skill_to_xml(self, tmp_path):
        """Test XML formatting"""
        skill = Skill(
            name="xml-test",
            description="Test XML output",
            content="Instructions here",
            path=tmp_path,
            location="user"
        )

        xml = skill.to_xml()
        assert "<name>xml-test</name>" in xml
        assert "<description>Test XML output</description>" in xml
        assert "<location>user</location>" in xml

    def test_skill_get_prompt(self, tmp_path):
        """Test get_prompt includes header"""
        skill = Skill(
            name="prompt-test",
            description="Test prompt",
            content="My instructions",
            path=tmp_path,
            location="project"
        )

        prompt = skill.get_prompt()
        assert "Loading: prompt-test" in prompt
        assert str(tmp_path) in prompt
        assert "My instructions" in prompt


class TestSkillRegistry:
    """Tests for SkillRegistry"""

    def setup_method(self):
        """Reset registry before each test"""
        reset_skill_registry()

    def test_register_and_get(self, tmp_path):
        """Test registering and retrieving skills"""
        registry = SkillRegistry()

        skill = Skill(
            name="reg-test",
            description="Registry test",
            content="Content",
            path=tmp_path
        )

        assert registry.register(skill) is True
        assert registry.get("reg-test") == skill
        assert registry.exists("reg-test") is True
        assert len(registry) == 1

    def test_priority_override(self, tmp_path):
        """Test project skills override user skills"""
        registry = SkillRegistry()

        user_skill = Skill(
            name="priority-test",
            description="User version",
            content="User content",
            path=tmp_path,
            location="user"
        )

        project_skill = Skill(
            name="priority-test",
            description="Project version",
            content="Project content",
            path=tmp_path,
            location="project"
        )

        # Register user skill first
        registry.register(user_skill)
        assert registry.get("priority-test").description == "User version"

        # Project skill should override
        registry.register(project_skill)
        assert registry.get("priority-test").description == "Project version"

    def test_list_all(self, tmp_path):
        """Test listing all skills"""
        registry = SkillRegistry()

        for i in range(3):
            skill = Skill(
                name=f"skill-{i}",
                description=f"Skill {i}",
                content="Content",
                path=tmp_path
            )
            registry.register(skill)

        skills = registry.list_all()
        assert len(skills) == 3

    def test_generate_skills_prompt(self, tmp_path):
        """Test generating skills prompt"""
        registry = SkillRegistry()

        skill = Skill(
            name="prompt-gen",
            description="For prompt generation",
            content="Content",
            path=tmp_path
        )
        registry.register(skill)

        prompt = registry.generate_skills_prompt()
        assert "<available_skills>" in prompt
        assert "prompt-gen" in prompt


class TestSkillLoader:
    """Tests for SkillLoader"""

    def setup_method(self):
        reset_skill_registry()

    def test_discover_skills(self, tmp_path):
        """Test skill discovery"""
        # Create skill directory structure
        skills_dir = tmp_path / ".minion" / "skills"
        skill1_dir = skills_dir / "skill1"
        skill1_dir.mkdir(parents=True)

        (skill1_dir / "SKILL.md").write_text("""---
name: skill1
description: First skill
---

Instructions for skill1.
""")

        loader = SkillLoader(project_root=tmp_path)
        skill_files = loader.discover_skills(skills_dir)

        assert len(skill_files) == 1
        assert skill_files[0].name == "SKILL.md"

    def test_load_all(self, tmp_path):
        """Test loading all skills"""
        # Create skills
        for skill_name in ["alpha", "beta"]:
            skill_dir = tmp_path / ".minion" / "skills" / skill_name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"""---
name: {skill_name}
description: {skill_name.title()} skill
---

Instructions for {skill_name}.
""")

        loader = SkillLoader(project_root=tmp_path)
        registry = loader.load_all(SkillRegistry())

        assert len(registry) == 2
        assert registry.exists("alpha")
        assert registry.exists("beta")


class TestSkillTool:
    """Tests for SkillTool"""

    def setup_method(self):
        reset_skill_registry()

    def test_execute_unknown_skill(self):
        """Test executing unknown skill returns error"""
        tool = SkillTool()
        result = tool.forward(skill="nonexistent")

        assert result["success"] is False
        assert "Unknown skill" in result["error"]

    def test_validate_skill(self):
        """Test skill validation"""
        tool = SkillTool()

        valid, error = tool.validate_skill("")
        assert valid is False
        assert "required" in error.lower()

        valid, error = tool.validate_skill("nonexistent")
        assert valid is False


class TestBashTool:
    """Tests for BashTool"""

    def test_execute_simple_command(self):
        """Test executing simple bash command"""
        tool = BashTool()
        result = tool.forward(command="echo 'hello'")

        assert "hello" in result
        assert "Exit code: 0" in result

    def test_dangerous_command_blocked(self):
        """Test dangerous commands are blocked"""
        tool = BashTool()

        result = tool.forward(command="rm -rf /")
        assert "Dangerous command prohibited" in result

        result = tool.forward(command="sudo echo test")
        assert "Dangerous command prohibited" in result

    def test_timeout(self):
        """Test command timeout"""
        tool = BashTool()
        result = tool.forward(command="sleep 5", timeout=1)

        assert "timeout" in result.lower()
