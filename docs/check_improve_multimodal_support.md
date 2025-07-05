# CheckMinion和FeedbackMinion多模态支持

本文档说明了CheckMinion和FeedbackMinion对消息列表（multimodal）输入的支持功能。

## 概述

为了支持包含图像、文本等多种内容类型的验证和改进任务，我们为以下Minion类添加了多模态支持：

- **CheckMinion**: 基础检查验证Minion
- **TestMinion**: 基于测试用例的验证Minion  
- **DoctestMinion**: 基于doctest的验证Minion
- **CodiumCheckMinion**: 基于输入/输出的验证Minion
- **FeedbackMinion**: 基于反馈的改进Minion

## 主要功能

### 1. 智能输入检测

所有支持的Minion都会自动检测输入格式：

```python
# 检测是否为消息列表
if hasattr(self.input, 'query') and isinstance(self.input.query, list):
    # 使用多模态处理
    messages = construct_simple_message(self.input.query)
else:
    # 使用传统模板渲染
    prompt = Template(TEMPLATE).render(input=self.input)
```

### 2. 多模态内容支持

支持的内容类型包括：

- **文本字符串**: 普通文本内容
- **PIL.Image对象**: 自动转换为base64格式
- **图像文件路径**: 自动检测并转换
- **OpenAI格式**: 预格式化的图像消息
- **混合内容**: 文本、图像、文件路径的组合

### 3. 上下文增强

#### CheckMinion类

对于多模态输入，直接使用消息列表：

```python
# 示例：多模态检查
multimodal_query = [
    "Please check this mathematical solution:",
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
    "Is the solution correct?"
]
```

#### DoctestMinion

自动添加测试用例信息：

```python
# 为doctest添加测试信息
test_info = f"\n\nDoctest cases to verify:\n"
for i, test in enumerate(self.test_cases, 1):
    test_info += f"Test {i}: {test.source}\nExpected: {test.want}\n"

# 添加到最后一个消息
enhanced_messages[-1] += test_info
```

#### FeedbackMinion

自动添加改进上下文：

```python
# 添加改进上下文信息
improvement_context = f"\n\nImprovement Context:\n"
improvement_context += f"Previous Answer: {self.worker.input.answer}\n"
if hasattr(self.worker.input, 'feedback') and self.worker.input.feedback:
    improvement_context += f"Feedback: {self.worker.input.feedback}\n"
improvement_context += "Please improve the answer based on this feedback."
```

## 使用示例

### 基础验证示例

```python
from minion.main.check import CheckMinion

# 多模态输入
multimodal_input = [
    "Please verify this solution:",
    pil_image,  # PIL.Image对象
    "image.png",  # 图像文件路径
    "Is the mathematical derivation correct?"
]

# 创建输入对象
input_obj = Input(query=multimodal_input, answer="Solution is correct")

# 创建并执行CheckMinion
minion = CheckMinion(input=input_obj, brain=brain)
result = await minion.execute()
```

### 反馈改进示例

```python
from minion.main.improve import FeedbackMinion

# 多模态改进请求
multimodal_query = [
    "Here's my solution with diagram:",
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
    "Please improve it based on the feedback"
]

# 创建改进Minion
minion = FeedbackMinion(
    input=Input(query=multimodal_query),
    brain=brain,
    worker=original_worker
)
improved_result = await minion.execute()
```

## 向后兼容性

所有修改都保持了向后兼容性：

- **传统文本输入**: 继续使用原有的模板渲染方式
- **现有API**: 所有现有的接口和参数保持不变
- **错误处理**: 包含优雅的降级处理

## 测试验证

运行测试来验证功能：

```bash
# 运行多模态支持测试
PYTHONPATH=/path/to/minion1 python tests/test_check_improve_multimodal.py
```

测试覆盖：

- ✅ 文本输入处理
- ✅ 多模态列表处理  
- ✅ 消息增强功能
- ✅ 向后兼容性验证

## 技术实现

### 核心修改

1. **导入增强**: 添加`construct_simple_message`导入
2. **条件检测**: 使用`isinstance(self.input.query, list)`检测
3. **消息构建**: 使用`construct_simple_message()`处理多模态内容
4. **上下文增强**: 为不同类型的Minion添加特定的上下文信息

### 修改的文件

- `minion/main/check.py`: 添加CheckMinion等类的多模态支持
- `minion/main/improve.py`: 添加FeedbackMinion的多模态支持
- `tests/test_check_improve_multimodal.py`: 相关测试

## 总结

通过这些改进，CheckMinion和FeedbackMinion现在可以：

1. **无缝处理多模态内容**: 包括文本、图像、文件等
2. **保持向后兼容**: 现有代码无需修改
3. **智能上下文增强**: 自动添加相关的验证和改进信息
4. **统一接口**: 与其他Minion保持一致的使用方式

这些功能为验证和改进任务提供了更强大的多模态支持能力。 