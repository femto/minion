#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Think in Code 完整演示
运行所有演示和测试
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

async def run_all_demos():
    """运行所有Think in Code演示"""
    print("🎯 Think in Code 完整功能演示")
    print("=" * 80)
    print("这个演示将展示Meta工具在不同场景下的使用")
    print("=" * 80)
    
    demos = [
        ("基础Meta工具演示", "basic_demo.py"),
        ("代码执行中的Meta工具", "code_execution_demo.py"), 
        ("真实CodeAgent演示", "real_code_agent_demo.py")
    ]
    
    for i, (title, script) in enumerate(demos, 1):
        print(f"\n📋 演示 {i}: {title}")
        print("-" * 60)
        
        try:
            # 动态导入并运行演示
            script_name = script.replace('.py', '')
            
            if script_name == "basic_demo":
                from . import basic_demo
                await basic_demo.basic_meta_tools_demo()
                
            elif script_name == "code_execution_demo":
                from . import code_execution_demo
                await code_execution_demo.code_execution_demo()
                await code_execution_demo.algorithm_development_demo()
                
            elif script_name == "real_code_agent_demo":
                from . import real_code_agent_demo
                await real_code_agent_demo.demo_thinking_code_agent()
                await real_code_agent_demo.demo_simulated_thinking()
                
            print(f"✅ 演示 {i} 完成")
            
        except Exception as e:
            print(f"❌ 演示 {i} 执行失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
        
        if i < len(demos):
            print("\n" + "🔄 准备下一个演示..." + "\n")
            await asyncio.sleep(1)  # 短暂暂停
    
    print("\n" + "=" * 80)
    print("🎉 所有演示完成!")
    print("=" * 80)
    
    print("\n📊 Think in Code 功能总结:")
    print("   🧠 ThinkInCodeTool  - 内部思考和推理分析")
    print("   📋 PlanTool        - 任务规划和步骤管理") 
    print("   🔍 ReflectionTool  - 自我反思和学习改进")
    print("   💻 CodeExecution   - 代码中透明调用Meta工具")
    print("   🤖 SmartCodeAgent  - 自动根据任务复杂度使用Meta工具")
    
    print("\n🚀 应用场景:")
    print("   • 复杂算法开发和优化")
    print("   • 数据分析和科学计算")
    print("   • 代码调试和错误分析")
    print("   • 架构设计和系统规划")
    print("   • 自动化测试和验证")
    
    print("\n📖 更多信息:")
    print("   • 使用指南: THINK_IN_CODE_GUIDE.md")
    print("   • 基础演示: examples/think_in_code/basic_demo.py")
    print("   • 代码执行: examples/think_in_code/code_execution_demo.py")
    print("   • 真实应用: examples/think_in_code/real_code_agent_demo.py")

# 单独的快速测试功能
async def quick_test():
    """快速测试Meta工具基础功能"""
    print("⚡ Think in Code 快速测试\n")
    
    from minion.tools.think_in_code_tool import ThinkInCodeTool
    from minion.tools.meta_tools import PlanTool, ReflectionTool
    
    # 快速测试ThinkInCodeTool
    print("🧠 测试ThinkInCodeTool...")
    think_tool = ThinkInCodeTool()
    result = await think_tool.forward("快速测试思考功能")
    print(f"   ✅ 思考完成: {result['thinking_complete']}")
    
    # 快速测试PlanTool
    print("📋 测试PlanTool...")
    plan_tool = PlanTool()
    result = await plan_tool.forward("create", {
        "title": "测试计划",
        "steps": ["步骤1", "步骤2"]
    })
    print(f"   ✅ 计划创建: {result['plan_created']}")
    
    # 快速测试ReflectionTool
    print("🔍 测试ReflectionTool...")
    reflect_tool = ReflectionTool()
    result = await reflect_tool.forward("process", {"test": True})
    print(f"   ✅ 反思完成: {result['reflection_complete']}")
    
    print("\n🎉 快速测试完成! 所有Meta工具正常工作.")

# 交互式菜单
async def interactive_demo():
    """交互式演示菜单"""
    while True:
        print("\n🎮 Think in Code 交互式演示")
        print("=" * 40)
        print("1. 运行所有演示")
        print("2. 基础Meta工具演示")
        print("3. 代码执行演示")
        print("4. 真实CodeAgent演示")
        print("5. 快速测试")
        print("0. 退出")
        print("=" * 40)
        
        try:
            choice = input("请选择 (0-5): ").strip()
            
            if choice == "0":
                print("👋 感谢使用Think in Code演示!")
                break
            elif choice == "1":
                await run_all_demos()
            elif choice == "2":
                from . import basic_demo
                await basic_demo.basic_meta_tools_demo()
            elif choice == "3":
                from . import code_execution_demo
                await code_execution_demo.code_execution_demo()
            elif choice == "4":
                from . import real_code_agent_demo
                await real_code_agent_demo.demo_thinking_code_agent()
            elif choice == "5":
                await quick_test()
            else:
                print("❌ 无效选择，请重试")
                
        except KeyboardInterrupt:
            print("\n👋 演示被用户中断")
            break
        except Exception as e:
            print(f"❌ 执行错误: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Think in Code 演示")
    parser.add_argument("--mode", choices=["all", "quick", "interactive"], 
                       default="interactive", help="演示模式")
    
    args = parser.parse_args()
    
    if args.mode == "all":
        asyncio.run(run_all_demos())
    elif args.mode == "quick":
        asyncio.run(quick_test())
    else:
        asyncio.run(interactive_demo())