#!/usr/bin/env python3
"""
基于 minion OpenAI provider 的同步流式聊天完成示例
"""

from minion import config
from minion.providers import create_llm_provider

def stream_chat_example():
    """演示同步流式聊天完成"""
    
    # 获取 LLM 配置和 provider
    model = "gpt-4o"  # 或者你想用的其他模型
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)
    
    # 获取同步客户端
    client = llm.client_sync
    
    messages = [
        {"role": "system", "content": "你是一个有用的助手。"},
        {"role": "user", "content": "请写一首关于编程的短诗"}
    ]
    
    print("开始流式响应:")
    print("-" * 50)
    
    # 创建流式聊天完成
    stream = client.chat.completions.create(
        model=llm.config.model,  # 使用配置中的模型
        messages=messages,
        stream=True,  # 启用流式响应
        max_tokens=200,
        temperature=0.7
    )
    
    # 逐步处理流式响应
    full_response = ""
    for chunk in stream:
        # 检查是否有内容
        if chunk.choices and chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)  # 实时打印，不换行
            full_response += content
    
    print("\n" + "-" * 50)
    print(f"完整响应: {full_response}")
    print(f"响应长度: {len(full_response)} 字符")

def stream_with_error_handling():
    """带错误处理的流式响应示例"""
    
    # 获取 LLM 配置和 provider
    model = "gpt-4o"
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)
    client = llm.client_sync
    
    try:
        stream = client.chat.completions.create(
            model=llm.config.model,
            messages=[
                {"role": "user", "content": "解释什么是递归"}
            ],
            stream=True,
            max_tokens=150
        )
        
        collected_messages = []
        
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                chunk_message = chunk.choices[0].delta.content
                collected_messages.append(chunk_message)
                print(chunk_message, end="")
        
        print(f"\n\n收集到 {len(collected_messages)} 个消息块")
        
    except Exception as e:
        print(f"发生错误: {e}")

def simple_stream_example():
    """最简单的流式示例"""
    
    # 模仿 brain.py 的方式
    model = "gpt-4o"
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)
    
    # 直接使用同步客户端进行流式调用
    stream = llm.client_sync.chat.completions.create(
        model=llm.config.model,
        messages=[{"role": "user", "content": "用一句话解释什么是AI"}],
        stream=True,
        max_tokens=100
    )
    
    print("AI 回答: ", end="", flush=True)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")

def stream_with_usage_example():
    """演示如何获取流式响应中的 usage 信息"""
    
    model = "gpt-4o"
    llm_config = config.models.get(model)
    llm = create_llm_provider(llm_config)
    client = llm.client_sync
    
    # 创建流式聊天完成，启用 usage 统计
    stream = client.chat.completions.create(
        model=llm.config.model,
        messages=[{"role": "user", "content": "解释什么是机器学习，用50字以内"}],
        stream=True,
        max_tokens=100,
        #stream_options={"include_usage": True}  # 关键：启用 usage 统计
    )
    
    print("流式响应: ", end="", flush=True)
    full_response = ""
    usage_info = None
    
    for chunk in stream:
        # 处理内容
        if chunk.choices and chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)
            full_response += content
        
        # 检查是否有 usage 信息（通常在最后一个 chunk）
        if hasattr(chunk, 'usage') and chunk.usage is not None:
            usage_info = chunk.usage
            print(f"\n\n📊 Usage 信息:")
            print(f"  Prompt tokens: {usage_info.prompt_tokens}")
            print(f"  Completion tokens: {usage_info.completion_tokens}")
            print(f"  Total tokens: {usage_info.total_tokens}")
    
    print(f"\n\n完整响应: {full_response}")
    
    if usage_info is None:
        print("⚠️  未获取到 usage 信息，可能需要检查 API 版本或参数设置")

if __name__ == "__main__":
    print("基于 minion OpenAI provider 的同步流式聊天示例")
    print("=" * 60)
    
    # 运行最简单的示例
    #simple_stream_example()
    
    print("=" * 60)
    
    # 运行带 usage 统计的示例
    stream_with_usage_example()
    
    print("\n" + "=" * 60)
    
    # 运行基本示例
    stream_chat_example()
    
    print("\n" + "=" * 60)
    
    # 运行带错误处理的示例
    stream_with_error_handling()