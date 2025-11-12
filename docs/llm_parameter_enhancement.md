# LLM 参数增强说明

## 问题

之前的 `_resolve_llm` 方法签名为 `llm_name: str`，只能接受字符串参数。但实际使用中，用户可能直接传入 `BaseProvider` 实例，导致类型不匹配。

## 解决方案

### 1. 更新 `_resolve_llm` 方法

**修改前：**
```python
def _resolve_llm(self, llm_name: str) -> Optional[BaseProvider]:
    if llm_name == "primary":
        return self.llm
    elif self.llms and llm_name in self.llms:
        return self.llms[llm_name]
    else:
        return None
```

**修改后：**
```python
def _resolve_llm(self, llm: Union[str, BaseProvider]) -> Optional[BaseProvider]:
    """
    Resolve LLM name or provider to BaseProvider instance
    
    Args:
        llm: LLM name ("primary", "code", "math", etc.) or BaseProvider instance
        
    Returns:
        BaseProvider instance or None if not found
    """
    # If already a BaseProvider instance, return it directly
    if isinstance(llm, BaseProvider):
        return llm
    
    # Otherwise treat as string name
    if llm == "primary":
        return self.llm
    elif self.llms and llm in self.llms:
        return self.llms[llm]
    else:
        return None
```

### 2. 更新方法签名

所有使用 `llm` 参数的方法都更新为支持 `Union[str, BaseProvider]`：

#### BaseAgent.run()
```python
def run(
    task: Optional[Union[str, Input]] = None,
    state: Optional[AgentState] = None,
    max_steps: Optional[int] = None,
    reset: bool = False,
    llm: Optional[Union[str, BaseProvider]] = None,  # 支持字符串或实例
    route: Optional[str] = None,
    **kwargs
) -> Any
```

#### BaseAgent.run_async()
```python
async def run_async(
    task: Optional[Union[str, Input]] = None,
    state: Optional[AgentState] = None,
    max_steps: Optional[int] = None,
    reset: bool = False,
    stream: bool = False,
    llm: Optional[Union[str, BaseProvider]] = None,  # 支持字符串或实例
    route: Optional[str] = None,
    **kwargs
) -> Any
```

#### BaseAgent.step()
```python
async def step(
    state: AgentState,
    stream: bool = False,
    llm: Optional[Union[str, BaseProvider]] = None,  # 支持字符串或实例
    **kwargs
) -> AgentResponse
```

## 使用示例

### 1. 使用字符串名称（原有方式）

```python
agent = BaseAgent(
    name="my_agent",
    llm=default_llm,
    llms={
        "code": code_llm,
        "math": math_llm,
    }
)
await agent.setup()

# 使用字符串名称
result = await agent.run_async(
    task="Calculate something",
    llm="code",  # 字符串名称
    max_steps=3
)
```

### 2. 使用 BaseProvider 实例（新增方式）

```python
from minion.providers import create_llm_provider

# 创建自定义 provider 实例
custom_llm = create_llm_provider(config.models.get("custom_model"))

# 直接传入 provider 实例
result = await agent.run_async(
    task="Calculate something",
    llm=custom_llm,  # BaseProvider 实例
    max_steps=3
)
```

### 3. 混合使用

```python
# 有时用字符串
result1 = await agent.run_async(task="Task 1", llm="code")

# 有时用实例
custom_llm = create_llm_provider(config.models.get("special_model"))
result2 = await agent.run_async(task="Task 2", llm=custom_llm)

# 有时不指定（使用默认）
result3 = await agent.run_async(task="Task 3")
```

## 优势

1. ✅ **灵活性更高**: 支持字符串名称和 provider 实例两种方式
2. ✅ **向后兼容**: 原有的字符串方式仍然有效
3. ✅ **类型安全**: 使用 `Union[str, BaseProvider]` 明确类型
4. ✅ **动态创建**: 可以在运行时动态创建和使用 provider 实例

## 使用场景

### 场景 1: 预定义的 LLM 配置
```python
# 使用预定义的 LLM 名称
agent = BaseAgent(llm=default_llm, llms={"code": code_llm})
result = await agent.run_async(task="...", llm="code")
```

### 场景 2: 动态创建 LLM
```python
# 根据用户选择动态创建 LLM
user_model = user_input.get("model")
custom_llm = create_llm_provider(config.models.get(user_model))
result = await agent.run_async(task="...", llm=custom_llm)
```

### 场景 3: 临时使用特殊配置
```python
# 为特定任务使用特殊配置的 LLM
from minion.providers.openai_provider import OpenAIProvider

special_llm = OpenAIProvider(
    model="gpt-4",
    temperature=0.1,  # 特殊配置
    max_tokens=1000
)
result = await agent.run_async(task="...", llm=special_llm)
```

## 测试

运行测试示例：
```bash
python examples/test_llm_provider_parameter.py
```

测试内容包括：
1. 使用字符串名称
2. 使用 BaseProvider 实例
3. 混合使用
4. step 方法中使用

## 总结

这个增强使得 `llm` 参数更加灵活和强大，用户可以根据需要选择最合适的方式来指定 LLM：

- **简单场景**: 使用字符串名称 `llm="code"`
- **复杂场景**: 使用 provider 实例 `llm=custom_provider`
- **混合场景**: 两种方式都支持，可以灵活切换
