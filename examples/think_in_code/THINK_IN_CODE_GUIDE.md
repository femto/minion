# Think in Code - Meta工具使用说明

## 概述

Think in Code功能允许CodeAgent在代码执行过程中进行内部思考、规划和反思，而这些meta工具对LLM完全透明，不会出现在functions命名空间中。

## 核心特性

### 1. **AgentStateAwareTool基类**
- 能够通过调用栈自动发现agent上下文
- 访问Brain、state、Input等agent内部状态  
- 对LLM完全透明

### 2. **内置Meta工具**
- `think` - ThinkInCodeTool: 内部思考和推理
- `plan` - PlanTool: 任务规划和步骤跟踪
- `reflect` - ReflectionTool: 自我反思和学习

### 3. **透明调用机制**
- 使用`_meta_call(tool_name, *args, **kwargs)`调用
- 在代码中可用，对LLM不可见
- 自动处理异步执行

## 使用方法

### 基本调用格式

```python
# 内部思考
_meta_call("think", 
    "思考内容", 
    {"context": "上下文信息"}, 
    "priority"  # low/medium/high/critical
)

# 规划管理
_meta_call("plan", "create", {
    "title": "计划标题",
    "steps": ["步骤1", "步骤2", "步骤3"]
})

_meta_call("plan", "complete_step", {
    "result": "步骤结果",
    "notes": "注释"
})

# 自我反思
_meta_call("reflect", "process", {
    "data": {"完成的工作": "结果"},
    "questions": ["What went well?", "What could be improved?"]
})
```

### 典型使用场景

#### 1. 复杂问题解决
```python
def solve_complex_problem():
    # 开始思考
    _meta_call("think", 
        "This is a complex multi-step problem requiring systematic approach",
        {"complexity": "high", "domain": "mathematics"}
    )
    
    # 制定计划
    _meta_call("plan", "create", {
        "title": "解决复杂问题",
        "steps": ["分析", "分解", "求解", "验证"]
    })
    
    # 执行每个步骤...
    for step in steps:
        result = execute_step(step)
        _meta_call("plan", "complete_step", {"result": result})
    
    # 最终反思
    _meta_call("reflect", "overall", {"final_result": result})
    return result
```

#### 2. 代码生成和优化
```python
def generate_optimized_code():
    _meta_call("think", "Need to write efficient algorithm considering time complexity")
    
    # 生成代码...
    code = write_algorithm()
    
    # 反思代码质量
    _meta_call("reflect", "result", {
        "code_length": len(code),
        "efficiency": "O(n log n)",
        "readability": "high"
    })
    
    return code
```

#### 3. 调试和错误处理
```python
def debug_with_thinking():
    try:
        result = risky_operation()
    except Exception as e:
        _meta_call("think", f"Encountered error: {e}. Need to analyze root cause.")
        
        # 分析错误
        _meta_call("reflect", "process", {
            "error_type": type(e).__name__,
            "error_message": str(e)
        })
        
        # 制定修复计划
        _meta_call("plan", "create", {
            "title": "错误修复",
            "steps": ["识别原因", "设计修复", "测试验证"]
        })
        
        result = implement_fix()
    
    return result
```

## Meta工具详细说明

### ThinkInCodeTool

**用途**: 内部思考和推理分析

**参数**:
- `thought` (string): 思考内容
- `context` (object, 可选): 上下文信息
- `priority` (string, 可选): 优先级 (low/medium/high/critical)

**返回**:
```python
{
    "thinking_complete": True,
    "thought_id": 1,
    "analysis": {
        "thought_type": "problem_solving",
        "complexity": "medium",
        "emotional_tone": "analytical",
        "key_concepts": ["algorithm", "optimization"],
        "reasoning_pattern": "sequential_reasoning"
    },
    "suggestions": ["Break down the problem", "Consider alternatives"]
}
```

### PlanTool

**用途**: 任务规划和步骤管理

**操作**:
- `create`: 创建新计划
- `update`: 更新计划
- `complete_step`: 完成步骤
- `get_status`: 获取状态

**示例**:
```python
# 创建计划
_meta_call("plan", "create", {
    "title": "数据分析项目",
    "goal": "完成数据清洗和可视化", 
    "steps": ["收集数据", "清洗数据", "分析模式", "创建图表"]
})

# 完成步骤
_meta_call("plan", "complete_step", {
    "result": "数据收集完成，获得1000条记录",
    "notes": "数据质量良好"
})

# 检查状态
status = _meta_call("plan", "get_status")
```

### ReflectionTool

**用途**: 自我反思和学习

**反思主题**:
- `result`: 结果反思
- `process`: 过程反思  
- `decision`: 决策反思
- `overall`: 整体反思

**参数**:
- `subject` (string): 反思主题
- `data` (object, 可选): 反思数据
- `questions` (array, 可选): 具体问题

**示例**:
```python
# 过程反思
_meta_call("reflect", "process", {
    "steps_taken": 5,
    "time_spent": "30 minutes",
    "errors_encountered": 1
})

# 结果反思  
_meta_call("reflect", "result", {
    "final_answer": "42",
    "confidence": "high",
    "method_used": "analytical_approach"
})
```

## 集成到现有代码

### 1. AsyncPythonExecutor自动支持
Meta工具已集成到AsyncPythonExecutor中，无需额外配置即可使用。

### 2. Brain.step()兼容
Brain.step()方法已支持meta工具的状态传递。

### 3. Agent状态访问
Meta工具通过调用栈自动发现agent上下文，可访问：
- Brain实例
- 当前state字典
- Input对象
- Agent实例（如果有）

## 最佳实践

### 1. 思考时机
- 任务开始时进行初始思考
- 遇到复杂决策时思考
- 错误发生时分析思考
- 任务完成后总结思考

### 2. 规划使用
- 复杂任务开始前制定计划
- 及时更新计划状态
- 完成步骤时记录结果

### 3. 反思频率
- 关键步骤后进行过程反思
- 最终结果的结果反思
- 重要决策的决策反思
- 会话结束时整体反思

### 4. 记忆集成
Meta工具会自动将思考、计划、反思内容存储到agent的记忆系统中（如果可用），支持长期学习和改进。

## 技术实现

### 状态发现机制
```python
def _discover_agent_context(self):
    """通过调用栈发现agent状态"""
    frame = inspect.currentframe()
    while frame:
        locals_vars = frame.f_locals
        if 'brain' in locals_vars or 'state' in locals_vars:
            return {
                'brain': locals_vars.get('brain'),
                'state': locals_vars.get('state', {}),
                'input': locals_vars.get('input'),
            }
        frame = frame.f_back
    return None
```

### 透明注册机制
```python
# Meta工具注册到static_tools但不暴露给functions命名空间
meta_tools = {"think": ThinkInCodeTool(), ...}
self.static_tools.update(meta_tools)

# functions命名空间只包含LLM可见工具
functions_namespace = types.SimpleNamespace()
for name, tool in converted_tools.items():  # 不包含meta_tools
    setattr(functions_namespace, name, tool)
```

这样设计确保了meta工具对LLM完全透明，但在代码执行中完全可用，为CodeAgent提供了强大的内部认知能力。