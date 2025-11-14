#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test _format_multimodal_content normalization fix
"""
import sys
from pathlib import Path

# Mock the _format_multimodal_content function with the fix
def _format_multimodal_content_fixed(item):
    """Fixed version with content field normalization"""
    if isinstance(item, str):
        # Text string
        return {"type": "text", "text": item}

    elif isinstance(item, dict):
        # 规范化 content block 格式
        # OpenAI 和 Anthropic 都使用 {"type": "text", "text": "..."} 格式
        if item.get("type") == "text":
            # 提取文本内容，支持 "text" 或 "content" 字段（向后兼容）
            text_content = item.get("text") or item.get("content", "")
            return {"type": "text", "text": text_content}
        else:
            # 其他类型（image_url 等）保持不变
            return item

    else:
        # Other types, convert to text
        return {"type": "text", "text": str(item)}

def test_text_field():
    """Test: content block with 'text' field (standard format)"""
    print("\n=== Test 1: Standard format with 'text' field ===")
    item = {"type": "text", "text": "Hello, world!"}
    result = _format_multimodal_content_fixed(item)

    print(f"Input:  {item}")
    print(f"Output: {result}")

    assert result == {"type": "text", "text": "Hello, world!"}, "Should preserve 'text' field"
    assert "content" not in result, "Should not have 'content' field"
    print("✓ PASS: Standard format preserved")

def test_content_field():
    """Test: content block with 'content' field (non-standard, needs normalization)"""
    print("\n=== Test 2: Non-standard format with 'content' field ===")
    item = {"type": "text", "content": "what's the solution 234*568"}
    result = _format_multimodal_content_fixed(item)

    print(f"Input:  {item}")
    print(f"Output: {result}")

    assert result == {"type": "text", "text": "what's the solution 234*568"}, "Should normalize to 'text' field"
    assert "content" not in result, "Should not have 'content' field in output"
    print("✓ PASS: Non-standard 'content' field normalized to 'text' field")

def test_both_fields():
    """Test: content block with both 'text' and 'content' fields (prefer 'text')"""
    print("\n=== Test 3: Both 'text' and 'content' fields present ===")
    item = {"type": "text", "text": "text value", "content": "content value"}
    result = _format_multimodal_content_fixed(item)

    print(f"Input:  {item}")
    print(f"Output: {result}")

    # Should prefer 'text' field
    assert result == {"type": "text", "text": "text value"}, "Should prefer 'text' field when both present"
    print("✓ PASS: Prefers 'text' field when both are present")

def test_image_url():
    """Test: non-text content type (image_url) should be preserved"""
    print("\n=== Test 4: Non-text content type (image_url) ===")
    item = {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
    result = _format_multimodal_content_fixed(item)

    print(f"Input:  {item}")
    print(f"Output: {result}")

    assert result == item, "Non-text content types should be preserved as-is"
    print("✓ PASS: Non-text content type preserved")

def test_plain_string():
    """Test: plain string should be converted to standard format"""
    print("\n=== Test 5: Plain string ===")
    item = "Just a plain string"
    result = _format_multimodal_content_fixed(item)

    print(f"Input:  {item}")
    print(f"Output: {result}")

    assert result == {"type": "text", "text": "Just a plain string"}, "Plain string should be wrapped"
    print("✓ PASS: Plain string converted to standard format")

def test_empty_content():
    """Test: empty 'content' field"""
    print("\n=== Test 6: Empty 'content' field ===")
    item = {"type": "text", "content": ""}
    result = _format_multimodal_content_fixed(item)

    print(f"Input:  {item}")
    print(f"Output: {result}")

    assert result == {"type": "text", "text": ""}, "Empty content should result in empty text"
    print("✓ PASS: Empty content handled correctly")

if __name__ == "__main__":
    print("Testing _format_multimodal_content normalization")
    print("=" * 70)

    try:
        test_text_field()
        test_content_field()
        test_both_fields()
        test_image_url()
        test_plain_string()
        test_empty_content()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("\nSummary:")
        print("1. Standard format {'type': 'text', 'text': '...'} is preserved")
        print("2. Non-standard {'type': 'text', 'content': '...'} is normalized")
        print("3. When both fields present, 'text' field is preferred")
        print("4. Non-text content types (images) are preserved")
        print("5. Plain strings are wrapped in standard format")
        print("\nThis fix ensures compatibility with both OpenAI and Anthropic APIs")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
