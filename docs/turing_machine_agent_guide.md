# Turing Machine Agent 使用指南

## 概述

Turing Machine Agent 是一个基于图灵机概念的 LLM 代理实现，它将 AI 代理建模为状态机，具有明确的状态转换、记忆系统和计划执行能力。

## 核心概念

### 1. 代理状态 (AgentState)
- `PLANNING`: 制定计划阶段
- `EXECUTING`: 执行任务阶段  
- `REFLECTING`: 反思总结阶段
- `WAITING`: 等待输入阶段
- `HALTED`: 任务完成/停止
- `ERROR`: 错误状态

### 2. 记忆系统 (Memory)
- **工作记忆** (working_memory): 短期任务相关信息
- **情节记忆** (episodic_memory): 执行步骤历史记录
- **语义记忆** (semantic_memory): 长期知识存储

### 3. 计划系统 (Plan)
- 分层计划结构
- 步骤化任务分解
- 动态计划调整

## 快速开始

### 基础使用

```python
import asyncio
from minion.agents import create_turing_machine_agent
from minion.main.input import Input

async def basic_example():
    # 创建代理（使用默认LLM配置）
    agent = create_turing_machine_agent(name="my_agent")
    
    # 执行任务
    task = "帮我制定一个学习Python的计划"
    result = await agent.run(task, max_steps=5)
    
    print(f"结果: {result}")

asyncio.run(basic_example())
```

### 使用特定模型

```python
# 使用配置中的特定模型
agent = create_turing_machine_agent(
    model_name="gpt-4o-mini",  # 需要在config.yaml中配置
    name="specialized_agent"
)
```

### 通过BaseAgent接口使用

```python
from minion.main.input import Input

async def step_by_step():
    agent = create_turing_machine_agent()
    task_input = Input(query="解释什么是机器学习")
    
    # 执行单步
    response, score, terminated, truncated, info = await agent.step(
        task_input, 
        debug=True
    )
    
    print(f"响应: {response}")
    print(f"置信度: {score}")
    print(f"是否完成: {terminated}")
    print(f"额外信息: {info}")
```

## 高级用法

### 自定义记忆和计划

```python
from minion.agents import AgentInput, Memory, Plan, AgentState

async def advanced_example():
    agent = create_turing_machine_agent()
    
    # 初始化记忆
    memory = Memory()
    memory.update_working("task_type", "programming")
    memory.update_semantic("user_preference", "detailed_explanations")
    
    # 创建详细计划
    plan = Plan(goal="创建Python Web应用")
    plan.add_step("选择框架", {"options": ["Flask", "Django", "FastAPI"]})
    plan.add_step("设计架构", {"patterns": ["MVC", "微服务"]})
    plan.add_step("实现功能", {"features": ["用户认证", "数据库"]})
    plan.add_step("测试部署", {"environment": "Docker"})
    
    # 创建代理输入
    agent_input = AgentInput(
        goal="创建一个完整的Python Web应用",
        plan=plan,
        memory=memory,
        prompt="请帮我创建一个用户管理系统的Web应用",
        context={"tech_stack": "Python", "complexity": "intermediate"}
    )
    
    # 逐步执行
    outputs = []
    for i in range(10):  # 最多10步
        if agent.turing_machine.current_state == AgentState.HALTED:
            break
            
        output = await agent.turing_machine.step(agent_input, debug=True)
        outputs.append(output)
        
        if output.halt_condition:
            break
    
    print(f"执行了 {len(outputs)} 步")
    return outputs
```

### 流式执行监控

```python
async def streaming_example():
    agent = create_turing_machine_agent()
    
    task = "分析人工智能的发展趋势"
    
    # 使用流式接口
    async for intermediate_result in agent.run(task, streaming=True, max_steps=5):
        print(f"中间结果: {intermediate_result}")
        # 可以在这里进行实时处理或显示
```

## 配置选项

### LLM Provider 配置

Turing Machine Agent 支持使用 minion 配置系统中的任何 LLM provider：

```python
# 方式1: 使用模型名称
agent = create_turing_machine_agent(model_name="gpt-4o-mini")

# 方式2: 使用LLMConfig对象
from minion.configs.config import LLMConfig
config = LLMConfig(
    api_type="openai",
    api_key="your-key",
    model="gpt-4",
    temperature=0.7
)
agent = create_turing_machine_agent(llm_config=config)

# 方式3: 直接传入provider实例
from minion.providers.openai_provider import OpenAIProvider
provider = OpenAIProvider(config)
agent = TuringMachineAgent(llm_config=provider)
```

### 代理参数

```python
agent = create_turing_machine_agent(
    model_name="gpt-4o-mini",
    name="custom_agent",
    max_steps=20,  # 最大执行步数
    user_id="user123",  # 用户ID（用于记忆系统）
    session_id="session456"  # 会话ID
)
```

## 最佳实践

### 1. 合理设置最大步数
```python
# 简单任务
result = await agent.run(task, max_steps=3)

# 复杂任务
result = await agent.run(task, max_steps=15)
```

### 2. 使用调试模式
```python
# 开启调试以查看详细执行过程
output = await agent.turing_machine.step(agent_input, debug=True)
```

### 3. 错误处理
```python
try:
    result = await agent.run(task, max_steps=10)
except Exception as e:
    print(f"执行出错: {e}")
    # 可以重置代理状态
    agent.reset()
```

### 4. 状态监控
```python
# 检查当前状态
print(f"当前状态: {agent.turing_machine.current_state}")
print(f"执行步数: {agent.turing_machine.step_count}")

# 检查记忆内容
print(f"工作记忆: {agent.agent_memory.working_memory}")
print(f"历史记录: {len(agent.agent_memory.episodic_memory)}")
```

## 与现有系统集成

### 与 BaseAgent 兼容
TuringMachineAgent 继承自 BaseAgent，完全兼容现有的代理系统：

```python
# 可以像使用其他代理一样使用
from minion.agents import BaseAgent

def use_any_agent(agent: BaseAgent):
    return agent.run("执行某个任务")

# TuringMachineAgent 可以直接传入
turing_agent = create_turing_machine_agent()
result = await use_any_agent(turing_agent)
```

### 与工具系统集成
```python
from minion.tools import SomeCustomTool

agent = create_turing_machine_agent()
agent.add_tool(SomeCustomTool())

# 工具会自动在执行过程中可用
result = await agent.run("使用工具完成任务")
```

## 故障排除

### 常见问题

1. **模型配置错误**
   ```python
   # 确保模型在config.yaml中正确配置
   from minion.configs.config import config
   print(config.models.keys())  # 查看可用模型
   ```

2. **无限循环**
   ```python
   # 设置合理的最大步数
   result = await agent.run(task, max_steps=10)
   ```

3. **记忆溢出**
   ```python
   # 定期重置代理状态
   agent.reset()
   ```

## 示例项目

完整的示例代码请参考 `examples/turing_machine_demo.py`，包含：
- 基础用法演示
- 逐步执行监控
- BaseAgent接口使用
- 多模型配置测试

运行示例：
```bash
cd examples
python turing_machine_demo.py
``` 