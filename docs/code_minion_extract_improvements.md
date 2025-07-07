# Code Minion 代码提取功能改进

## 概述

根据用户需求，我们对 `worker.py` 中的 Code Minion 进行了重要改进，使其能够像 smolagents 一样正确处理 `<end_code>` 标记，确保代码提取逻辑与 smolagents 的行为一致。

## 问题背景

在原有的实现中，`extract_python` 函数无法正确处理 smolagents 风格的代码块，特别是：
- 以 `<end_code>` 结尾的代码块
- 没有结束 ``` 但有 `<end_code>` 的代码块
- 多种代码块格式的混合情况

## 改进内容

### 1. 更新 `extract_python` 函数

文件位置：`minion/utils/answer_extraction.py`

主要改进：
- **支持三种代码块格式**：
  - 标准的 ```python ... ``` 块
  - 以 `<end_code>` 结尾的代码块：```python ... ```<end_code>
  - 没有结束 ``` 但有 `<end_code>` 的代码块：```python ... <end_code>

- **改进正则表达式**：
  - 原来：`r'```(?:python|py)?\s*\n(.*?)\n```'`
  - 现在：`r'```(?:python|py)?\s*\n(.*?)\n\s*```'`（支持结尾空格）

- **优化代码提取逻辑**：
  - 当找到明确的代码块时，直接返回而不进行额外的 sanitize 操作
  - 避免了 sanitize 函数的截断问题
  - 只有在指定 entrypoint 时才进行 sanitize

### 2. 支持的代码块格式

```python
# 格式1：标准代码块
```python
import math
radius = 5
area = math.pi * radius ** 2
print(area)
```

# 格式2：smolagents风格 - 有结束标记
```python
import math
radius = 5
area = math.pi * radius ** 2
print(area)
```<end_code>

# 格式3：smolagents风格 - 无结束```
```python
import math
radius = 5
area = math.pi * radius ** 2
print(area)
<end_code>
```

### 3. 测试验证

我们创建了全面的测试用例，验证了以下场景：
- ✅ 标准代码块 + `<end_code>`
- ✅ 无结束``` + `<end_code>`
- ✅ 多个代码块（提取第一个）
- ✅ 标准代码块（无`<end_code>`）
- ✅ smolagents 示例

## 影响的组件

### 1. Worker.py 中的 Minions

- **PythonMinion**: 使用更新的 `extract_python` 函数
- **CodeMinion**: 继承自 PythonMinion，自动获得改进

### 2. 代码执行流程

1. LLM 生成包含 `<end_code>` 标记的代码
2. `extract_python` 函数正确提取代码块
3. 代码被发送到 Python 环境执行
4. 返回执行结果

## 使用示例

### 在 smolagents 风格的响应中：

```
Thought: I will calculate the area of a circle with radius 5.
Code:
```py
import math
radius = 5
area = math.pi * radius ** 2
print(f"Area: {area}")
```<end_code>
```

这样的响应现在可以被正确解析和执行。

### 在 PythonMinion 中：

```python
from minion.main.worker import PythonMinion

# 创建 PythonMinion 实例
minion = PythonMinion(input=input_obj, brain=brain_obj)

# 执行时会自动使用改进的 extract_python 函数
result = await minion.execute()
```

## 兼容性

- ✅ 向后兼容：仍然支持原有的标准代码块格式
- ✅ 新功能：支持 smolagents 风格的 `<end_code>` 标记
- ✅ 无破坏性变更：所有现有功能保持不变

## 总结

这次改进使得 Code Minion 能够：
1. 正确处理 smolagents 风格的代码块
2. 支持多种代码块格式
3. 避免代码被意外截断
4. 保持与现有系统的完全兼容性

通过这些改进，Code Minion 现在能够无缝地与 smolagents 风格的 Code Agent 协同工作，确保代码提取和执行的准确性。 