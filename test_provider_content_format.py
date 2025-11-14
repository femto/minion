#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test to understand content block format for different LLM providers

Based on official documentation:
- OpenAI: https://platform.openai.com/docs/api-reference/chat/create
- Anthropic Claude: https://docs.claude.com/en/api/messages
"""

print("=" * 80)
print("Content Block Format Comparison")
print("=" * 80)

print("\n1. Anthropic Claude API Format")
print("-" * 40)
print("According to Claude API docs (https://docs.claude.com/en/api/messages):")
print()
print("Text content blocks use 'text' field:")
print("""
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "Hello, Claude"  ← Uses 'text' field
    }
  ]
}
""")

print("\n2. OpenAI API Format")
print("-" * 40)
print("According to OpenAI API docs:")
print()
print("For multimodal content, text blocks also use 'text' field:")
print("""
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "What's in this image?"  ← Uses 'text' field
    },
    {
      "type": "image_url",
      "image_url": {"url": "https://..."}
    }
  ]
}
""")

print("\n3. Standard Format")
print("-" * 40)
print("Both OpenAI and Anthropic use the SAME format for content blocks:")
print()
print("  {\"type\": \"text\", \"text\": \"...\"}")
print()
print("NOT:")
print("  {\"type\": \"text\", \"content\": \"...\"}")
print()

print("\n4. Why did 'content' field seem to work?")
print("-" * 40)
print("Possible reasons:")
print("1. Some LLM providers are more lenient and accept both 'text' and 'content'")
print("2. LiteLLM or wrapper libraries might normalize the format")
print("3. The field was silently ignored and default behavior was used")
print()

print("\n5. Conclusion")
print("-" * 40)
print("✓ Standard format: {\"type\": \"text\", \"text\": \"...\"}")
print("✓ Both OpenAI and Anthropic Claude expect 'text' field")
print("✓ Using 'content' field is non-standard and may cause issues")
print()
print("Recommendation: Always use 'text' field for text content blocks")
print("=" * 80)
