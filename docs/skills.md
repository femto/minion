# Skills System

Skills are modular packages that extend agent capabilities with specialized knowledge and workflows.

## Skill Locations

Skills are loaded from these directories (in priority order):

| Location | Path | Priority |
|----------|------|----------|
| Project | `.minion/skills/` | Highest |
| Project | `.claude/skills/` | High |
| User | `~/.minion/skills/` | Low |
| User | `~/.claude/skills/` | Lowest |

Project-level skills override user-level skills with the same name.

## Installing Skills

### Install Skills from git(eg. Anthropic Skills )

```bash
# Create skills directory and clone official skills
mkdir -p .minion/
cd .minion/
git clone https://github.com/anthropics/skills.git
```

### Install Individual Skills

Simply copy skill folders to one of the skill directories:

```bash
# Install to project (recommended for project-specific skills)
cp -r path/to/my-skill .minion/skills/

# Install to user directory (available across all projects)
mkdir -p ~/.minion/skills/
cp -r path/to/my-skill ~/.minion/skills/
```

## Skill Structure

A skill is a directory containing a `SKILL.md` file:

```
.minion/skills/
└── my-skill/
    ├── SKILL.md          # Required: Metadata and instructions
    ├── scripts/          # Optional: Python scripts
    ├── references/       # Optional: Reference documents
    └── assets/           # Optional: Other resources
```

## SKILL.md Format

```markdown
---
name: my-skill
description: A brief description of what this skill does
license: MIT
allowed-tools:
  - bash
  - file_read
---

# Skill Instructions

Instructions for the AI when this skill is activated.

## Usage

Describe how to use this skill...

## Examples

Provide examples...
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique skill identifier |
| `description` | Yes | Brief description (shown in skill list) |
| `license` | No | License type (e.g., MIT, Apache-2.0) |
| `allowed-tools` | No | List of tools the skill can use |

## Using Skills

### With SkillTool

```python
from minion.tools import SkillTool

skill_tool = SkillTool()

# Execute a skill
result = skill_tool.forward(skill="pdf")

if result["success"]:
    print(result["prompt"])  # Skill instructions
```

### With CodeAgent

```python
from minion.agents import CodeAgent
from minion.tools import SkillTool, BashTool

# Create agent with skill support
agent = await CodeAgent.create(
    name="Skill Agent",
    llm="gpt-4o",
    tools=[SkillTool(), BashTool()],
)

# Agent can now invoke skills
async for event in await agent.run_async("Use the pdf skill to extract text"):
    print(event)
```

### Programmatic Access

```python
from minion.skills import load_skills, get_available_skills

# Load all skills
registry = load_skills()

# List skills
for skill in registry.list_all():
    print(f"{skill.name}: {skill.description}")

# Get specific skill
skill = registry.get("pdf")
if skill:
    print(skill.get_prompt())
```

## Example Skill

Here's a complete example skill for PDF processing:

**.minion/skills/pdf-helper/SKILL.md**

```markdown
---
name: pdf-helper
description: Extract and analyze text from PDF documents
license: MIT
allowed-tools:
  - bash
  - file_read
---

# PDF Helper Skill

This skill helps you work with PDF documents.

## Capabilities

- Extract text from PDFs
- Summarize PDF content
- Search within PDFs

## Usage

1. User provides a PDF file path
2. Use `pdftotext` or Python libraries to extract content
3. Process and return results

## Example Commands

```bash
# Extract text (requires poppler-utils)
pdftotext input.pdf output.txt

# Using Python
python -c "import PyPDF2; ..."
```

## Dependencies

- poppler-utils (for pdftotext)
- PyPDF2 (Python library)
```

## Best Practices

1. **Clear descriptions** - Write concise descriptions for the skill list
2. **Detailed instructions** - Provide comprehensive instructions in the body
3. **Examples** - Include practical examples
4. **Dependencies** - Document any required tools or libraries
5. **Error handling** - Describe how to handle common errors

## See Also

- [examples/skill_example.py](../examples/skill_example.py) - Working code examples
- [BashTool](../minion/tools/bash_tool.py) - For executing commands in skills
