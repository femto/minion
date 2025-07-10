# AWS Bedrock Provider 使用指南

## 概述

AWS Bedrock Provider 为 Minion 项目提供了与 AWS Bedrock 服务的集成，支持 Claude 等 Anthropic 模型。

## 功能特性

- ✅ **同步和异步生成**：支持 `generate_sync()` 和 `generate()` 方法
- ✅ **流式响应**：支持 `generate_stream()` 进行实时流式输出
- ✅ **流式响应对象**：支持 `generate_stream_response()` 返回完整的响应对象
- ✅ **成本跟踪**：自动记录 token 使用情况和成本
- ✅ **错误处理**：完整的错误处理和重试机制
- ✅ **消息格式转换**：自动将 Minion 消息格式转换为 Bedrock Claude 格式
- ✅ **多媒体支持**：支持文本和图片输入

## 安装要求

确保安装了必要的依赖：

```bash
pip install boto3 botocore
```

## 配置

### 1. 基本配置

在 `config/config.yaml` 中添加 Bedrock 模型配置：

```yaml
models:
  "claude-3-5-sonnet-20240620":
    api_type: "bedrock"
    access_key_id: "YOUR_AWS_ACCESS_KEY_ID"
    secret_access_key: "YOUR_AWS_SECRET_ACCESS_KEY"
    region: "us-east-1"
    model: "anthropic.claude-3-5-sonnet-20240620-v1:0"
    temperature: 0.1
```

### 2. AWS 凭证配置

有几种方式配置 AWS 凭证：

#### 方式 1：分离的访问密钥（推荐，清晰明确）
```yaml
access_key_id: "YOUR_AWS_ACCESS_KEY_ID"
secret_access_key: "YOUR_AWS_SECRET_ACCESS_KEY"
```

#### 方式 2：使用 api_key 字段（向后兼容）
```yaml
api_key: "YOUR_AWS_ACCESS_KEY_ID:YOUR_AWS_SECRET_ACCESS_KEY"
```

#### 方式 3：使用环境变量
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-east-1"
```

#### 方式 4：使用 AWS CLI 配置
```bash
aws configure
```

### 3. 支持的模型

- `anthropic.claude-3-5-sonnet-20240620-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`
- `anthropic.claude-3-opus-20240229-v1:0`

### 4. 支持的区域

确保在支持 Anthropic 模型的 AWS 区域：
- `us-east-1` (推荐)
- `us-west-2`
- 其他支持的区域请参考 [Anthropic 支持的国家/地区](https://www.anthropic.com/supported-countries)

## 使用示例

### 基本使用

```python
from minion.providers import create_llm_provider
from minion.configs.config import LLMConfig
from minion.schema.message_types import Message

# 创建配置（使用清晰的字段名）
config = LLMConfig(
    api_type="bedrock",
    access_key_id="YOUR_AWS_ACCESS_KEY_ID",
    secret_access_key="YOUR_AWS_SECRET_ACCESS_KEY",
    region="us-east-1",
    model="anthropic.claude-3-5-sonnet-20240620-v1:0",
    temperature=0.1
)

# 创建 provider
provider = create_llm_provider(config)

# 准备消息
messages = [
    Message(role="user", content="Hello, how are you?")
]

# 同步生成
response = provider.generate_sync(messages)
print(response)

# 异步生成
response = await provider.generate(messages)
print(response)

# 流式响应对象
response = await provider.generate_stream_response(messages)
print(f"完整响应: {response}")
print(f"内容: {response['choices'][0]['message']['content']}")
print(f"Token 使用: {response['usage']}")
```

### 与 Brain 集成

```python
from minion.main.brain import Brain
from minion.main.input import Input

# 创建 Brain
brain = Brain()

# 更新 Brain 使用 Bedrock
from minion.configs.config import config
bedrock_config = config.models.get("claude-3-5-sonnet-20240620")
brain.llm = create_llm_provider(bedrock_config)

# 使用 Brain
input_obj = Input(query="解释什么是机器学习", route="code")
result = await brain.step(input_obj)
print(result.response)
```

### 与 CodeAgent 集成

```python
from minion.agents.code_agent import CodeAgent
from minion.main.brain import Brain

# 创建配置了 Bedrock 的 Brain
brain = Brain()
bedrock_config = config.models.get("claude-3-5-sonnet-20240620")
brain.llm = create_llm_provider(bedrock_config)

# 创建 CodeAgent
agent = CodeAgent(brain=brain, use_async_executor=True)

# 使用 CodeAgent
input_obj = Input(query="计算斐波那契数列的第10项", route="code")
result = await agent.step(input_obj)
print(result.response)
```

## 错误处理

常见错误及解决方案：

### 1. 地区限制错误
```
ValidationException: Access to Anthropic models is not allowed from unsupported countries
```
**解决方案**：确保在支持的 AWS 区域运行，参考 [Anthropic 支持的国家/地区](https://www.anthropic.com/supported-countries)

### 2. 认证错误
```
UnauthorizedOperation: AWS was not able to validate the provided access credentials
```
**解决方案**：检查 AWS 凭证是否正确配置

### 3. 模型不可用
```
ValidationException: The requested model does not exist or is not available
```
**解决方案**：检查模型 ID 是否正确，确保在对应区域启用了模型访问

## 成本监控

Bedrock Provider 自动跟踪 token 使用情况：

```python
# 获取成本信息
cost_manager = provider.get_cost()
print(f"总成本: ${cost_manager.total_cost:.6f}")
print(f"输入 tokens: {cost_manager.total_prompt_tokens}")
print(f"输出 tokens: {cost_manager.total_completion_tokens}")
```

## 技术细节

### 消息格式转换

Provider 自动处理以下转换：
- Minion `Message` 对象 → Bedrock Claude API 格式
- `system` 消息特殊处理
- 图片内容支持（base64 格式）

### 异步支持

由于 AWS SDK 不直接支持异步，provider 使用线程池来实现异步调用：

```python
async def generate(self, messages, temperature=None, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self.generate_sync, messages, temperature, **kwargs)
```

### 流式响应

支持真正的流式响应，使用 `invoke_model_with_response_stream`：

```python
response = self.client.invoke_model_with_response_stream(
    modelId=self.model_id,
    body=json.dumps(request_body)
)

for event in response['body']:
    if 'chunk' in event:
        chunk = json.loads(event['chunk']['bytes'])
        # 处理文本增量...
```

## 最佳实践

1. **区域选择**：使用 `us-east-1` 获得最佳性能和模型可用性
2. **成本控制**：定期监控 token 使用情况
3. **错误重试**：Provider 内置重试机制处理临时错误
4. **安全**：不要在代码中硬编码 AWS 凭证，使用环境变量或 IAM 角色
5. **模型选择**：根据任务复杂度选择合适的 Claude 模型

## 支持

如有问题，请检查：
1. AWS 凭证配置是否正确
2. 区域是否支持 Anthropic 模型
3. 模型访问权限是否已启用
4. 网络连接是否正常