# Think in Code Examples

这个目录包含了Think in Code功能的完整演示和示例，展示了Meta工具在不同场景下的使用。

## 📁 文件结构

```
think_in_code/
├── __init__.py                 # 包初始化文件
├── README.md                   # 本文件
├── basic_demo.py              # 基础Meta工具演示
├── code_execution_demo.py     # 代码执行中的Meta工具使用
├── real_code_agent_demo.py    # 真实CodeAgent集成演示
└── run_demos.py               # 完整演示运行器
```

## 🚀 快速开始

### 运行完整演示
```bash
# 交互式模式（推荐）
python examples/think_in_code/run_demos.py

# 运行所有演示
python examples/think_in_code/run_demos.py --mode all

# 快速测试
python examples/think_in_code/run_demos.py --mode quick
```

### 单独运行演示
```bash
# 基础Meta工具演示
python examples/think_in_code/basic_demo.py

# 代码执行演示
python examples/think_in_code/code_execution_demo.py

# 真实CodeAgent演示
python examples/think_in_code/real_code_agent_demo.py
```

## 📋 演示内容

### 1. 基础Meta工具演示 (`basic_demo.py`)

展示三个核心Meta工具的基础功能：

- **ThinkInCodeTool**: 内部思考和推理分析
- **PlanTool**: 任务规划和步骤管理
- **ReflectionTool**: 自我反思和学习改进

**特点**:
- 完整的工具功能演示
- 详细的分析和总结
- 易于理解的示例场景

### 2. 代码执行演示 (`code_execution_demo.py`)

展示在AsyncPythonExecutor中使用Meta工具：

- 智能数据分析程序
- 算法开发中的思考过程
- 代码中透明调用Meta工具

**特点**:
- 真实的代码执行环境
- 完整的思考-规划-反思流程
- 自动的算法选择和优化

### 3. 真实CodeAgent演示 (`real_code_agent_demo.py`)

展示具有思考能力的CodeAgent：

- 自动任务复杂度评估
- 智能的思考提示注入
- 不同复杂度任务的处理策略

**特点**:
- 真实的AI Agent集成
- 自适应的思考策略
- 完整的端到端演示

## 🧠 Meta工具详解

### ThinkInCodeTool - 内部思考工具

**用途**: 支持agent在代码执行中进行深度思考和推理

**核心功能**:
- 思考内容分析和分类
- 复杂度评估
- 情感色调识别
- 关键概念提取
- 推理模式识别
- 趋势分析

**使用示例**:
```python
_meta_call("think", 
    "这是一个复杂的数学问题，需要系统性方法",
    {"complexity": "high", "domain": "mathematics"},
    "high"
)
```

### PlanTool - 任务规划工具

**用途**: 提供结构化的任务分解和执行跟踪

**核心功能**:
- 创建详细执行计划
- 步骤进度跟踪
- 计划动态更新
- 完成度统计
- 上下文保持

**使用示例**:
```python
# 创建计划
_meta_call("plan", "create", {
    "title": "算法优化项目",
    "steps": ["分析", "设计", "实现", "测试", "优化"]
})

# 完成步骤
_meta_call("plan", "complete_step", {
    "result": "分析完成",
    "notes": "识别了3个性能瓶颈"
})
```

### ReflectionTool - 自我反思工具

**用途**: 实现深度的自我评估和持续学习

**核心功能**:
- 多维度反思分析
- 学习点提取
- 改进建议生成
- 决策质量评估
- 经验总结

**使用示例**:
```python
_meta_call("reflect", "result", {
    "final_solution": "优化后的算法",
    "efficiency_gain": "40%",
    "method": "缓存优化"
})
```

## 🎯 应用场景

### 1. 复杂算法开发
- 自动算法选择和优化
- 性能分析和改进建议
- 复杂度评估和权衡

### 2. 数据科学项目
- 数据质量评估
- 分析方法选择
- 结果解释和验证

### 3. 系统架构设计
- 架构决策记录
- 技术选型分析
- 性能权衡评估

### 4. 代码调试和优化
- 错误模式识别
- 调试策略制定
- 性能瓶颈分析

### 5. 自动化测试
- 测试用例生成
- 覆盖率分析
- 质量评估

## 🔧 技术实现

### 状态感知机制
Meta工具通过调用栈自动发现agent上下文：
- Brain实例访问
- 当前state字典获取
- Input对象引用
- Agent实例识别

### 透明调用机制
使用`_meta_call()`函数透明调用Meta工具：
- 对LLM完全不可见
- 在代码中自然调用
- 自动异步处理
- 状态自动传递

### 集成架构
Meta工具深度集成到执行环境：
- AsyncPythonExecutor自动注册
- Brain.step()状态传递
- BaseAgent兼容性
- 记忆系统集成

## 🛠️ 扩展开发

### 创建自定义Meta工具

```python
from minion.tools.agent_state_aware_tool import AgentStateAwareTool

class CustomMetaTool(AgentStateAwareTool):
    name = "custom_tool"
    description = "自定义Meta工具"
    
    async def forward(self, *args, **kwargs):
        # 获取agent状态
        brain = self.get_brain()
        state = self.get_agent_state()
        
        # 实现自定义逻辑
        result = process_custom_logic(args, kwargs, state)
        
        return result
```

### 注册自定义工具

```python
# 在AsyncPythonExecutor中注册
executor.send_tools({
    "my_custom_tool": CustomMetaTool()
})

# 在代码中使用
_meta_call("my_custom_tool", param1, param2=value)
```

## 📚 相关文档

- [Think in Code 使用指南](../../THINK_IN_CODE_GUIDE.md)
- [Meta工具API文档](../../minion/tools/)
- [CodeAgent集成文档](../../minion/agents/)

## 🤝 贡献指南

欢迎贡献新的演示和示例：

1. 创建新的演示文件
2. 添加到`run_demos.py`中
3. 更新本README文档
4. 确保代码质量和文档完整性

## 📄 许可证

本项目遵循与主项目相同的许可证。