## 🧠 **记忆存储**

### **系统架构记忆**
- never put test in the top level folder
- agent.run_async() 返回的是一个async函数，需要先await才能获得async generator
  - 正确用法: `async for event in (await agent.run_async(input_obj, **kwargs)):`
  - 错误用法: `async for event in agent.run_async(input_obj, **kwargs):`
  - 这是因为run_async是async函数，它delegate到其他函数，本身需要await才能返回真正的async generator

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

### **开发流程记忆**
- 如果是一定功能的修改的话,尽可能添加test,先跑通test
- 如果非常简单的修改可以不用test
- 另外添加的文件请git add 到版本库里
- 如果是修改examples,也请改完之后试跑该example,修改必要的bug,直到跑通为止
