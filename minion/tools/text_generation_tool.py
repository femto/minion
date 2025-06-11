#!/usr/bin/env python3
"""
Text Generation Tool for pure text creation tasks
"""

from minion.tools.base_tool import BaseTool


class TextGenerationTool(BaseTool):
    """
    Tool for generating text content directly
    Useful for writing, creative tasks, explanations, etc.
    """
    
    name = "text_generator"
    description = "Generate text content directly for writing, creative tasks, explanations, and other text-based work"
    inputs = {
        "task": {
            "type": "string",
            "description": "The text generation task to complete"
        },
        "content": {
            "type": "string", 
            "description": "The text content to generate or write"
        },
        "format": {
            "type": "string",
            "description": "Optional format specification (e.g., 'novel', 'outline', 'article', 'story')",
            "default": "text"
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
    
    def forward(self, task: str, content: str, format: str = "text") -> str:
        """
        Generate text content based on the task and input content
        
        Args:
            task: Description of what text to generate
            content: The actual text content
            format: Format specification
            
        Returns:
            The generated text content
        """
        # For a text generation tool, we simply format and return the content
        # The LLM should have already generated the content in the "content" parameter
        
        if format.lower() in ["novel", "story", "fiction"]:
            result = f"=== {task} ===\n\n{content}\n\n=== End of {format} ===\n"
        elif format.lower() in ["outline", "plan"]:
            result = f"=== {task} ===\n\n{content}\n"
        elif format.lower() in ["article", "essay"]:
            result = f"# {task}\n\n{content}\n"
        else:
            result = content
        
        return result
    
    def get_examples(self) -> list:
        """Return example usage patterns"""
        return [
            {
                "task": "Write a short story about space exploration",
                "content": "Captain Sarah gazed out at the stars...",
                "format": "story"
            },
            {
                "task": "Create an outline for a fantasy novel",
                "content": "Chapter 1: The Discovery\n- Hero finds magical artifact\n- Meets mentor",
                "format": "outline"
            },
            {
                "task": "Explain quantum physics simply",
                "content": "Quantum physics is the study of very small particles...",
                "format": "article"
            }
        ] 