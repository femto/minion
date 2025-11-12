# Route Parameter Quick Reference

## 快速开始

```python
# BaseAgent 使用 route
result = await agent.run_async(task="Your task", route="code")

# CodeAgent 覆盖默认 route
result = await code_agent.run_async(task="Your task", route="cot")

# 同步接口
result = agent.run(task="Your task", route="native")
```

## 常用 Routes

| Route | 适用场景 | 示例 |
|-------|---------|------|
| `code` | 需要编程解决的问题 | 计算、数据处理、算法实现 |
| `cot` | 需要逐步推理的问题 | 数学题、逻辑推理、解释说明 |
| `native` | 简单问答 | 知识查询、定义解释 |
| `plan` | 复杂任务分解 | 多步骤任务、项目规划 |
| `python` | Python 代码生成 | 编写函数、脚本生成 |

## Route 优先级

```
run_async(route="X")  >  Input(route="Y")  >  Agent 默认
     (最高)                  (中等)              (最低)
```

## 完整示例

```python
import asyncio
from minion.agents.base_agent import BaseAgent
from minion.providers import create_llm_provider
from minion.config import config

async def main():
    llm = create_llm_provider(config.models.get("default"))
    agent = BaseAgent(name="my_agent", llm=llm)
    await agent.setup()
    
    # 使用 code route
    result = await agent.run_async(
        task="Calculate fibonacci(10)",
        route="code",
        max_steps=3
    )
    print(result)
    
    await agent.close()

asyncio.run(main())
```

## API 签名

### BaseAgent

```python
def run(
    task: Optional[Union[str, Input]] = None,
    state: Optional[AgentState] = None,
    max_steps: Optional[int] = None,
    reset: bool = False,
    llm: Optional[str] = None,
    route: Optional[str] = None,  # 新增
    **kwargs
) -> Any

async def run_async(
    task: Optional[Union[str, Input]] = None,
    state: Optional[AgentState] = None,
    max_steps: Optional[int] = None,
    reset: bool = False,
    stream: bool = False,
    llm: Optional[str] = None,
    route: Optional[str] = None,  # 新增
    **kwargs
) -> Any
```

### CodeAgent

```python
def run(
    task: Optional[Union[str, Input]] = None,
    max_steps: Optional[int] = None,
    reset: bool = False,
    route: Optional[str] = None,  # 新增
    **kwargs
) -> Any

async def run_async(
    task: Optional[Union[str, Input]] = None,
    max_steps: Optional[int] = None,
    reset: bool = False,
    stream: bool = False,
    route: Optional[str] = None,  # 新增
    **kwargs
) -> Any
```

## 常见用法

### 1. 动态切换策略

```python
# 根据任务类型选择不同的 route
if task_requires_code:
    result = await agent.run_async(task, route="code")
elif task_requires_reasoning:
    result = await agent.run_async(task, route="cot")
else:
    result = await agent.run_async(task, route="native")
```

### 2. 覆盖 Input 的 route

```python
input_obj = Input(query="Task", route="native")
# 覆盖为 code
result = await agent.run_async(input_obj, route="code")
```

### 3. CodeAgent 使用非 code route

```python
code_agent = CodeAgent(...)
# 使用 cot 而不是默认的 code
result = await code_agent.run_async(task, route="cot")
```

## 调试

查看实际使用的 route：

```python
import logging
logging.basicConfig(level=logging.INFO)

# 日志会显示：
# INFO:minion.main.worker:Use enforced route: code
```

## 注意事项

- ✅ route 参数是可选的
- ✅ 不指定 route 时使用默认行为
- ✅ route 必须在 MINION_REGISTRY 中注册
- ✅ CodeAgent 默认使用 'code' route
- ✅ BaseAgent 会智能选择 route（如果不指定）

## 更多信息

- 详细指南: `docs/agent_route_parameter_guide.md`
- 调用链路分析: `docs/code_minion_call_chain_analysis.md`
- 测试示例: `examples/test_agent_route_parameter.py`
