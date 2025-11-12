# Agent Route Parameter 使用指南

## 概述

现在 `BaseAgent` 和 `CodeAgent` 的 `run()` 和 `run_async()` 方法都支持 `route` 参数，允许你在运行时动态指定使用哪个 minion（推理策略）。

## 什么是 Route？

Route 是指定使用哪个 minion（worker）来处理任务的方式。不同的 minion 有不同的推理策略：

- **`code`**: 使用 CodeMinion，通过 Thought -> Code -> Observation 循环来解决问题
- **`cot`**: 使用 CotMinion (Chain of Thought)，让 LLM 逐步思考
- **`native`**: 使用 NativeMinion，直接询问 LLM
- **`plan`**: 使用 PlanMinion，将问题分解为子任务
- **`python`**: 使用 PythonMinion，编写 Python 代码解决问题
- 等等...

## 使用方法

### 1. BaseAgent 使用 route 参数

```python
from minion.agents.base_agent import BaseAgent
from minion.providers import create_llm_provider
from minion.config import config

# 创建 agent
llm = create_llm_provider(config.models.get("default"))
agent = BaseAgent(name="my_agent", llm=llm)
await agent.setup()

# 使用 'cot' route
result = await agent.run_async(
    task="What is 25 * 37?",
    route="cot",
    max_steps=1
)

# 使用 'native' route
result = await agent.run_async(
    task="What is the capital of France?",
    route="native",
    max_steps=1
)

# 使用 'code' route
result = await agent.run_async(
    task="Calculate the sum of numbers from 1 to 100",
    route="code",
    max_steps=3
)
```

### 2. CodeAgent 使用 route 参数

CodeAgent 默认使用 `'code'` route，但你可以通过 `route` 参数覆盖：

```python
from minion.agents.code_agent import CodeAgent

# 创建 CodeAgent
agent = CodeAgent(name="code_agent", llm=llm)
await agent.setup()

# 使用默认的 'code' route
result = await agent.run_async(
    task="Calculate factorial of 10"
)

# 覆盖为 'cot' route
result = await agent.run_async(
    task="What is 15 * 23?",
    route="cot",
    max_steps=1
)

# 使用 'plan' route
result = await agent.run_async(
    task="Create a simple Python function to calculate factorial",
    route="plan",
    max_steps=5
)
```

### 3. 同步接口

`run()` 方法也支持 `route` 参数：

```python
# 同步调用
result = agent.run(
    task="What is 12 + 34?",
    route="cot",
    max_steps=1
)
```

### 4. 与 Input 对象一起使用

```python
from minion.main.input import Input

# 创建 Input 对象（不指定 route）
input_obj = Input(query="What is 5 * 6?")

# 通过 route 参数指定
result = await agent.run_async(
    task=input_obj,
    route="cot",
    max_steps=1
)

# 创建 Input 对象（指定 route）
input_obj_with_route = Input(query="What is 7 * 8?", route="native")

# route 参数会覆盖 Input 对象中的 route
result = await agent.run_async(
    task=input_obj_with_route,
    route="cot",  # 这会覆盖 Input 中的 "native"
    max_steps=1
)
```

## Route 优先级

Route 的设置遵循以下优先级（从高到低）：

1. **`run_async()` 的 `route` 参数** - 最高优先级
2. **`Input` 对象的 `route` 属性** - 中等优先级
3. **Agent 的默认行为** - 最低优先级
   - `BaseAgent`: 由 RouteMinion 智能选择
   - `CodeAgent`: 默认使用 `'code'`

## 完整示例

```python
import asyncio
from minion.agents.base_agent import BaseAgent
from minion.agents.code_agent import CodeAgent
from minion.providers import create_llm_provider
from minion.config import config
from minion.main.input import Input

async def main():
    # 创建 LLM provider
    llm = create_llm_provider(config.models.get("default"))
    
    # 示例 1: BaseAgent 使用不同的 routes
    agent = BaseAgent(name="base_agent", llm=llm)
    await agent.setup()
    
    # 使用 cot route
    result = await agent.run_async(
        task="Explain how photosynthesis works",
        route="cot",
        max_steps=1
    )
    print(f"CoT result: {result}")
    
    # 使用 code route
    result = await agent.run_async(
        task="Calculate the fibonacci sequence up to 10 terms",
        route="code",
        max_steps=3
    )
    print(f"Code result: {result}")
    
    await agent.close()
    
    # 示例 2: CodeAgent 覆盖默认 route
    code_agent = CodeAgent(name="code_agent", llm=llm)
    await code_agent.setup()
    
    # 使用默认的 code route
    result = await code_agent.run_async(
        task="Sort a list [3, 1, 4, 1, 5, 9, 2, 6]"
    )
    print(f"Default code route: {result}")
    
    # 覆盖为 cot route
    result = await code_agent.run_async(
        task="What is the difference between a list and a tuple in Python?",
        route="cot",
        max_steps=1
    )
    print(f"Overridden to CoT: {result}")
    
    await code_agent.close()
    
    # 示例 3: 使用 Input 对象
    agent = BaseAgent(name="input_agent", llm=llm)
    await agent.setup()
    
    # Input 对象 + route 参数
    input_obj = Input(
        query="Calculate the area of a circle with radius 5",
        route="native"  # 这会被下面的 route 参数覆盖
    )
    
    result = await agent.run_async(
        task=input_obj,
        route="code",  # 覆盖 Input 中的 "native"
        max_steps=3
    )
    print(f"Input with route override: {result}")
    
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## 可用的 Routes

以下是常用的 routes（minions）：

| Route | Minion | 描述 |
|-------|--------|------|
| `code` | CodeMinion | 使用 Thought -> Code -> Observation 循环，适合需要编程的任务 |
| `cot` | CotMinion | Chain of Thought，逐步推理，适合需要解释的任务 |
| `native` | NativeMinion | 直接询问 LLM，适合简单问答 |
| `plan` | PlanMinion | 将任务分解为子任务，适合复杂任务 |
| `python` | PythonMinion | 编写 Python 代码解决问题 |
| `dcot` | DcotMinion | Dynamic Chain of Thought |

## 注意事项

1. **Route 必须存在**: 指定的 route 必须在 `MINION_REGISTRY` 中注册，否则会抛出异常
2. **CodeAgent 的默认行为**: CodeAgent 默认使用 `'code'` route，除非显式指定其他 route
3. **BaseAgent 的智能选择**: 如果不指定 route，BaseAgent 会通过 RouteMinion 智能选择合适的 minion
4. **Route 覆盖**: `run_async()` 的 `route` 参数会覆盖 `Input` 对象中的 `route` 属性

## 调试技巧

如果想查看实际使用的 route，可以查看日志：

```python
import logging
logging.basicConfig(level=logging.INFO)

# 运行 agent 时会看到类似的日志：
# INFO:minion.main.worker:Use enforced route: code
# INFO:minion.main.worker:Choosing Route: cot using default brain.llm
```

## 总结

通过 `route` 参数，你可以：

1. ✅ 在运行时动态选择推理策略
2. ✅ 覆盖 agent 的默认行为
3. ✅ 为不同类型的任务使用最合适的 minion
4. ✅ 灵活控制任务执行方式

这使得 agent 的使用更加灵活和强大！
