#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tests for multimodal template functionality
"""

import pytest
from unittest.mock import MagicMock
from minion.utils.template import construct_messages_from_template, construct_simple_message
from minion.main.input import Input
from datetime import datetime


def test_construct_simple_message_text():
    """Test simple text message construction"""
    messages = construct_simple_message(
        "Hello world",
        system_prompt="You are a helpful assistant."
    )
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant."
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hello world"


def test_construct_simple_message_multimodal():
    """Test multimodal message construction"""
    multimodal_content = [
        "Analyze this image:",
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,test123"}
        }
    ]
    
    messages = construct_simple_message(
        multimodal_content,
        system_prompt="You are a helpful assistant."
    )
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant."
    assert messages[1]["role"] == "user"
    assert len(messages[1]["content"]) == 2
    assert messages[1]["content"][0]["type"] == "text"
    assert messages[1]["content"][0]["text"] == "Analyze this image:"
    assert messages[1]["content"][1]["type"] == "image_url"


def test_construct_messages_from_template_text():
    """Test template-based message construction with text query"""
    template = """
You are a helpful assistant.

User query: {{input.query}}

Please respond helpfully.
"""
    
    input_obj = Input(
        query="What is the capital of France?",
        query_type="question",
        query_time=datetime.utcnow(),
        system_prompt="You are a helpful assistant."
    )
    
    messages = construct_messages_from_template(
        template,
        input_obj
    )
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant."
    assert messages[1]["role"] == "user"
    assert "What is the capital of France?" in messages[1]["content"]


def test_construct_messages_from_template_multimodal():
    """Test template-based message construction with multimodal query"""
    template = """
Please analyze: {{input.query}}

Provide detailed analysis.
"""
    
    multimodal_query = [
        "this image:",
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,test123"}
        }
    ]
    
    input_obj = Input(
        query=multimodal_query,
        query_type="image_analysis",
        query_time=datetime.utcnow(),
        system_prompt="You are a helpful assistant."
    )
    
    messages = construct_messages_from_template(
        template,
        input_obj
    )
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant."
    assert messages[1]["role"] == "user"
    assert isinstance(messages[1]["content"], list)
    
    # Check that template parts are properly included
    content_parts = messages[1]["content"]
    text_parts = [part for part in content_parts if part.get("type") == "text"]
    image_parts = [part for part in content_parts if part.get("type") == "image_url"]
    
    assert len(text_parts) >= 1  # Should have text from template
    assert len(image_parts) == 1  # Should have one image


def test_construct_messages_no_system_prompt():
    """Test message construction without system prompt"""
    messages = construct_simple_message("Hello world")
    
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello world"


def test_construct_messages_empty_query():
    """Test message construction with empty query"""
    messages = construct_simple_message("")
    
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == ""


def test_construct_messages_dict_format():
    """Test message construction with dict format content"""
    multimodal_content = [
        "Test text",
        {"type": "image_url", "image_url": {"url": "test_url"}}
    ]
    
    messages = construct_simple_message(multimodal_content)
    
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert len(messages[0]["content"]) == 2
    assert messages[0]["content"][0]["type"] == "text"
    assert messages[0]["content"][0]["text"] == "Test text"
    assert messages[0]["content"][1]["type"] == "image_url"


def test_mixed_content_types():
    """Test handling of mixed content types"""
    mixed_content = [
        "Text part",
        {"type": "image_url", "image_url": {"url": "test"}},
        123,  # Non-string, non-dict
        "More text"
    ]
    
    messages = construct_simple_message(mixed_content)
    
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert len(messages[0]["content"]) == 4
    
    # Check type conversions
    content = messages[0]["content"]
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "Text part"
    assert content[1]["type"] == "image_url"
    assert content[2]["type"] == "text"
    assert content[2]["text"] == "123"  # Number converted to string
    assert content[3]["type"] == "text"
    assert content[3]["text"] == "More text"


def test_construct_simple_message_with_input_object():
    """Test construct_simple_message with Input object"""
    input_obj = Input(
        query="What is Python?",
        query_type="question",
        query_time=datetime.utcnow(),
        system_prompt="You are a helpful coding assistant."
    )
    
    messages = construct_simple_message(input_obj)
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful coding assistant."
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "What is Python?"


def test_construct_simple_message_with_input_object_multimodal():
    """Test construct_simple_message with Input object containing multimodal query"""
    multimodal_query = [
        "Describe this code:",
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,code_screenshot"}
        }
    ]
    
    input_obj = Input(
        query=multimodal_query,
        query_type="code_analysis",
        query_time=datetime.utcnow(),
        system_prompt="You are a helpful coding assistant."
    )
    
    messages = construct_simple_message(input_obj)
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful coding assistant."
    assert messages[1]["role"] == "user"
    assert len(messages[1]["content"]) == 2
    assert messages[1]["content"][0]["type"] == "text"
    assert messages[1]["content"][0]["text"] == "Describe this code:"


if __name__ == "__main__":
    # Run basic tests
    test_construct_simple_message_text()
    test_construct_simple_message_multimodal()
    test_construct_messages_from_template_text()
    test_construct_messages_from_template_multimodal()
    test_construct_messages_no_system_prompt()
    test_construct_messages_empty_query()
    test_construct_messages_dict_format()
    test_mixed_content_types()
    test_construct_simple_message_with_input_object()
    test_construct_simple_message_with_input_object_multimodal()
    
    print("✅ All tests passed!") 