# Code Agent (Code Minion) 改进文档

## 概述

基于smolagents的提示词，我们对Code Agent进行了重大改进，使其成为一个真正的"code minion"，能够通过结构化的代码推理来解决问题。

## 主要改进

### 1. 结构化的"Thought-Code-Observation"循环

采用了smolagents的结构化方法：
- **Thought**: 解释推理和计划
- **Code**: 编写Python代码，以`<end_code>`结尾
- **Observation**: 自动生成的执行结果和反馈

### 2. Well-Defined代码保证

确保生成的代码是完整且可执行的：
- 包含所有必要的imports
- 定义所有变量
- 代码可以独立运行
- 明确的final_answer调用

### 3. 改进的代码执行

- 支持多种代码块格式：
  - 标准 ```python 块
  - 以 ```<end_code> 结尾的块
  - 松散的 <end_code> 标记
- 结构化的观察反馈
- 详细的错误处理和恢复建议
- 自动检测final_answer调用

### 4. 工具集成

- 正确配置LocalPythonExecutor
- 自动更新工具给executor
- 支持自定义工具和函数

## 使用示例

### 基本使用

```python
from minion.agents.code_agent import CodeAgent

# 创建code agent实例
agent = CodeAgent()

# 解决简单问题
result = await agent.solve_problem("Calculate the area of a circle with radius 5")
print(result)
```

### 数据分析

```python
# 分析数据
data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
question = "What is the mean and standard deviation of this data?"

result = await agent.analyze_data(data, question)
print(result)
```

### 多步骤问题

```python
# 复杂的多步骤问题
problem = """
A company has the following sales data for 6 months:
Month 1: $10,000
Month 2: $12,000
Month 3: $15,000
Month 4: $11,000
Month 5: $18,000
Month 6: $14,000

Calculate:
1. Total sales for the 6 months
2. Average monthly sales
3. Which month had the highest sales
4. What is the growth rate from month 1 to month 6
"""

result = await agent.solve_problem(problem)
print(result)
```

## 提示词结构

Agent使用以下结构化提示词：

```
You are an expert assistant who can solve any task using code blobs.
To solve the task, you must plan forward to proceed in a series of steps, 
in a cycle of 'Thought:', 'Code:', and 'Observation:' sequences.

At each step, in the 'Thought:' sequence, you should first explain your reasoning 
towards solving the task and the tools that you want to use.

Then in the 'Code:' sequence, you should write the code in simple Python. 
The code sequence must end with '<end_code>' sequence.

...
```

## 规则和约束

### 必须遵守的规则

1. 总是提供'Thought:'序列和'Code:'序列
2. 代码块必须以'```<end_code>'结尾
3. 只使用已定义的变量
4. 确保代码是well-defined和完整的
5. 使用final_answer()提供最终答案

### 代码要求

- 包含所有必要的imports
- 定义所有变量
- 使用print()输出中间结果
- 确保代码可以独立运行
- 调用final_answer()完成任务

## 工具和库支持

### 授权的Python库

- 标准库：math, datetime, json, re, etc.
- 数据科学库：numpy, pandas, matplotlib, seaborn
- 网络库：requests
- 文件处理：csv

### 自定义工具

Agent支持自定义工具，可以通过`add_tool()`方法添加：

```python
from minion.tools.base_tool import BaseTool

class CustomTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "custom_tool"
        self.description = "A custom tool for specific tasks"
    
    def forward(self, *args, **kwargs):
        # Tool implementation
        return "Tool result"

agent.add_tool(CustomTool())
```

## 自我反思机制

Agent具有自我反思能力，在以下情况下会自动触发：
- 错误次数达到阈值（默认3次）
- 执行步数达到阈值（默认每5步）
- 置信度过低（默认<0.3）

## 错误处理

### 错误观察

当代码执行失败时，Agent会提供：
- 详细的错误信息
- 简化的traceback
- 恢复建议

### 示例错误反馈

```
**Observation:** Code block 1 execution failed.
**Error:** NameError: name 'undefined_var' is not defined
**Traceback:** NameError: name 'undefined_var' is not defined
**Suggestion:** Review the error and try a different approach in the next step.
```

## 测试

使用提供的测试脚本验证功能：

```bash
python test_code_agent_improved.py
```

测试包括：
- 简单数学计算
- 数据分析
- 多步骤问题解决
- 直接代码执行

## 配置选项

### 初始化参数

```python
agent = CodeAgent(
    max_code_length=2000,           # 最大代码长度
    enable_reflection=True,         # 启用自我反思
    name="my_code_minion"          # Agent名称
)
```

### Python Executor配置

```python
# 在__post_init__中自动配置
self.python_executor = LocalPythonExecutor(
    additional_authorized_imports=["numpy", "pandas", "matplotlib", "seaborn", "requests", "json", "csv"],
    max_print_outputs_length=50000,
    additional_functions={}
)
```

## 最佳实践

1. **明确的问题描述**：提供清晰、具体的问题描述
2. **分步骤思考**：让Agent自然地分解复杂问题
3. **验证结果**：检查Agent的推理过程和最终答案
4. **错误处理**：利用Agent的错误恢复能力
5. **工具扩展**：根据需要添加自定义工具

## 性能优化

- 代码长度限制防止过长代码执行
- 智能错误恢复减少失败率
- 结构化反馈提高可读性
- 工具缓存提高执行效率

## 总结

改进后的Code Agent是一个功能强大的"code minion"，它：
- 使用结构化的推理方法
- 生成well-defined的代码
- 提供详细的观察反馈
- 支持复杂的多步骤问题解决
- 具有自我反思和错误恢复能力

这些改进使得Code Agent能够更好地理解和解决各种编程和数据分析任务，同时保持代码的可读性和可维护性。 