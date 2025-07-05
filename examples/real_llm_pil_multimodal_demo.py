#!/usr/bin/env python3
"""
Real LLM + PIL.Image Multimodal Demo
====================================

This demo connects to actual LLM providers to test PIL.Image multimodal functionality.
Uses the existing minion config system like smart_minion/brain.py.

Usage:
    python examples/real_llm_pil_multimodal_demo.py
"""

import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from minion import config
from minion.main.brain import Brain
from minion.main.input import Input
from minion.providers import create_llm_provider


def create_test_images():
    """创建测试用的PIL图像"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        images = {}
        
        # 1. 简单的彩色方块
        img1 = Image.new('RGB', (200, 200), color='red')
        images['red_square'] = img1
        
        # 2. 渐变图像
        img2 = Image.new('RGB', (200, 100))
        for x in range(200):
            for y in range(100):
                img2.putpixel((x, y), (int(255 * x / 200), int(255 * y / 100), 128))
        images['gradient'] = img2
        
        # 3. 带文字的图像
        img3 = Image.new('RGB', (300, 100), color='white')
        draw = ImageDraw.Draw(img3)
        try:
            # 尝试使用默认字体
            draw.text((10, 30), "Hello AI! Can you read this?", fill='black')
        except:
            # 如果没有字体，使用默认
            draw.text((10, 30), "Hello AI! Can you read this?", fill='black')
        images['text_image'] = img3
        
        # 4. 几何图形
        img4 = Image.new('RGB', (200, 200), color='lightblue')
        draw = ImageDraw.Draw(img4)
        # 画圆
        draw.ellipse([50, 50, 150, 150], fill='yellow', outline='black', width=2)
        # 画三角形
        draw.polygon([(100, 60), (80, 90), (120, 90)], fill='red')
        images['shapes'] = img4
        
        return images
        
    except ImportError:
        print("⚠ PIL/Pillow not available. Please install: pip install Pillow")
        return {}


async def demo_basic_text_query(brain: Brain):
    """演示基本文本查询"""
    print("\n" + "="*50)
    print("Demo 1: Basic Text Query")
    print("="*50)
    
    input_data = Input(
        query="Hello! Please introduce yourself briefly.",
        system_prompt="You are a helpful AI assistant."
    )
    
    try:
        result, _, _, _, _ = await brain.step(input_data)
        print(f"✓ LLM Response: {result}")
        return True
    except Exception as e:
        print(f"❌ Basic text query failed: {e}")
        return False


async def demo_pil_image_query(brain: Brain, images: dict):
    """演示PIL.Image多模态查询"""
    print("\n" + "="*50)
    print("Demo 2: PIL.Image Multimodal Query")
    print("="*50)
    
    if not images:
        print("⚠ No images available, skipping PIL.Image test")
        return False
    
    # 选择一个测试图像
    test_image = images['red_square']
    
    input_data = Input(
        query=[
            "Please analyze this image:",
            test_image,
            "What color is it? What shape do you see?"
        ],
        system_prompt="You are an expert image analyst. Describe what you see in detail."
    )
    
    try:
        result, _, _, _, _ = await brain.step(input_data)
        print(f"✓ LLM Vision Response: {result}")
        return True
    except Exception as e:
        print(f"❌ PIL.Image query failed: {e}")
        return False


async def demo_complex_multimodal_query(brain: Brain, images: dict):
    """演示复杂的多模态查询（多张图片+文本）"""
    print("\n" + "="*50)
    print("Demo 3: Complex Multimodal Query (Multiple Images)")
    print("="*50)
    
    if len(images) < 2:
        print("⚠ Need at least 2 images for complex test, skipping")
        return False
    
    # 选择两张不同的图像
    image_names = list(images.keys())[:2]
    
    input_data = Input(
        query=[
            "I have two images to show you:",
            "Image 1:",
            images[image_names[0]],
            "Image 2:", 
            images[image_names[1]],
            "Can you compare these two images? What are the differences?"
        ],
        system_prompt="You are an expert at comparing and analyzing multiple images. Provide detailed comparisons."
    )
    
    try:
        result, _, _, _, _ = await brain.step(input_data)
        print(f"✓ Multi-image Response: {result}")
        return True
    except Exception as e:
        print(f"❌ Complex multimodal query failed: {e}")
        return False


async def demo_text_image_query(brain: Brain, images: dict):
    """演示带文字的图像理解"""
    print("\n" + "="*50)
    print("Demo 4: Text in Image Recognition")
    print("="*50)
    
    if 'text_image' not in images:
        print("⚠ No text image available, skipping text recognition test")
        return False
    
    input_data = Input(
        query=[
            "Can you read the text in this image?",
            images['text_image'],
            "What does it say exactly?"
        ],
        system_prompt="You are excellent at reading text from images. Be precise about what text you see."
    )
    
    try:
        result, _, _, _, _ = await brain.step(input_data)
        print(f"✓ Text Recognition Response: {result}")
        return True
    except Exception as e:
        print(f"❌ Text recognition query failed: {e}")
        return False


async def demo_image_file_path(brain: Brain):
    """演示图像文件路径支持"""
    print("\n" + "="*50)
    print("Demo 5: Image File Path Support")
    print("="*50)
    
    # 检查assets目录中的图像
    asset_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'minion1.webp')
    
    if not os.path.exists(asset_path):
        print("⚠ No asset image found, skipping file path test")
        return False
    
    input_data = Input(
        query=[
            "Please analyze this image file:",
            asset_path,
            "What do you see in this image? Describe it in detail."
        ],
        system_prompt="You are an image analyst. Describe the image in detail."
    )
    
    try:
        result, _, _, _, _ = await brain.step(input_data)
        print(f"✓ File Path Response: {result}")
        return True
    except Exception as e:
        print(f"❌ File path query failed: {e}")
        return False


async def main():
    """主函数，模仿smart_minion/brain.py的配置方式"""
    print("Real LLM + PIL.Image Multimodal Demo")
    print("====================================")
    print("Using minion config system (like smart_minion/brain.py)")
    
    # 1. 配置LLM（模仿smart_minion/brain.py）
    # 你可以更改这里的model来测试不同的LLM
    model = "gpt-4o-mini"  # 支持vision的模型
    # model = "gpt-4o"     # 更好的vision但更贵
    # model = "claude"     # Claude 3.5 Sonnet
    # model = "gemini-2.0-flash-exp"  # Gemini
    
    print(f"🤖 Using model: {model}")
    
    try:
        llm_config = config.models.get(model)
        if not llm_config:
            print(f"❌ Model '{model}' not found in config!")
            print("Available models:", list(config.models.keys()))
            return 1
        
        llm = create_llm_provider(llm_config)
        print(f"✓ Created LLM provider: {type(llm).__name__}")
        print(f"✓ Model: {llm_config.model}")
        print(f"✓ API Type: {llm_config.api_type}")
        
    except Exception as e:
        print(f"❌ Failed to create LLM provider: {e}")
        return 1
    
    # 2. 创建Brain（使用LocalPythonEnv避免Docker依赖）
    try:
        brain = Brain(llm=llm)  # 默认使用LocalPythonEnv
        print(f"✓ Created Brain with {type(brain.python_env).__name__}")
    except Exception as e:
        print(f"❌ Failed to create Brain: {e}")
        return 1
    
    # 3. 创建测试图像
    print("\n🎨 Creating test images...")
    images = create_test_images()
    if images:
        print(f"✓ Created {len(images)} test images: {list(images.keys())}")
    else:
        print("⚠ No images created (PIL not available)")
    
    # 4. 运行演示
    print("\n🧪 Running multimodal demos with real LLM...")
    
    demo_results = []
    
    # 基本文本演示
    result = await demo_basic_text_query(brain)
    demo_results.append(("Basic Text", result))
    
    # PIL.Image演示（需要vision模型）
    if images:
        result = await demo_pil_image_query(brain, images)
        demo_results.append(("PIL.Image", result))
        
        result = await demo_complex_multimodal_query(brain, images)
        demo_results.append(("Multi-Image", result))
        
        result = await demo_text_image_query(brain, images)
        demo_results.append(("Text Recognition", result))
    
    # 文件路径演示
    result = await demo_image_file_path(brain)
    demo_results.append(("File Path", result))
    
    # 5. 总结结果
    print("\n" + "="*50)
    print("Demo Results Summary")
    print("="*50)
    
    success_count = 0
    for demo_name, success in demo_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{demo_name:15} {status}")
        if success:
            success_count += 1
    
    print(f"\nTotal: {success_count}/{len(demo_results)} demos succeeded")
    
    if success_count == len(demo_results):
        print("\n🎉 All demos passed! PIL.Image multimodal support is working with real LLM!")
    elif success_count > 0:
        print("\n⚠️  Some demos passed. Check your LLM's vision capabilities.")
        if success_count == 1 and demo_results[0][1]:  # 只有基本文本演示通过
            print("💡 Your LLM works but may not support vision. Try a vision-enabled model like:")
            print("   - gpt-4o-mini")
            print("   - gpt-4o") 
            print("   - claude")
    else:
        print("\n❌ All demos failed. Check your LLM configuration.")
    
    # 6. 额外演示：快速计算演示（类似smart_minion/brain.py）
    print("\n" + "="*50)
    print("Bonus: Quick Math Demo (like smart_minion/brain.py)")
    print("="*50)
    
    try:
        result, _, _, _, _ = await brain.step(
            query="what's the solution 234*568",
            route="python",
            check=False
        )
        print(f"✓ Math Result: {result}")
    except Exception as e:
        print(f"❌ Math demo failed: {e}")
    
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 