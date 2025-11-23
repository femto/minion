# Skills System - Agent Integration Design

## 🎯 Overview

基于项目架构，Skills系统将直接集成到Agent层，而不是创建单独的SkillMinion。Agent在执行ReAct/CodeAct循环时，自动识别和使用可用的skills。

## 🏗️ Architecture

### Agent-Centric Integration

```
┌──────────────────────────────────────────────────────────────────┐
│                    Agent with Skills Support                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                BaseAgent / CodeAgent                     │   │
│  │  ┌────────────────────────────────────────────────┐     │   │
│  │  │          SkillsManager (New Component)         │     │   │
│  │  │  - Load skills from ~/.minion/skills/         │     │   │
│  │  │  - Convert skills to tool-like interface      │     │   │
│  │  │  - Inject skill context to system prompt      │     │   │
│  │  │  - Provide skill resources to executor        │     │   │
│  │  └────────────────────────────────────────────────┘     │   │
│  │                        │                                 │   │
│  │                        ▼                                 │   │
│  │  agent.tools = [default_tools]  # Skills as context     │   │
│  │                        │                                 │   │
│  │                        ▼                                 │   │
│  │            ┌───────────────────────┐                    │   │
│  │            │ Enhanced System Prompt│                    │   │
│  │            │ + Available Skills    │                    │   │
│  │            │ + Skill Instructions  │                    │   │
│  │            └───────────────────────┘                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│                   ┌────────────────┐                           │
│                   │  Brain.step()  │                           │
│                   └────────────────┘                           │
│                            │                                    │
│                            ▼                                    │
│                   ┌────────────────┐                           │
│                   │  CodeMinion    │                           │
│                   │  (route=code)  │                           │
│                   └────────────────┘                           │
│                            │                                    │
│                            ▼                                    │
│                 ┌──────────────────┐                           │
│                 │ Python Executor  │                           │
│                 │ + Skill Context  │                           │
│                 │ + Skill Scripts  │                           │
│                 └──────────────────┘                           │
│                            │                                    │
│          ┌─────────────────┼─────────────────┐                │
│          ▼                 ▼                 ▼                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │Execute Code  │  │Use Functions │  │Access Skills │        │
│  │              │  │from Skills   │  │Scripts       │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 🔑 Key Design Decisions

### 1. Skills as Context, Not Tools

**Why not make skills separate tools?**
- Skills应该是**上下文增强**，而不是tool calls
- CodeAgent已经有完整的Python executor和code-based reasoning
- Skills提供的是**知识和代码库**，而不是黑盒API

**Implementation:**
```python
# ❌ Bad: Skills as separate tool calls
agent.tools = [SearchTool(), AnalysisTool(), DataAnalysisSkill()]
# LLM needs to decide: should I call tool or write code?

# ✅ Good: Skills as context enhancement
agent = CodeAgent(
    skills=["data-analysis", "web-scraping"],
    # Skills inject their instructions and scripts into system prompt
    # Agent writes Python code using skill functions naturally
)
```

### 2. SkillsManager in Agent

SkillsManager是Agent的一个组件，负责：
- 加载和管理skills
- 增强system prompt with skill instructions
- 提供skill scripts to Python executor
- 不创建额外的tools或minions

### 3. Skill Execution Flow

```
1. User: "Analyze this CSV file"
   │
   ├─▶ Agent detects task might use data-analysis skill
   │   (based on keywords or explicit skill mention)
   │
   ├─▶ SkillsManager enhances system prompt:
   │   """
   │   You have access to the data-analysis skill.
   │
   │   Available functions:
   │   - load_dataset(filepath): Load data from CSV, Excel, etc.
   │   - basic_statistics(df): Calculate statistics
   │   - plot_distribution(df, column): Create plots
   │
   │   Instructions: [from SKILL.md]
   │
   │   To use these functions, simply import and call them in your code.
   │   """
   │
   ├─▶ CodeAgent performs ReAct/CodeAct loop:
   │   - Writes Python code using skill functions
   │   - Python executor has skill scripts in namespace
   │   - Code executes naturally
   │
   └─▶ Result returned to user
```

## 🔧 Implementation Components

### 1. SkillsManager Class

```python
# minion/tools/skills/skills_manager.py

from typing import Dict, List, Optional, Set
from pathlib import Path

class SkillsManager:
    """Manages skills for an agent"""

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        enabled_skills: Optional[List[str]] = None,
        auto_load: bool = True
    ):
        """Initialize skills manager

        Args:
            skills_dir: Directory containing skills
            enabled_skills: List of skill names to enable (None = all)
            auto_load: Automatically load all skills on init
        """
        self.loader = SkillLoader(skills_dir)
        self.enabled_skills = set(enabled_skills) if enabled_skills else None
        self.skills: Dict[str, Skill] = {}

        if auto_load:
            self.load_all_skills()

    def load_all_skills(self):
        """Load all available skills"""
        all_skills = self.loader.load_all_skills()

        # Filter by enabled_skills if specified
        if self.enabled_skills:
            self.skills = {
                name: skill
                for name, skill in all_skills.items()
                if name in self.enabled_skills
            }
        else:
            self.skills = all_skills

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name"""
        return self.skills.get(name)

    def list_skills(self) -> List[str]:
        """List available skill names"""
        return list(self.skills.keys())

    def build_system_prompt_extension(
        self,
        task: Optional[str] = None
    ) -> str:
        """Build system prompt extension with skill info

        Args:
            task: Optional task description for skill selection

        Returns:
            String to append to system prompt
        """
        if not self.skills:
            return ""

        # Select relevant skills based on task
        relevant_skills = self._select_relevant_skills(task)

        if not relevant_skills:
            return ""

        prompt = "\n\n# Available Skills\n\n"
        prompt += "You have access to specialized skills with pre-built functions.\n\n"

        for skill_name in relevant_skills:
            skill = self.skills[skill_name]
            prompt += f"## {skill.metadata.name}\n\n"
            prompt += f"{skill.metadata.description}\n\n"

            # List available functions
            if skill.scripts:
                prompt += "**Available functions:**\n"
                for script_name in skill.list_scripts():
                    # Parse and show function signatures
                    functions = self._extract_function_signatures(
                        skill.get_script(script_name)
                    )
                    for func_sig in functions:
                        prompt += f"- `{func_sig}`\n"
                prompt += "\n"

            # Add usage instructions
            prompt += f"**Instructions:** {skill.instructions}\n\n"

        prompt += "To use these skills, import and call the functions directly in your Python code.\n"

        return prompt

    def get_skill_scripts_namespace(self) -> Dict[str, str]:
        """Get all skill scripts as a namespace for Python executor

        Returns:
            Dictionary mapping module names to script content
        """
        namespace = {}

        for skill_name, skill in self.skills.items():
            for script_name, script_content in skill.scripts.items():
                # Create module name like: skill_data_analysis_analyze
                module_name = f"skill_{skill_name.replace('-', '_')}_{script_name.replace('.py', '').replace('/', '_')}"
                namespace[module_name] = script_content

        return namespace

    def _select_relevant_skills(self, task: Optional[str]) -> List[str]:
        """Select relevant skills based on task description

        Simple keyword matching for now, can be enhanced with LLM later
        """
        if not task:
            return list(self.skills.keys())

        task_lower = task.lower()
        relevant = []

        for skill_name, skill in self.skills.items():
            # Check if skill name or tags match task keywords
            if skill_name.lower() in task_lower:
                relevant.append(skill_name)
                continue

            for tag in skill.metadata.tags:
                if tag.lower() in task_lower:
                    relevant.append(skill_name)
                    break

        # If no specific match, return all skills
        return relevant if relevant else list(self.skills.keys())

    def _extract_function_signatures(self, code: str) -> List[str]:
        """Extract function signatures from Python code"""
        import ast

        try:
            tree = ast.parse(code)
            signatures = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Build signature
                    args = []
                    for arg in node.args.args:
                        args.append(arg.arg)

                    sig = f"{node.name}({', '.join(args)})"
                    signatures.append(sig)

            return signatures
        except:
            return []
```

### 2. Enhanced BaseAgent

```python
# minion/agents/base_agent.py

@dataclass
class BaseAgent:
    """Agent with skills support"""

    # ... existing fields ...

    # Skills configuration
    skills: Optional[List[str]] = None  # List of skill names to enable
    skills_dir: Optional[Path] = None   # Custom skills directory
    skills_manager: Optional[SkillsManager] = field(default=None, init=False)

    def __post_init__(self):
        """Initialize agent with skills"""
        super().__post_init__()

        # Initialize skills manager if skills are specified
        if self.skills:
            self.skills_manager = SkillsManager(
                skills_dir=self.skills_dir,
                enabled_skills=self.skills,
                auto_load=True
            )

    async def setup(self):
        """Setup agent with skills"""
        await super().setup()

        # No additional setup needed for skills
        # Skills are injected as context, not tools

    def _build_system_prompt(self, task: Optional[str] = None) -> str:
        """Build system prompt with skills context"""
        base_prompt = self.system_prompt or ""

        if self.skills_manager:
            skills_prompt = self.skills_manager.build_system_prompt_extension(task)
            return f"{base_prompt}\n{skills_prompt}"

        return base_prompt
```

### 3. Enhanced CodeAgent

```python
# minion/agents/code_agent.py

@dataclass
class CodeAgent(BaseAgent):
    """CodeAgent with skills support"""

    async def setup(self):
        """Setup CodeAgent with skills in executor"""
        await super().setup()

        # Inject skill scripts into Python executor
        if self.skills_manager and self.python_executor:
            skill_scripts = self.skills_manager.get_skill_scripts_namespace()

            # Add skill scripts to executor's namespace
            for module_name, script_content in skill_scripts.items():
                # Execute script in executor to make functions available
                try:
                    await self.python_executor.execute_async(script_content)
                    logger.info(f"Loaded skill module: {module_name}")
                except Exception as e:
                    logger.warning(f"Failed to load skill module {module_name}: {e}")

    async def execute_step(self, state: CodeAgentState, **kwargs) -> AgentResponse:
        """Execute step with skills context"""
        # Get current task
        task = state.task or (state.input.query if state.input else None)

        # Build enhanced system prompt with skills
        if self.skills_manager:
            enhanced_prompt = self._build_system_prompt(task)
            kwargs['system_prompt'] = enhanced_prompt

        # Execute normally
        return await super().execute_step(state, **kwargs)
```

### 4. Enhanced Python Executor (Optional)

Skills scripts can be pre-loaded into the executor's namespace, or executed on-demand:

```python
# In AsyncPythonExecutor

class AsyncPythonExecutor:
    def __init__(self, ..., skill_scripts: Optional[Dict[str, str]] = None):
        # ... existing init ...

        # Pre-load skill scripts
        if skill_scripts:
            for module_name, script in skill_scripts.items():
                try:
                    exec(script, self.globals_dict)
                except Exception as e:
                    logger.warning(f"Failed to pre-load skill {module_name}: {e}")
```

## 📊 Usage Examples

### Basic Usage

```python
from minion.agents import CodeAgent

# Create agent with specific skills
agent = CodeAgent(
    skills=["data-analysis", "web-scraping"],
    llm="gpt-4o"
)

await agent.setup()

# Use agent - skills are automatically available
result = await agent.run_async("Analyze this sales data CSV file")
# Agent will use data-analysis skill functions naturally
```

### With Custom Skills Directory

```python
agent = CodeAgent(
    skills=["custom-skill"],
    skills_dir=Path("./my-skills"),
    llm="gpt-4o"
)
```

### Checking Available Skills

```python
if agent.skills_manager:
    available = agent.skills_manager.list_skills()
    print(f"Available skills: {available}")

    # Get skill details
    skill = agent.skills_manager.get_skill("data-analysis")
    print(f"Description: {skill.metadata.description}")
    print(f"Scripts: {skill.list_scripts()}")
```

## 🔄 Execution Flow Example

```
User: "Analyze this CSV file and create visualizations"

1. CodeAgent.run_async() called
   │
   ├─▶ SkillsManager detects relevant skill: "data-analysis"
   │   (based on keywords: "analyze", "csv", "visualizations")
   │
   ├─▶ System prompt enhanced with skill context:
   │   """
   │   You are a code-based reasoning agent.
   │
   │   # Available Skills
   │
   │   ## data-analysis
   │   Analyze datasets and create visualizations
   │
   │   Available functions:
   │   - load_dataset(filepath): Load data from CSV, Excel, etc.
   │   - basic_statistics(df): Calculate descriptive statistics
   │   - plot_distribution(df, column): Create distribution plots
   │   - correlation_analysis(df): Compute correlations
   │
   │   Instructions: When user requests data analysis...
   │   [full skill instructions from SKILL.md]
   │
   │   To use these skills, import and call functions in your code.
   │   """
   │
   ├─▶ CodeAgent performs ReAct loop:
   │
   │   Step 1: Agent writes code
   │   ```python
   │   # Load the dataset
   │   df = load_dataset('data.csv')
   │
   │   # Get basic statistics
   │   stats = basic_statistics(df)
   │   print(stats)
   │   ```
   │
   │   Step 2: Python executor runs code
   │   - Functions from data-analysis skill are available in namespace
   │   - Code executes successfully
   │
   │   Step 3: Agent continues
   │   ```python
   │   # Create visualizations
   │   plot_distribution(df, 'sales')
   │   save_plot('sales_distribution.png')
   │   ```
   │
   └─▶ Final result returned with analysis and visualizations
```

## 🚀 Migration Path

### Phase 1: Basic Integration (Current)
- ✅ SkillLoader and Skill classes
- [ ] SkillsManager implementation
- [ ] BaseAgent skills integration
- [ ] CodeAgent skills integration

### Phase 2: Enhanced Features
- [ ] Smart skill selection based on task
- [ ] Skill dependency management
- [ ] Skill versioning
- [ ] Skill testing framework

### Phase 3: Advanced Features
- [ ] LLM-based skill selection
- [ ] Dynamic skill loading
- [ ] Skill marketplace integration
- [ ] Collaborative skill development

## 📝 Benefits of This Approach

1. **Natural Integration**: Skills work seamlessly with CodeAgent's code-based reasoning
2. **No Extra Tools**: Skills don't pollute the tool namespace
3. **Flexible**: Skills can be enabled/disabled per agent instance
4. **Reusable**: Skills are just Python functions that can be called naturally
5. **Extensible**: Easy to add new skills without changing agent code
6. **Testable**: Skills can be tested independently
7. **Documentation**: Skill instructions guide the agent naturally

## 🔍 Comparison with Other Approaches

### Approach 1: Skills as Tools (❌ Rejected)
```python
agent.tools = [DataAnalysisSkillTool(), WebScrapingSkillTool()]
# Problem: Agent needs to decide between writing code and calling tools
# Adds complexity and reduces flexibility
```

### Approach 2: Separate SkillMinion (❌ Rejected)
```python
brain.route = 'skill'  # Routes to SkillMinion
# Problem: Extra layer of complexity
# Duplicates Python execution logic
# Harder to integrate with existing CodeAgent
```

### Approach 3: Skills as Context (✅ Adopted)
```python
agent = CodeAgent(skills=["data-analysis"])
# Benefits: Natural, flexible, reusable
# Agent writes code using skill functions
# No extra routing or tool management
```
