# Multimodal Query Support

This document explains how to use the new multimodal query support in the minion framework, which allows you to handle text, images, and other multimedia content in your queries.

## Overview

The minion framework now supports multimodal queries through:

1. **Enhanced Template Engine**: New utility functions for constructing OpenAI-compatible messages from Jinja2 templates
2. **Multimodal Input Support**: Support for query inputs that contain both text and multimedia content
3. **Backward Compatibility**: Existing string-based queries continue to work as before

## Key Features

### 1. Template-Based Message Construction

The new `construct_messages_from_template()` function handles the conversion of Jinja2 templates to OpenAI message format:

```python
from minion.utils.template import construct_messages_from_template

# Template with query placeholder
template = """
You are a helpful assistant.

User Query: {{input.query}}

Please provide a detailed response.
"""

# Create input object with system_prompt
input_obj = Input(
    query="Your question here",
    system_prompt="You are a helpful assistant."
)

messages = construct_messages_from_template(template, input_obj)
```

### 2. Multimodal Query Support

You can now pass queries that contain both text and multimedia content:

```python
# Text + Image query
multimodal_query = [
    "Please analyze this image:",
    {
        "type": "image_url",
        "image_url": {
            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD//..."
        }
    },
    "What do you see in the image?"
]

input_obj = Input(
    query=multimodal_query,
    query_type="image_analysis",
    system_prompt="You are a helpful assistant."
)
```

### 3. Simple Message Construction

For simple cases, use `construct_simple_message()`:

```python
from minion.utils.template import construct_simple_message
from minion.main.input import Input

# Method 1: Using Input object (recommended)
input_obj = Input(
    query="What is the capital of France?",
    system_prompt="You are a helpful assistant."
)
messages = construct_simple_message(input_obj)

# Method 2: Direct content with system_prompt parameter
messages = construct_simple_message(
    "What is the capital of France?",
    system_prompt="You are a helpful assistant."
)

# Multimodal message with Input object
multimodal_input = Input(
    query=["Analyze this image:", {"type": "image_url", "image_url": {"url": "..."}}],
    system_prompt="You are a helpful assistant."
)
messages = construct_simple_message(multimodal_input)
```

## Usage Examples

### Basic Text Query

```python
from minion.main.brain import Brain
from minion.main.input import Input

brain = Brain()

input_obj = Input(
    query="What is machine learning?",
    query_type="question",
    system_prompt="You are a helpful AI assistant."
)

answer, cost, terminated, truncated, info = await brain.step(input=input_obj)
print(answer)
```

### Multimodal Query

```python
from minion.main.brain import Brain
from minion.main.input import Input

brain = Brain()

# Query with text and image
multimodal_query = [
    "Please analyze this chart and explain the trends:",
    {
        "type": "image_url",
        "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        }
    },
    "Focus on any patterns or anomalies you notice."
]

input_obj = Input(
    query=multimodal_query,
    query_type="chart_analysis",
    system_prompt="You are a data analyst."
)

answer, cost, terminated, truncated, info = await brain.step(input=input_obj)
print(answer)
```

### Direct Message Passing

```python
from minion.main.brain import Brain

brain = Brain()

# Pass messages directly to brain.step
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": [
        {"type": "text", "text": "What do you see in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]}
]

answer, cost, terminated, truncated, info = await brain.step(
    messages=messages,
    query_type="image_question"
)
print(answer)
```

## Supported Worker Minions

The following worker minions have been updated to support multimodal queries:

- **RawMinion**: Direct LLM queries with multimodal support
- **NativeMinion**: Template-based queries with multimodal support
- **CotMinion**: Chain-of-thought reasoning with multimodal support
- **DcotMinion**: Dynamic chain-of-thought with multimodal support

## Implementation Details

### Template Processing

When a template contains `{{input.query}}` and the query is a list (multimodal), the system:

1. Splits the template around the `{{input.query}}` placeholder
2. Renders the prefix and suffix parts using Jinja2
3. Constructs an OpenAI-compatible message with mixed content types
4. Combines text and multimedia elements appropriately

### Message Format

The system automatically converts different input formats to OpenAI message format:

```python
# Input: Simple string
"Hello world"

# Output: OpenAI message
[{"role": "user", "content": "Hello world"}]

# Input: Multimodal list
["Analyze this:", {"type": "image_url", "image_url": {"url": "..."}}]

# Output: OpenAI message
[{"role": "user", "content": [
    {"type": "text", "text": "Analyze this:"},
    {"type": "image_url", "image_url": {"url": "..."}}
]}]
```

### Backward Compatibility

Existing code that uses string-based queries will continue to work without modification. The new functionality is additive and doesn't break existing behavior.

## Error Handling

The system gracefully handles various input formats:

- Empty queries
- Mixed content types
- Invalid image URLs
- Missing template placeholders

## Best Practices

1. **Use appropriate query types**: Set `query_type` to indicate the nature of your query (e.g., "image_analysis", "chart_analysis")
2. **Provide clear system prompts**: Help the model understand its role, especially for multimodal tasks
3. **Handle image encoding**: Ensure images are properly base64-encoded for the OpenAI API
4. **Test with various input types**: Verify your code works with both text and multimodal inputs

## Example Files

See `examples/multimodal_query_example.py` for a complete working example demonstrating all features.

## Future Enhancements

Planned improvements include:

- Support for audio and video content
- Advanced template features for multimedia
- Better error handling and validation
- Performance optimizations for large media files 