# Minion Skills System Design

## 🎯 Overview

这是一个受Claude Skills启发的开源技能系统实现，允许用户定义、加载和执行专门的AI技能。

## 📚 参考项目

- **BandarLabs/open-skills**: 本地沙箱执行环境，提供VM级别隔离
- **numman-ali/openskills**: 通用skill loader，CLI管理工具

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Minion Skills System                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Skill Loader │───▶│ Skill Parser │───▶│  Skill Tool  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                                         │         │
│         │                                         ▼         │
│         │                               ┌──────────────┐   │
│         └──────────────────────────────▶│ Brain Router │   │
│                                         └──────────────┘   │
│                                                 │           │
│                                                 ▼           │
│                                       ┌──────────────┐     │
│                                       │ SkillMinion  │     │
│                                       └──────────────┘     │
│                                                 │           │
│                       ┌─────────────────────────┼──────────┤
│                       ▼                         ▼           │
│              ┌────────────────┐      ┌────────────────┐   │
│              │ Python Executor│      │ File Operations│   │
│              └────────────────┘      └────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 📝 Skill Definition Format

### Directory Structure

```
~/.minion/skills/
├── data-analysis/
│   ├── SKILL.md              # Skill definition and instructions
│   ├── scripts/
│   │   ├── analyze.py
│   │   └── visualize.py
│   ├── references/
│   │   └── examples.md
│   └── requirements.txt      # Optional Python dependencies
│
└── web-scraping/
    ├── SKILL.md
    └── scripts/
        └── scrape.py
```

### SKILL.md Format

```markdown
---
name: data-analysis
description: Analyze datasets and create visualizations
version: 1.0.0
author: Your Name
tags: [data, analysis, visualization]
requirements:
  - pandas>=2.0.0
  - matplotlib>=3.7.0
---

# Data Analysis Skill

## Description
This skill helps analyze datasets and create meaningful visualizations.

## Usage Instructions
When user requests data analysis:
1. Load the dataset using pandas
2. Perform basic statistical analysis
3. Create appropriate visualizations
4. Save results to output directory

## Available Resources
- **scripts/analyze.py**: Main analysis functions
- **scripts/visualize.py**: Visualization utilities
- **references/examples.md**: Usage examples

## Example Prompts
- "Analyze this CSV file and show me the trends"
- "Create a visualization of the sales data"
- "Find correlations in the dataset"
```

## 🔧 Core Components

### 1. SkillLoader (`minion/tools/skills/skill_loader.py`)

负责从文件系统加载和解析技能：

```python
@dataclass
class SkillMetadata:
    """Skill metadata from YAML frontmatter"""
    name: str
    description: str
    version: str
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)

@dataclass
class Skill:
    """Complete skill definition"""
    metadata: SkillMetadata
    instructions: str  # Markdown content after frontmatter
    scripts: Dict[str, str]  # filename -> content
    references: Dict[str, str]  # filename -> content
    assets: Dict[str, bytes]  # filename -> binary content
    skill_dir: Path

class SkillLoader:
    """Load skills from filesystem"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or Path.home() / ".minion" / "skills"

    def load_skill(self, skill_name: str) -> Skill:
        """Load a single skill by name"""

    def load_all_skills(self) -> Dict[str, Skill]:
        """Load all available skills"""

    def install_skill(self, source: str, skill_name: Optional[str] = None):
        """Install skill from GitHub or local path"""
```

### 2. SkillTool (`minion/tools/skills/skill_tool.py`)

将Skill转换为可执行的Tool：

```python
class SkillTool(AsyncBaseTool):
    """Executable skill tool"""

    def __init__(self, skill: Skill):
        self.skill = skill
        self.name = skill.metadata.name
        self.description = skill.metadata.description

    async def forward(self, task: str, **kwargs) -> Dict[str, Any]:
        """Execute the skill"""
        # 1. 准备执行环境
        # 2. 注入skill instructions到context
        # 3. 执行相关脚本
        # 4. 返回结果
```

### 3. SkillMinion (`minion/main/skill_minion.py`)

专门执行技能任务的Minion：

```python
class SkillMinion:
    """Minion specialized for skill execution"""

    def __init__(
        self,
        llm: LLMProvider,
        skills: List[Skill],
        python_executor: Optional[PythonExecutor] = None
    ):
        self.llm = llm
        self.skills = {s.metadata.name: s for s in skills}
        self.executor = python_executor or AsyncPythonExecutor()

    async def execute(
        self,
        task: str,
        skill_name: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """Execute task using appropriate skill"""

        # 1. 选择合适的skill（如果未指定）
        if not skill_name:
            skill_name = await self._select_skill(task)

        # 2. 加载skill context
        skill = self.skills[skill_name]
        context = self._prepare_skill_context(skill)

        # 3. 构造messages with skill instructions
        messages = self._build_messages(task, context)

        # 4. 执行LLM + tools
        response = await self.llm.chat_async(messages, tools=self._get_skill_tools(skill))

        # 5. 处理tool calls（如Python execution）
        if response.tool_calls:
            results = await self._execute_tool_calls(response.tool_calls, skill)
            return AgentResponse(
                output=results,
                messages=messages + [response],
                terminated=True
            )

        return AgentResponse(
            output=response.content,
            messages=messages + [response],
            terminated=True
        )
```

### 4. Brain Integration (`minion/main/brain.py`)

将技能系统集成到Brain路由：

```python
class Brain:
    def __init__(self, ...):
        # ... existing code ...

        # Load skills
        self.skill_loader = SkillLoader()
        self.skills = self.skill_loader.load_all_skills()

        # Create skill minion
        self.skill_minion = SkillMinion(
            llm=self.llm,
            skills=list(self.skills.values())
        )

    async def step(self, messages, route: Optional[str] = None, **kwargs):
        # ... existing routing logic ...

        if route == 'skill':
            # Use skill minion
            skill_name = kwargs.get('skill_name')
            return await self.skill_minion.execute(
                task=messages[-1].content,
                skill_name=skill_name,
                **kwargs
            )

        # ... rest of routing logic ...
```

## 🔄 Execution Flow

```
1. User: "Analyze this CSV file using data-analysis skill"
   │
   ├─▶ Brain receives task with route='skill'
   │
   ├─▶ SkillMinion loads 'data-analysis' skill
   │   │
   │   ├─▶ Parse SKILL.md to get instructions
   │   ├─▶ Load scripts/analyze.py content
   │   └─▶ Prepare execution context
   │
   ├─▶ Construct messages with skill context:
   │   [
   │     SystemMessage(skill instructions),
   │     UserMessage(task),
   │     ToolDefinitions([execute_python, read_file, write_file])
   │   ]
   │
   ├─▶ LLM generates response with tool calls
   │
   ├─▶ Execute tool calls:
   │   ├─▶ execute_python(code from analyze.py)
   │   ├─▶ read_file(data.csv)
   │   └─▶ write_file(results.json)
   │
   └─▶ Return final results to user
```

## 🛠️ Tools Available in Skills

SkillMinion提供以下工具给技能使用：

1. **execute_python**: 执行Python代码
2. **read_file**: 读取文件
3. **write_file**: 写入文件
4. **list_skill_files**: 列出skill中的可用文件
5. **get_skill_file**: 获取skill文件内容

## 📦 Installation & Usage

### Installing a Skill

```bash
# From GitHub
minion skill install https://github.com/user/skill-name

# From local directory
minion skill install /path/to/skill

# List installed skills
minion skill list

# Show skill details
minion skill info data-analysis
```

### Using Skills in Code

```python
from minion import Brain, Input

# Create brain with skills
brain = Brain(llm="gpt-4o")

# Use specific skill
result = await brain.step(
    messages=[UserMessage("Analyze sales.csv")],
    route='skill',
    skill_name='data-analysis'
)

# Auto-select skill
result = await brain.step(
    messages=[UserMessage("Scrape data from example.com")],
    route='skill'  # Will auto-select web-scraping skill
)
```

### Creating Custom Skills

```bash
# Create new skill
minion skill create my-skill

# This creates:
# ~/.minion/skills/my-skill/
#   ├── SKILL.md (template)
#   ├── scripts/
#   └── references/
```

## 🔐 Security Considerations

### Sandbox Isolation (Future Enhancement)

借鉴BandarLabs/open-skills的沙箱机制：

1. **Phase 1 (Current)**: 使用AsyncPythonExecutor的现有隔离
2. **Phase 2**: 添加Docker容器隔离
3. **Phase 3**: VM级别隔离（参考open-skills）

### Permission Model

```yaml
# In SKILL.md
permissions:
  filesystem:
    - read: ["/tmp", "~/.minion/data"]
    - write: ["/tmp"]
  network:
    - allow_domains: ["api.example.com"]
  python:
    - allowed_modules: ["pandas", "numpy", "matplotlib"]
    - blocked_modules: ["os.system", "subprocess"]
```

## 🚀 Roadmap

### Phase 1: Basic Implementation (Current)
- [x] Design skill format
- [ ] Implement SkillLoader
- [ ] Implement SkillTool
- [ ] Implement SkillMinion
- [ ] Brain integration
- [ ] Basic CLI commands

### Phase 2: Enhanced Features
- [ ] Skill marketplace
- [ ] Dependency management
- [ ] Skill testing framework
- [ ] Skill documentation generator

### Phase 3: Advanced Isolation
- [ ] Docker container execution
- [ ] Resource limits (CPU, memory)
- [ ] Network isolation
- [ ] VM-level isolation

## 📚 Example Skills

### 1. Data Analysis Skill
- 数据清洗和预处理
- 统计分析
- 可视化生成

### 2. Web Scraping Skill
- 网页抓取
- 数据提取
- 结构化存储

### 3. Code Review Skill
- 代码质量检查
- 最佳实践建议
- 安全漏洞扫描

### 4. Document Generation Skill
- Markdown报告生成
- PDF导出
- 图表嵌入

## 🤝 Contributing

欢迎贡献新的技能！请参考 [CONTRIBUTING.md](../CONTRIBUTING.md)

## 📄 License

Same as Minion project license.
