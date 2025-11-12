#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test provider registry with bedrock_async"""

def test_registry():
    """Test if bedrock_async can be registered and loaded"""
    from minion.providers.llm_provider_registry import llm_registry

    print("=" * 60)
    print("Testing Provider Registry")
    print("=" * 60)

    # Test 1: Check if bedrock_async module can be imported
    print("\n1. Testing module import:")
    try:
        import minion.providers.bedrock_async_provider
        print("   ✓ bedrock_async_provider module imported successfully")
    except ImportError as e:
        print(f"   ✗ Failed to import bedrock_async_provider: {e}")
        return

    # Test 2: Check if bedrock_async is registered
    print("\n2. Checking registry:")
    print(f"   Registered providers: {list(llm_registry.providers.keys())}")

    if "bedrock_async" in llm_registry.providers:
        print(f"   ✓ bedrock_async is registered: {llm_registry.providers['bedrock_async']}")
    else:
        print("   ✗ bedrock_async is NOT registered")
        return

    # Test 3: Try to get the provider class
    print("\n3. Testing get_provider:")
    try:
        provider_cls = llm_registry.get_provider("bedrock_async")
        print(f"   ✓ Got provider class: {provider_cls}")
    except Exception as e:
        print(f"   ✗ Failed to get provider: {e}")
        return

    # Test 4: Try to create a provider instance
    print("\n4. Testing provider instantiation:")
    try:
        from minion.configs.config import LLMConfig
        config = LLMConfig(
            provider="bedrock_async",
            api_type="bedrock_async",
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            region="us-east-1"
        )
        provider = provider_cls(config)
        print(f"   ✓ Created provider instance: {provider}")
        print(f"   Model ID: {provider.model_id}")
        print(f"   Region: {provider.region_name}")
    except Exception as e:
        print(f"   ✗ Failed to create provider: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 5: Try using create_llm_provider
    print("\n5. Testing create_llm_provider:")
    try:
        from minion.providers import create_llm_provider
        provider2 = create_llm_provider(config)
        print(f"   ✓ Created provider via create_llm_provider: {provider2}")
    except Exception as e:
        print(f"   ✗ Failed with create_llm_provider: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_registry()
