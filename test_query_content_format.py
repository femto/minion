#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test for query content format normalization in CodeMinion.construct_current_turn_messages()
"""

# Mock the query processing logic from CodeMinion.construct_current_turn_messages()
def normalize_query_content(query):
    """
    Simulate the query normalization logic from worker.py lines 1203-1223
    """
    user_content_parts = []

    if isinstance(query, str):
        user_content_parts.append({"type": "text", "text": f"**Problem:** {query}"})
    elif isinstance(query, list):
        # Add problem header
        user_content_parts.append({"type": "text", "text": "**Problem:**"})
        # Add multimodal content
        for item in query:
            if isinstance(item, dict):
                # Normalize content block format
                # Handle both "content" and "text" field names
                if item.get("type") == "text":
                    # Extract text from either "content" or "text" field
                    text_content = item.get("text") or item.get("content", "")
                    user_content_parts.append({"type": "text", "text": text_content})
                else:
                    # Other content types (image, etc.), keep as is
                    user_content_parts.append(item)
            elif isinstance(item, str):
                # Plain text
                user_content_parts.append({"type": "text", "text": item})
            else:
                # Convert other types to text
                user_content_parts.append({"type": "text", "text": str(item)})

    return user_content_parts

def test_case_1_content_field():
    """Test: query with 'content' field (the problematic case)"""
    print("\n=== Test Case 1: Query with 'content' field ===")
    query = [{"type": "text", "content": "what's the solution 234*568"}]

    result = normalize_query_content(query)

    print(f"Input:  {query}")
    print(f"Output: {result}")

    # Verify the output
    assert len(result) == 2, "Should have 2 parts: header + content"
    assert result[0] == {"type": "text", "text": "**Problem:**"}, "First part should be header"
    assert result[1] == {"type": "text", "text": "what's the solution 234*568"}, "Second part should have normalized 'text' field"

    # Check that 'content' field was converted to 'text' field
    assert "content" not in result[1], "Should not have 'content' field"
    assert "text" in result[1], "Should have 'text' field"

    print("✓ PASS: 'content' field correctly normalized to 'text' field")

def test_case_2_text_field():
    """Test: query with 'text' field (already correct format)"""
    print("\n=== Test Case 2: Query with 'text' field ===")
    query = [{"type": "text", "text": "what's 5 + 10?"}]

    result = normalize_query_content(query)

    print(f"Input:  {query}")
    print(f"Output: {result}")

    assert len(result) == 2, "Should have 2 parts: header + content"
    assert result[1] == {"type": "text", "text": "what's 5 + 10?"}, "Should preserve 'text' field"

    print("✓ PASS: 'text' field preserved correctly")

def test_case_3_plain_string():
    """Test: query as plain string"""
    print("\n=== Test Case 3: Query as plain string ===")
    query = "Calculate 100 * 25"

    result = normalize_query_content(query)

    print(f"Input:  {query}")
    print(f"Output: {result}")

    assert len(result) == 1, "Should have 1 part"
    assert result[0] == {"type": "text", "text": "**Problem:** Calculate 100 * 25"}, "Should wrap string correctly"

    print("✓ PASS: Plain string handled correctly")

def test_case_4_mixed_content():
    """Test: query with mixed content types"""
    print("\n=== Test Case 4: Query with mixed content ===")
    query = [
        {"type": "text", "content": "First part"},
        {"type": "text", "text": "Second part"},
        "Third part as string"
    ]

    result = normalize_query_content(query)

    print(f"Input:  {query}")
    print(f"Output: {result}")

    assert len(result) == 4, "Should have 4 parts: header + 3 content parts"
    assert result[1] == {"type": "text", "text": "First part"}, "First content should be normalized"
    assert result[2] == {"type": "text", "text": "Second part"}, "Second content should be preserved"
    assert result[3] == {"type": "text", "text": "Third part as string"}, "String should be wrapped"

    print("✓ PASS: Mixed content handled correctly")

def test_case_5_non_text_type():
    """Test: query with non-text content type (like image)"""
    print("\n=== Test Case 5: Query with non-text content type ===")
    query = [
        {"type": "text", "content": "Analyze this image"},
        {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
    ]

    result = normalize_query_content(query)

    print(f"Input:  {query}")
    print(f"Output: {result}")

    assert len(result) == 3, "Should have 3 parts: header + text + image"
    assert result[1] == {"type": "text", "text": "Analyze this image"}, "Text should be normalized"
    assert result[2] == {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}, "Image should be kept as is"

    print("✓ PASS: Non-text content preserved correctly")

if __name__ == "__main__":
    print("Testing Query Content Format Normalization")
    print("=" * 60)

    try:
        test_case_1_content_field()
        test_case_2_text_field()
        test_case_3_plain_string()
        test_case_4_mixed_content()
        test_case_5_non_text_type()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("\nSummary of fix:")
        print("1. Detects content blocks with 'content' field instead of 'text' field")
        print("2. Normalizes to standard format: {'type': 'text', 'text': '...'}")
        print("3. Handles mixed content types correctly")
        print("4. Preserves non-text content types (images, etc.)")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
