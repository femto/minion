# CodeMinion 与 Smolagents 集成文档

## 概述

本文档总结了将 CodeMinion 与 smolagents 风格集成的所有改进，确保 CodeMinion 能够正确处理 `<end_code>` 标记，并使用 `LocalPythonExecutor` 进行代码执行。

## 问题背景

用户要求：
1. **Brain 传入 LocalPythonExecutor** 而不是其他 Python 环境
2. **CodeMinion 使用 smolagents 风格的逻辑**，包含 `<end_code>` 标记
3. **代码提取逻辑支持 `<end_code>` 标记**
4. **确保代码是 well-defined 的**

## 实现的改进

### 1. 代码提取功能改进

**文件**: `minion/utils/answer_extraction.py`

**改进内容**:
- 支持三种代码块格式：
  - 标准: ```python ... ```
  - 带 `<end_code>`: ```python ... ```<end_code>
  - 松散格式: ```python ... <end_code>
- 改进正则表达式处理空格
- 优化代码提取逻辑，避免被 sanitize 截断

```python
# 支持的格式示例
# 格式1：标准
```python
import math
radius = 5
area = math.pi * radius ** 2
print(f"Area: {area}")
```

# 格式2：带 <end_code>
```python
import math
radius = 5
area = math.pi * radius ** 2
print(f"Area: {area}")
```<end_code>

# 格式3：松散格式
```python
import math
radius = 5
area = math.pi * radius ** 2
print(f"Area: {area}")
<end_code>
```

### 2. CodeMinion 重构

**文件**: `minion/main/worker.py`

**改进内容**:
- 从简单的 `PythonMinion` 继承改为完整的 smolagents 风格实现
- 实现 "Thought -> Code -> Observation" 循环
- 构造包含 `<end_code>` 指令的 prompt
- 使用 `LocalPythonExecutor` 的正确接口

**主要特性**:
1. **Smolagents 风格 Prompt**: 指导 LLM 使用 `<end_code>` 标记
2. **多轮对话**: 支持最多 3 轮迭代改进
3. **错误处理**: 自动重试和错误反馈
4. **最终答案检测**: 自动识别最终答案

### 3. LocalPythonExecutor 集成

**接口适配**:
- 使用 `LocalPythonExecutor.__call__(code)` 方法
- 返回值: `(output, logs, is_final_answer)`
- 支持工具和函数扩展
- 完整的错误处理和状态管理

### 4. 示例代码更新

**文件**: `examples/code_agent_example.py`

**改进内容**:
- 从 `LocalPythonEnv` 改为 `LocalPythonExecutor`
- 正确的 Brain 初始化
- 接口兼容性修复

## 技术细节

### CodeMinion 的执行流程

1. **Prompt 构造**: 
   - 包含 smolagents 风格的指令
   - 明确要求使用 `<end_code>` 标记
   - 支持工具描述和错误反馈

2. **代码提取**: 
   - 使用改进的正则表达式
   - 支持多种 `<end_code>` 格式
   - 优先选择第一个有效代码块

3. **代码执行**: 
   - 使用 `LocalPythonExecutor` 的 `__call__` 方法
   - 处理输出、日志和最终答案标记
   - 完整的错误捕获和重试机制

4. **结果处理**: 
   - 自动检测最终答案
   - 格式化观察结果
   - 支持多轮迭代改进

### 代码提取正则表达式

```python
# 标准代码块
python_code_pattern = r'```(?:python|py)?\s*\n(.*?)\n\s*```'

# 带 <end_code> 的代码块
end_code_pattern = r'```(?:python|py)?\s*\n(.*?)\n```<end_code>'

# 松散格式的 <end_code>
loose_end_code_pattern = r'```(?:python|py)?\s*\n(.*?)<end_code>'
```

## 使用示例

### 基本使用

```python
from minion.main.brain import Brain
from minion.main.local_python_executor import LocalPythonExecutor
from minion.main.worker import CodeMinion
from minion.main.input import Input
from minion.providers import create_llm_provider

# 创建 LocalPythonExecutor
python_executor = LocalPythonExecutor(
    additional_authorized_imports=["math", "numpy"],
    max_print_outputs_length=50000,
    additional_functions={}
)

# 创建 Brain
brain = Brain(python_env=python_executor, llm=llm)

# 创建 Input
input_data = Input(query="Calculate the area of a circle with radius 5")

# 创建 CodeMinion
code_minion = CodeMinion(input=input_data, brain=brain)

# 执行
result = await code_minion.execute()
```

### 任务模式使用

```python
# 在 PlanMinion 中使用
task = {
    "task_id": "calculate_area",
    "instruction": "Calculate circle area",
    "task_description": "Calculate the area of a circle with radius 5",
    "output_key": "circle_area"
}

code_minion = CodeMinion(input=input_data, brain=brain, task=task)
result = await code_minion.execute()
```

## 测试验证

**测试文件**: `test_code_minion_smolagents.py`

**测试用例**:
1. LocalPythonExecutor 接口测试
2. 简单数学计算（圆面积）
3. 递归算法（斐波那契数列）
4. 错误处理和重试
5. 数据分析任务

## 兼容性说明

### 向后兼容性
- 保持 `PythonMinion` 的现有接口
- 继承了所有 `WorkerMinion` 的功能
- 支持所有现有的配置选项

### 新增功能
- Smolagents 风格的 prompt 构造
- `<end_code>` 标记支持
- 多轮对话和错误恢复
- 自动最终答案检测

## 配置选项

### CodeMinion 配置
```python
code_minion = CodeMinion(
    input=input_data,
    brain=brain,
    task=task,  # 可选，用于任务模式
    max_iterations=3  # 最大迭代次数
)
```

### LocalPythonExecutor 配置
```python
python_executor = LocalPythonExecutor(
    additional_authorized_imports=["math", "numpy", "pandas"],
    max_print_outputs_length=50000,
    additional_functions={"custom_func": my_function}
)
```

## 总结

通过这些改进，CodeMinion 现在：

1. ✅ **完全支持 smolagents 风格的代码执行**
2. ✅ **正确处理 `<end_code>` 标记**
3. ✅ **使用 LocalPythonExecutor 进行代码执行**
4. ✅ **支持多轮对话和错误恢复**
5. ✅ **生成 well-defined 的代码**
6. ✅ **保持向后兼容性**

CodeMinion 现在可以作为一个强大的代码执行工具，支持复杂的编程任务，并且能够自动处理错误和迭代改进解决方案。 