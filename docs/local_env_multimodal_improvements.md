# Local Python Environment & Multimodal Improvements

## 概述

本文档记录了对minion项目的重要改进，主要包括：
1. Brain使用LocalPythonEnv替代Docker环境
2. 完善的PIL.Image多模态支持
3. 简化的测试和演示环境

## 主要改进

### 1. LocalPythonEnv作为默认环境

**问题**: 之前Brain默认使用Docker的PythonEnv，需要intercode-python镜像，对于测试和轻量使用过于重量级。

**解决方案**: 修改`minion/main/brain.py`，将默认python_env改为LocalPythonEnv。

```python
# 之前
image_name = "intercode-python"
self.python_env = python_env or PythonEnv(image_name, verbose=False, is_agent=True)

# 现在
# 优先使用LocalPythonEnv，避免Docker依赖
self.python_env = python_env or LocalPythonEnv(verbose=False, is_agent=True)
```

**优势**:
- ✅ 无需Docker依赖
- ✅ 启动更快
- ✅ 适合开发和测试
- ✅ 支持本地Python代码执行
- ✅ 保持与PythonEnv相同的接口

### 2. 完善的PIL.Image多模态支持

**功能**: 在`minion/utils/template.py`中添加了完整的PIL.Image支持。

#### 新增函数：

1. **`_convert_pil_image_to_base64(image, format='PNG')`**
   - 将PIL.Image对象转换为base64 data URL
   - 支持PNG/JPEG格式
   - 自动处理RGBA→RGB转换（JPEG兼容性）

2. **`_convert_image_path_to_base64(image_path)`**  
   - 将图像文件路径转换为base64 data URL
   - 自动检测文件格式
   - 支持各种图像格式

3. **`_format_multimodal_content(item)`**
   - 通用内容格式化器
   - 自动识别和处理：
     - 文本字符串
     - PIL.Image对象 
     - 图像文件路径
     - 已格式化的OpenAI字典
     - 其他类型（转换为文本）

#### 支持的内容类型：

| 输入类型 | 处理方式 | 输出格式 |
|---------|----------|----------|
| `str` | 文本或图像路径检测 | `{"type": "text", "text": "..."}` 或 `{"type": "image_url", ...}` |
| `PIL.Image` | 转换为base64 | `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}` |
| `dict` | 保持原样 | 原字典（假设已是OpenAI格式） |
| 其他 | 转换为字符串 | `{"type": "text", "text": "..."}` |

#### 使用示例：

```python
from PIL import Image
from minion.utils.template import construct_simple_message
from minion.main.input import Input

# 创建混合内容
img = Image.new('RGB', (100, 100), color='red')
input_data = Input(
    query=[
        "请分析这张图片:",
        img,
        "它是什么颜色的?"
    ],
    system_prompt="你是图像分析专家"
)

# 构造消息
messages = construct_simple_message(input_data)
# messages[1]['content'] 将包含文本和base64编码的图像
```

### 3. 错误处理和兼容性

**PIL可选性**: 如果PIL/Pillow未安装：
- PIL.Image对象会被转换为文本格式
- 图像文件路径会被当作普通文本处理
- 系统优雅降级，不会崩溃

**错误恢复**: 
- 图像转换失败时自动回退到文本模式
- 文件路径无效时当作文本处理
- 保证系统稳定性

### 4. 测试和演示

#### 测试文件: `tests/test_pil_image_multimodal.py`

- ✅ 基本内容格式化测试
- ✅ PIL.Image转换测试（PIL可用时）
- ✅ 消息构造测试
- ✅ Brain与LocalPythonEnv集成测试
- ✅ 错误处理测试

#### 演示文件: `examples/simple_local_multimodal_demo.py`

- ✅ LocalPythonEnv基本功能演示
- ✅ 多模态模板功能演示
- ✅ PIL.Image支持演示（如果可用）
- ✅ 图像文件路径支持演示
- ✅ Brain集成演示

### 5. 运行方式

由于模块路径问题，建议使用PYTHONPATH运行：

```bash
# 运行测试
PYTHONPATH=/path/to/minion1 python tests/test_pil_image_multimodal.py

# 运行演示
PYTHONPATH=/path/to/minion1 python examples/simple_local_multimodal_demo.py
```

## 技术细节

### LocalPythonEnv特性

- 直接在本地Python进程中执行代码
- 支持变量状态保持
- 支持多行函数定义
- 提供相同的step()接口
- 无需Docker或容器

### PIL.Image Base64转换

```python
def _convert_pil_image_to_base64(image, format='PNG') -> str:
    buffer = io.BytesIO()
    
    # JPEG兼容性处理
    if format.upper() == 'JPEG' and image.mode in ('RGBA', 'LA'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    
    image.save(buffer, format=format)
    image_data = buffer.getvalue()
    base64_data = base64.b64encode(image_data).decode('utf-8')
    
    return f"data:image/{format.lower()};base64,{base64_data}"
```

### 多模态消息构造流程

1. **输入检测**: 判断query是字符串还是列表
2. **内容格式化**: 使用`_format_multimodal_content()`处理每个项目
3. **消息组装**: 构造OpenAI兼容的messages数组
4. **系统提示**: 添加system role消息

## 兼容性说明

### 向后兼容

- ✅ 现有的纯文本query继续工作
- ✅ 现有的模板渲染继续工作  
- ✅ Brain接口保持不变
- ✅ 可以显式传入PythonEnv覆盖默认行为

### 可选依赖

- **PIL/Pillow**: 用于图像处理，可选安装
- **Docker**: 不再必须，仅在显式指定PythonEnv时需要

## 使用建议

### 开发和测试环境
- 使用默认的LocalPythonEnv
- 安装Pillow以支持图像功能
- 使用PYTHONPATH确保模块正确加载

### 生产环境
- 根据需要选择LocalPythonEnv或Docker PythonEnv
- 确保图像文件访问权限
- 监控base64转换的内存使用

### 多模态应用
- 混合使用文本、PIL.Image对象和文件路径
- 利用自动格式检测简化代码
- 处理PIL不可用的降级情况

## 总结

这些改进显著提升了minion项目的可用性：

1. **简化部署**: 无需Docker即可运行
2. **增强功能**: 完整的多模态支持
3. **提高稳定性**: 优雅的错误处理和降级
4. **保持兼容**: 不破坏现有功能
5. **便于测试**: 轻量级的测试环境

现在用户可以轻松地在本地环境中使用文本和图像的混合查询，无需复杂的Docker设置或外部依赖。 