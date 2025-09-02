#!/usr/bin/env python3
"""
流式输出演示
展示如何使用 Minion 系统的真正流式输出功能
"""
import asyncio
import os
import time
from datetime import datetime
from minion import config
from minion.main.brain import Brain
from minion.main.input import Input
from minion.providers import create_llm_provider

class StreamDemo:
    """流式输出演示类"""
    
    def __init__(self, model_name="gpt-4o"):
        """初始化演示"""
        # 使用配置文件中的模型配置
        self.model_name = model_name
        self.llm_config = config.models.get(model_name)
        
        if not self.llm_config:
            print(f"❌ 模型 {model_name} 在配置文件中未找到")
            print("📋 可用模型:")
            for name in config.models.keys():
                print(f"   - {name}")
            raise ValueError(f"Model {model_name} not found in config")
        
        # 创建 LLM 提供者和 Brain
        self.llm = create_llm_provider(self.llm_config)
        self.brain = Brain(llm=self.llm)
        
        print("🚀 流式输出演示初始化完成")
        print(f"📋 使用模型: {model_name}")
        print(f"🔧 API 类型: {self.llm_config.api_type}")
        print(f"🔑 配置状态: 已从 config.yaml 加载")
        print("-" * 60)

    async def demo_basic_streaming(self):
        """基础流式输出演示"""
        print("\n🔥 基础流式输出演示")
        print("=" * 50)
        
        # 创建流式输入
        input_data = Input(
            query="请详细解释什么是人工智能，包括其历史发展、主要技术和应用领域",
            stream=True  # 启用流式输出
        )
        
        print(f"📝 查询: {input_data.query}")
        print("🔄 开始流式输出:")
        print("-" * 50)
        
        start_time = time.time()
        chunk_count = 0
        total_chars = 0
        
        try:
            # 使用 Brain 进行流式输出
            stream_generator = await self.brain.step({"input": input_data})
            
            async for chunk in stream_generator:
                # 处理 StreamChunk 对象或字符串
                if hasattr(chunk, 'content'):
                    content = chunk.content
                else:
                    content = str(chunk)
                
                # 实时输出每个块
                print(content, end='', flush=True)
                chunk_count += 1
                total_chars += len(content)
                
                # 添加小延迟以更好地展示流式效果
                await asyncio.sleep(0.01)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\n{'-' * 50}")
            print(f"✅ 流式输出完成!")
            print(f"📊 统计信息:")
            print(f"   - 总块数: {chunk_count}")
            print(f"   - 总字符数: {total_chars}")
            print(f"   - 耗时: {duration:.2f} 秒")
            print(f"   - 平均速度: {total_chars/duration:.1f} 字符/秒")
            
        except Exception as e:
            print(f"\n❌ 流式输出失败: {e}")

    async def demo_different_minions(self):
        """不同 Minion 的流式输出演示"""
        print("\n🤖 不同 Minion 流式输出对比")
        print("=" * 50)
        
        # 测试不同的 minion 类型
        test_cases = [
            {
                "name": "RawMinion",
                "route": None,  # 使用默认路由选择
                "query": "简单介绍一下 Python 编程语言的特点",
                "description": "原始 Minion，直接与 LLM 交互"
            },
            {
                "name": "CotMinion", 
                "route": "cot",
                "query": "请一步步分析为什么 Python 适合初学者学习编程",
                "description": "思维链 Minion，逐步推理"
            },
            {
                "name": "NativeMinion",
                "route": "native", 
                "query": "Python 在数据科学领域有哪些优势？",
                "description": "原生 Minion，使用标准提示模板"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🔍 测试 {i}/{len(test_cases)}: {test_case['name']}")
            print(f"📝 描述: {test_case['description']}")
            print(f"❓ 查询: {test_case['query']}")
            print("🔄 流式输出:")
            print("-" * 40)
            
            # 创建输入
            input_data = Input(
                query=test_case['query'],
                stream=True,
                route=test_case['route']
            )
            
            start_time = time.time()
            chunk_count = 0
            
            try:
                stream_generator = await self.brain.step({"input": input_data})
                
                async for chunk in stream_generator:
                    # 处理 StreamChunk 对象或字符串
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                    else:
                        content = str(chunk)
                    
                    print(content, end='', flush=True)
                    chunk_count += 1
                    await asyncio.sleep(0.01)
                
                duration = time.time() - start_time
                print(f"\n✅ {test_case['name']} 完成 ({chunk_count} 块, {duration:.1f}s)")
                
            except Exception as e:
                print(f"\n❌ {test_case['name']} 失败: {e}")

    async def demo_streaming_vs_normal(self):
        """流式输出 vs 普通输出对比演示"""
        print("\n⚖️  流式输出 vs 普通输出对比")
        print("=" * 50)
        
        query = "请详细介绍机器学习的基本概念和主要算法类型"
        
        # 测试流式输出
        print("🔄 流式输出测试:")
        print("-" * 30)
        
        input_stream = Input(
            query=query,
            stream=True,
            route="cot"
        )
        
        stream_start = time.time()
        stream_chunks = []
        
        try:
            stream_generator = await self.brain.step({"input": input_stream})
            
            async for chunk in stream_generator:
                # 处理 StreamChunk 对象或字符串
                if hasattr(chunk, 'content'):
                    content = chunk.content
                else:
                    content = str(chunk)
                
                print(content, end='', flush=True)
                stream_chunks.append(content)
                await asyncio.sleep(0.01)
            
            stream_duration = time.time() - stream_start
            stream_result = ''.join(stream_chunks)
            
            print(f"\n📊 流式输出统计:")
            print(f"   - 块数: {len(stream_chunks)}")
            print(f"   - 总长度: {len(stream_result)} 字符")
            print(f"   - 耗时: {stream_duration:.2f} 秒")
            
        except Exception as e:
            print(f"\n❌ 流式输出失败: {e}")
            stream_result = ""
            stream_duration = 0
        
        # 测试普通输出
        print(f"\n🔄 普通输出测试:")
        print("-" * 30)
        
        input_normal = Input(
            query=query,
            stream=False,  # 禁用流式输出
            route="cot"
        )
        
        normal_start = time.time()
        
        try:
            normal_result = await self.brain.step({"input": input_normal})
            normal_duration = time.time() - normal_start
            
            # 输出结果
            if hasattr(normal_result, 'answer'):
                print(normal_result.answer)
                normal_text = normal_result.answer
            else:
                print(str(normal_result))
                normal_text = str(normal_result)
            
            print(f"\n📊 普通输出统计:")
            print(f"   - 总长度: {len(normal_text)} 字符")
            print(f"   - 耗时: {normal_duration:.2f} 秒")
            
        except Exception as e:
            print(f"\n❌ 普通输出失败: {e}")
            normal_duration = 0
            normal_text = ""
        
        # 对比结果
        print(f"\n📈 对比结果:")
        print(f"   - 流式输出: {len(stream_result)} 字符, {stream_duration:.2f}s")
        print(f"   - 普通输出: {len(normal_text)} 字符, {normal_duration:.2f}s")
        if stream_duration > 0 and normal_duration > 0:
            print(f"   - 速度对比: 流式 {len(stream_result)/stream_duration:.1f} vs 普通 {len(normal_text)/normal_duration:.1f} 字符/秒")

    async def demo_interactive_streaming(self):
        """交互式流式输出演示"""
        print("\n💬 交互式流式输出演示")
        print("=" * 50)
        print("输入 'quit' 或 'exit' 退出演示")
        print("输入 'help' 查看可用命令")
        print("-" * 50)
        
        while True:
            try:
                # 获取用户输入
                user_query = input("\n🤔 请输入您的问题: ").strip()
                
                if user_query.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见！")
                    break
                
                if user_query.lower() == 'help':
                    print("📋 可用命令:")
                    print("   - 直接输入问题进行流式对话")
                    print("   - 'quit' 或 'exit': 退出演示")
                    print("   - 'help': 显示此帮助信息")
                    continue
                
                if not user_query:
                    print("⚠️  请输入有效的问题")
                    continue
                
                # 创建流式输入
                input_data = Input(
                    query=user_query,
                    stream=True,
                    route="cot"  # 使用思维链推理
                )
                
                print(f"\n🤖 AI 回答:")
                print("-" * 30)
                
                start_time = time.time()
                chunk_count = 0
                
                # 流式输出回答
                stream_generator = await self.brain.step({"input": input_data})
                
                async for chunk in stream_generator:
                    # 处理 StreamChunk 对象或字符串
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                    else:
                        content = str(chunk)
                    
                    print(content, end='', flush=True)
                    chunk_count += 1
                    await asyncio.sleep(0.01)
                
                duration = time.time() - start_time
                print(f"\n{'-' * 30}")
                print(f"📊 ({chunk_count} 块, {duration:.1f}s)")
                
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，退出演示")
                break
            except Exception as e:
                print(f"\n❌ 处理失败: {e}")

    async def demo_advanced_features(self):
        """高级功能演示"""
        print("\n🚀 高级流式输出功能演示")
        print("=" * 50)
        
        # 演示带系统提示的流式输出
        print("🎭 带系统提示的流式输出:")
        print("-" * 40)
        
        input_data = Input(
            query="请介绍一下量子计算的基本原理",
            system_prompt="你是一位专业的物理学教授，请用通俗易懂的语言解释复杂的科学概念。",
            stream=True,
            route="cot"
        )
        
        try:
            stream_generator = await self.brain.step({"input": input_data})
            
            async for chunk in stream_generator:
                # 处理 StreamChunk 对象或字符串
                if hasattr(chunk, 'content'):
                    content = chunk.content
                else:
                    content = str(chunk)
                
                print(content, end='', flush=True)
                await asyncio.sleep(0.01)
            
            print("\n✅ 系统提示演示完成")
            
        except Exception as e:
            print(f"\n❌ 系统提示演示失败: {e}")

    async def run_all_demos(self):
        """运行所有演示"""
        print("🎯 Minion 流式输出完整演示")
        print("=" * 60)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 检查配置
        if not self.llm_config:
            print(f"\n⚠️  警告: 模型 {self.model_name} 配置无效")
            print("请检查 config/config.yaml 文件")
            return
        
        try:
            # 运行各种演示
            await self.demo_basic_streaming()
            await self.demo_different_minions()
            await self.demo_streaming_vs_normal()
            await self.demo_advanced_features()
            
            print(f"\n🎉 所有演示完成!")
            print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 询问是否进行交互式演示
            try:
                choice = input("\n🤔 是否进行交互式演示? (y/n): ").strip().lower()
                if choice in ['y', 'yes', '是']:
                    await self.demo_interactive_streaming()
            except KeyboardInterrupt:
                print("\n👋 演示结束")
                
        except Exception as e:
            print(f"\n❌ 演示过程中发生错误: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """主函数"""
    # 可以选择不同的模型进行测试
    # 可用模型: gpt-4o, gpt-4o-mini, chatgpt-4o-latest, claude-3.5, llama3.2 等
    demo = StreamDemo(model_name="gpt-4o")  # 使用 Azure GPT-4o
    await demo.run_all_demos()

if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())