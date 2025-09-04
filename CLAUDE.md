## 🧠 **记忆存储**

### **系统架构记忆**
- never put test in the top level folder
- agent.run_async() 返回的是一个async函数，需要先await才能获得async generator
  - 正确用法: `async for event in (await agent.run_async(input_obj, **kwargs)):`
  - 错误用法: `async for event in agent.run_async(input_obj, **kwargs):`
  - 这是因为run_async是async函数，它delegate到其他函数，本身需要await才能返回真正的async generator

- Agent构造函数设计模式
  - 所有Agent应继承BaseAgent并使用@dataclass装饰器
  - 构造函数参数应与BaseAgent对齐，使用dataclass字段而非__init__方法
  - stream相关参数不应在构造函数中，而是通过run_async(stream=True/False)动态控制

- LLM构造和获取最佳实践
  - MinionToolCallingAgent构造时会自动从model配置创建LLM
  - 标准LLM获取模式（参考brain.py）：
    ```python
    # 方式1：直接指定model名称，从config.models获取配置
    model = "gpt-4o"  # 或其他模型: "gemini-2.0-flash-exp", "deepseek-r1", "phi-4", "llama3.2"
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)
    
    # 方式2：使用默认模型
    llm = create_llm_provider(config.models.get("default"))
    
    # 方式3：在Agent构造时传入model名称，让Agent自动创建
    agent = MinionToolCallingAgent(model="gpt-4o")  # 会自动创建LLM
    
    # 使用dataclass风格构造
    agent = MinionToolCallingAgent(
        name="my_agent",
        tools=[tool1, tool2],
        model="gpt-4o",
        max_tool_threads=4
    )
    ```
  - Brain类LLM处理逻辑：支持字符串model名称或直接传入LLM实例
    - 如果llm参数是字符串，会调用`create_llm_provider(config.models.get(llm))`
    - 如果llm参数是LLM实例，直接使用
    - 支持llms字典批量处理多个模型配置

- functions.final_answer调用修复
  - 修复了`functions.final_answer()`调用不抛异常的问题
  - 问题原因：`functions`命名空间中的`final_answer`是原始版本，不会抛出FinalAnswerException
  - 解决方案：在`evaluate_async_python_code`中创建异常包装器后，同时更新`functions`命名空间
  - 现在`functions.final_answer()`和直接调用`final_answer()`都会正确抛出异常并设置`is_final_answer=True`

- worker.py终止逻辑修复  
  - 修复了Python executor返回`is_final_answer=True`但任务不终止的问题
  - 问题原因：worker.py获取了`is_final_answer`值但没有使用，硬编码`terminated=False`
  - 解决方案：当`is_final_answer=True`时立即返回`terminated=True`的AgentResponse
  - 现在final_answer工具调用会正确终止任务执行

- Minion流式处理重构
  - 在基类Minion中添加了`stream_node_execution`通用方法
  - 所有子类现在使用统一的流式处理逻辑，直接yield StreamChunk对象
  - 移除了错误的final_answer检测逻辑，final_answer处理由LmpActionNode负责
  - 保持StreamChunk对象的原始结构，便于上层UI正确处理不同类型的chunk

- tool_choice参数支持
  - MinionToolCallingAgent和LmpActionNode现在都支持tool_choice参数
  - 可选值：
    - "auto": 让模型自动决定是否调用工具（默认值）
    - "none": 强制模型不调用任何工具
    - {"type": "function", "function": {"name": "function_name"}}: 强制调用特定工具
  - 使用示例：
    ```python
    # 在Agent中使用
    response = await agent.execute_step(state, tool_choice="none")
    
    # 在LmpActionNode中使用
    response = await lmp_node.execute(messages, tools=tools, tool_choice="auto")
    
    # 强制调用特定工具
    response = await lmp_node.execute(messages, tools=tools, 
                                    tool_choice={"type": "function", "function": {"name": "search"}})
    ```

- StreamChunk流式处理最佳实践
  - StreamChunk是agent流式输出的基本单元，每个chunk包含一小部分内容（如单个token）
  - UI处理时应该累积StreamChunk内容，而不是为每个chunk创建单独的消息行
  - StreamChunk有不同类型（chunk_type）：
    - 'text': Provider层输出文本（openai_provider使用）
    - 'tool_call': 工具调用信息
    - 'tool_response': 工具响应结果
    - 'llm_output': Agent层常规LLM输出内容
    - 'step_start': Agent步骤开始
    - 'step_end': Agent步骤结束
    - 'completion': 任务完成
    - 'warning': 警告信息
    - 'error': 错误信息
    - 'final_answer': 最终答案
  - 累积模式处理：
    ```python
    streaming_content = []
    if isinstance(event, StreamChunk):
        # 对于text和llm_output类型的chunk需要累积
        if event.chunk_type in ['text', 'llm_output']:
            streaming_content.append(event.content)
            display_content = "".join(streaming_content)
        else:
            # 其他类型单独处理（如error, final_answer等）
            handle_special_chunk(event)
    ```

- CodeAgent继承和重写BaseAgent最佳实践
  - CodeAgent与BaseAgent的主要区别在于偏好使用CodeMinion（route='code'）
  - CodeAgent重写run_async方法，但仍然调用super().run_async()来复用BaseAgent的执行逻辑
  - 关键重写点：
    ```python
    def _prepare_input(self, task):
        # 确保使用code route，这是CodeAgent的核心区别
        if isinstance(task, str):
            input_data = Input(query=task, route='code')  # 偏好code route
        elif isinstance(task, Input):
            input_data = task
            if not input_data.route:
                input_data.route = 'code'  # 默认使用code route
        
        # 增强input with code-thinking instructions
        enhanced_input = self._enhance_input_for_code_thinking(input_data)
        return enhanced_input
    ```
  - route='code'会传递给Brain.step()，最终路由到CodeMinion进行code-based reasoning
  - CodeAgent通过input enhancement而非完全重写执行逻辑来实现差异化
  - 保持与BaseAgent的兼容性，可选择启用state tracking等高级功能

- AgentResponse统一流式处理架构
  - AgentResponse现在继承自StreamChunk，统一了流式处理接口
  - 所有Agent响应都可以作为StreamChunk在streaming中使用
  - AgentResponse会自动设置适当的chunk_type：
    - error: 当有错误时
    - final_answer: 当is_final_answer=True时
    - completion: 当terminated=True时
    - agent_response: 默认类型
  - metadata自动包含AgentResponse的关键信息（score, confidence, terminated等）
  - 简化了UI层的处理逻辑，统一使用StreamChunk接口

- Gradio UI重复显示修复
  - 修复了gradio_demo中StreamChunk重复显示的问题
  - 问题原因1：每个StreamChunk都会yield一个包含所有累积内容的消息，导致UI重复显示相同内容
  - 问题原因2：CodeMinion.execute_stream()直接yield AgentResponse，导致pull_messages_from_step重复处理已通过StreamChunk显示的内容
  - 解决方案1：只对有意义的chunk内容进行yield，过滤掉纯格式化的chunk（如[STEP]标记）
  - 解决方案2：修复CodeMinion.execute_stream()确保yield的是StreamChunk兼容对象，利用AgentResponse继承StreamChunk的特性
  - 解决方案3：改进gradio_ui中skip_model_outputs的逻辑，避免重复处理
  - 解决方案4：修复interact_with_agent中的消息状态管理逻辑，区分pending消息更新和done消息添加
  - 问题原因3：原smolagents从step extract messages，但minion直接yield StreamChunk->gr.ChatMessage，导致pending消息被错误地标记为done
  - 现在Gradio UI会正确累积内容、管理消息状态，并避免重复显示

### **开发流程记忆**
- 如果是一定功能的修改的话,尽可能添加test,先跑通test
- 如果非常简单的修改可以不用test
- 另外添加的文件请git add 到版本库里
- 如果是修改examples,也请改完之后试跑该example,修改必要的bug,直到跑通为止
