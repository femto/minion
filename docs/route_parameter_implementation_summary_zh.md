# Route 参数实现总结

## 完成的工作

### 1. 调用链路分析

创建了详细的调用链路分析文档 `docs/code_minion_call_chain_analysis.md`，展示了 CodeAgent 如何使用 "code" route 调用 CodeMinion 的完整流程：

```
CodeAgent.execute_step()
  ↓ (设置 input.route = 'code')
Brain.step(state)
  ↓ (提取 input)
Mind.step(input)
  ↓ (创建 ModeratorMinion)
ModeratorMinion.execute_single()
  ↓ (使用 input.route)
RouteMinion.execute()
  ↓ (从 MINION_REGISTRY 获取 CodeMinion)
CodeMinion.execute()
  ↓ (Thought -> Code -> Observation 循环)
返回 AgentResponse
```

### 2. BaseAgent 支持 route 参数

**修改文件**: `minion/agents/base_agent.py`

#### 2.1 更新 `run()` 方法签名

```python
def run(self, 
       task: Optional[Union[str, Input]] = None,
       state: Optional[AgentState] = None, 
       max_steps: Optional[int] = None,
       reset: bool = False,
       llm: Optional[str] = None,
       route: Optional[str] = None,  # 新增参数
       **kwargs) -> Any:
```

#### 2.2 更新 `run_async()` 方法签名

```python
async def run_async(self, 
                   task: Optional[Union[str, Input]] = None,
                   state: Optional[AgentState] = None, 
                   max_steps: Optional[int] = None,
                   reset: bool = False,
                   stream: bool = False,
                   llm: Optional[str] = None,
                   route: Optional[str] = None,  # 新增参数
                   **kwargs) -> Any:
```

#### 2.3 在 `run_async()` 中处理 route

```python
# 处理状态初始化或恢复
if state is None:
    if task is None:
        raise ValueError("Either 'task' or 'state' must be provided")
    # 初始化新状态，传递 route 参数
    self._init_state_from_task(task, route=route, **kwargs)
else:
    # 使用已有状态
    self.state = state
    
    # 设置route（如果提供）
    if route is not None and self.state.input:
        self.state.input.route = route
```

#### 2.4 更新 `_init_state_from_task()` 方法

```python
def _init_state_from_task(self, task: Union[str, Input], route: Optional[str] = None, **kwargs) -> None:
    """
    从任务初始化内部状态
    Args:
        task: 任务描述或Input对象
        route: 可选的route名称，指定使用哪个minion
        **kwargs: 附加参数
    """
    # 将任务转换为Input对象
    if isinstance(task, str):
        input_obj = Input(query=task)
        task_str = task
    else:
        input_obj = task
        task_str = task.query
    
    # 设置route（如果提供）
    if route is not None:
        input_obj.route = route
    
    # ... 其余代码
```

### 3. CodeAgent 支持 route 参数

**修改文件**: `minion/agents/code_agent.py`

#### 3.1 更新 `run()` 方法签名

```python
def run(self, 
       task: Optional[Union[str, Input]] = None,
       max_steps: Optional[int] = None,
       reset: bool = False,
       route: Optional[str] = None,  # 新增参数
       **kwargs) -> Any:
```

#### 3.2 更新 `run_async()` 方法签名

```python
async def run_async(self, task: Optional[Union[str, Input]] = None,
                   max_steps: Optional[int] = None,
                   reset: bool = False,
                   stream: bool = False,
                   route: Optional[str] = None,  # 新增参数
                   **kwargs) -> Any:
```

#### 3.3 在 `run_async()` 中传递 route

```python
# Prepare input and internal state
enhanced_input = self._prepare_input(task, route=route)  # 传递 route
self._prepare_internal_state(task, reset)

# 调用父类方法时传递 route
result = await super().run_async(
    task=enhanced_input,
    state=self.state, 
    max_steps=max_steps, 
    stream=stream, 
    route=route,  # 传递 route
    **kwargs
)
```

#### 3.4 更新 `_prepare_input()` 方法

```python
def _prepare_input(self, task: Optional[Union[str, Input]], route: Optional[str] = None) -> Input:
    """
    Prepare input data for execution.
    
    Args:
        task: Task description or Input object
        route: 可选的route名称，如果提供则覆盖默认的'code' route
        
    Returns:
        Input: Prepared Input object with enhanced query
    """
    # Convert string task to Input if needed
    if isinstance(task, str):
        # Use provided route or default to 'code'
        default_route = route if route is not None else 'code'
        input_data = Input(query=task, route=default_route)
    elif isinstance(task, Input):
        input_data = task
        # Set route based on priority: explicit route param > existing route > default 'code'
        if route is not None:
            input_data.route = route
        elif not input_data.route:
            input_data.route = 'code'
    else:
        raise ValueError(f"Task must be string or Input object, got {type(task)}")
    
    # Enhance input with code-thinking instructions
    enhanced_input = input_data
    return enhanced_input
```

### 4. 创建测试示例

**文件**: `examples/test_agent_route_parameter.py`

创建了完整的测试示例，展示了：
- BaseAgent 使用不同 routes
- CodeAgent 使用不同 routes
- 同步接口使用 route 参数
- 与 Input 对象一起使用 route 参数

### 5. 创建使用指南

**文件**: `docs/agent_route_parameter_guide.md`

创建了详细的中文使用指南，包括：
- Route 的概念和作用
- 使用方法和示例
- Route 优先级说明
- 可用的 routes 列表
- 注意事项和调试技巧

## Route 优先级

Route 的设置遵循以下优先级（从高到低）：

1. **`run_async()` 的 `route` 参数** - 最高优先级
2. **`Input` 对象的 `route` 属性** - 中等优先级
3. **Agent 的默认行为** - 最低优先级
   - `BaseAgent`: 由 RouteMinion 智能选择
   - `CodeAgent`: 默认使用 `'code'`

## 使用示例

### 基本使用

```python
# BaseAgent 使用 route
agent = BaseAgent(name="my_agent", llm=llm)
await agent.setup()

result = await agent.run_async(
    task="Calculate 25 * 37",
    route="code",  # 指定使用 code minion
    max_steps=3
)
```

### CodeAgent 覆盖默认 route

```python
# CodeAgent 默认使用 'code' route
code_agent = CodeAgent(name="code_agent", llm=llm)
await code_agent.setup()

# 覆盖为 'cot' route
result = await code_agent.run_async(
    task="Explain photosynthesis",
    route="cot",  # 覆盖默认的 'code'
    max_steps=1
)
```

### 与 Input 对象一起使用

```python
# Input 对象中的 route 会被参数覆盖
input_obj = Input(query="Calculate factorial of 10", route="native")

result = await agent.run_async(
    task=input_obj,
    route="code",  # 覆盖 Input 中的 "native"
    max_steps=3
)
```

## 技术细节

### 数据流

1. **用户调用** `agent.run_async(task="...", route="code")`
2. **BaseAgent.run_async()** 接收 route 参数
3. **_init_state_from_task()** 将 route 设置到 `input.route`
4. **Brain.step()** 接收包含 route 的 state
5. **ModeratorMinion** 读取 `input.route`
6. **RouteMinion** 从 `MINION_REGISTRY` 查找对应的 minion
7. **CodeMinion** (或其他 minion) 执行任务

### 关键修改点

1. **方法签名**: 在 `run()` 和 `run_async()` 中添加 `route` 参数
2. **状态初始化**: 在 `_init_state_from_task()` 中设置 `input.route`
3. **状态恢复**: 在 `run_async()` 中处理已有状态时设置 route
4. **CodeAgent 特殊处理**: 在 `_prepare_input()` 中处理 route 优先级

## 向后兼容性

所有修改都是向后兼容的：
- ✅ `route` 参数是可选的（`Optional[str] = None`）
- ✅ 不传递 `route` 时使用原有的默认行为
- ✅ 现有代码无需修改即可继续工作

## 测试建议

运行测试示例：

```bash
python examples/test_agent_route_parameter.py
```

这将测试：
1. BaseAgent 使用不同 routes
2. CodeAgent 使用不同 routes
3. 同步接口
4. 与 Input 对象的交互

## 总结

通过这次实现，我们：

1. ✅ **分析了调用链路**: 理解了 CodeAgent 如何使用 "code" minion
2. ✅ **实现了 route 参数**: 在 BaseAgent 和 CodeAgent 的 `run/run_async` 方法中添加了 route 支持
3. ✅ **保持了向后兼容**: 所有修改都是可选的，不影响现有代码
4. ✅ **创建了文档和示例**: 提供了完整的使用指南和测试代码
5. ✅ **通过了语法检查**: 代码没有语法错误

现在用户可以灵活地在运行时指定使用哪个 minion，而不需要修改 agent 的配置或创建新的 agent 实例！
