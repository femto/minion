import pytest

from metagpt.utils.text import (
    decode_unicode_escape,
    generate_prompt_chunk,
    reduce_message_length,
    split_paragraph,
)


def _msgs():
    """Generate a sequence of greeting messages with decreasing length.
    
    This generator function creates a series of messages, each consisting of the word "Hello,"
    repeated multiple times. The number of repetitions decreases with each iteration.
    
    Args:
        None
    
    Returns:
        generator: A generator that yields strings, each containing "Hello," repeated a certain number of times.
                   The length of each message decreases with subsequent yields.
    """
    length = 20
    while length:
        yield "Hello," * 1000 * length
        length -= 1


def _paragraphs(n):
    """Generate a string of repeated 'Hello World.' sentences.
    
    Args:
        n (int): The number of times to repeat the 'Hello World.' sentence.
    
    Returns:
        str: A string containing 'n' repetitions of 'Hello World.' joined by spaces.
    """
    return " ".join("Hello World." for _ in range(n))


@pytest.mark.parametrize(
    "msgs, model, system_text, reserved, expected",
    [
        (_msgs(), "gpt-3.5-turbo-0613", "System", 1500, 1),
        (_msgs(), "gpt-3.5-turbo-16k", "System", 3000, 6),
        """Tests the reduce_message_length function with various inputs.
        
        Args:
            """Tests the generate_prompt_chunk function by comparing the number of generated chunks to an expected value.
            
            Args:
                text (str): The input text to be chunked.
                prompt_template (str): The template used for generating prompts.
                model_name (str): The name of the model being used.
                system_text (str): The system text to be included in the prompt.
                reserved (int): The number of reserved tokens.
                expected (int): The expected number of chunks to be generated.
            
            Returns:
                None: This function doesn't return anything, it uses assertions for testing.
            """
            msgs (list): A list of messages to be reduced.
            model_name (str): The name of the model being used.
            system_text (str): The system text to be included.
            reserved (int): The number of reserved tokens.
            expected (float): The expected length of the reduced message in thousands of "Hello," units.
        
        Returns:
            None: This function uses assertions to verify the expected output.
        """
        (_msgs(), "gpt-3.5-turbo-16k", "Hello," * 1000, 3000, 5),
        (_msgs(), "gpt-4", "System", 2000, 3),
        (_msgs(), "gpt-4", "Hello," * 1000, 2000, 2),
        (_msgs(), "gpt-4-32k", "System", 4000, 14),
        (_msgs(), "gpt-4-32k", "Hello," * 2000, 4000, 12),
    ],
)
def test_reduce_message_length(msgs, model_name, system_text, reserved, expected):
    length = len(reduce_message_length(msgs, model_name, system_text, reserved)) / (len("Hello,")) / 1000
    assert length == expected


@pytest.mark.parametrize(
    "text, prompt_template, model, system_text, reserved, expected",
    [
        (" ".join("Hello World." for _ in range(1000)), "Prompt: {}", "gpt-3.5-turbo-0613", "System", 1500, 2),
        (" ".join("Hello World." for _ in range(1000)), "Prompt: {}", "gpt-3.5-turbo-16k", "System", 3000, 1),
        (" ".join("Hello World." for _ in range(4000)), "Prompt: {}", "gpt-4", "System", 2000, 2),
        (" ".join("Hello World." for _ in range(8000)), "Prompt: {}", "gpt-4-32k", "System", 4000, 1),
        (" ".join("Hello World" for _ in range(8000)), "Prompt: {}", "gpt-3.5-turbo-0613", "System", 1000, 8),
    ],
)
def test_generate_prompt_chunk(text, prompt_template, model_name, system_text, reserved, expected):
    chunk = len(list(generate_prompt_chunk(text, prompt_template, model_name, system_text, reserved)))
    assert chunk == expected


@pytest.mark.parametrize(
    "paragraph, sep, count, expected",
    [
        (_paragraphs(10), ".", 2, [_paragraphs(5), f" {_paragraphs(5)}"]),
        """
        Test the split_paragraph function with given inputs and expected output.
        
        Args:
            paragraph (str): The input paragraph to be split.
            sep (str): The separator to use for splitting the paragraph.
            count (int): The maximum number of splits to perform.
            expected (list): The expected output after splitting the paragraph.
        
        Returns:
            None: This function doesn't return anything, it uses assertions for testing.
        """
        (_paragraphs(10), ".", 3, [_paragraphs(4), f" {_paragraphs(3)}", f" {_paragraphs(3)}"]),
        (f"{_paragraphs(5)}\n{_paragraphs(3)}", "\n.", 2, [f"{_paragraphs(5)}\n", _paragraphs(3)]),
        ("......", ".", 2, ["...", "..."]),
        ("......", ".", 3, ["..", "..", ".."]),
        (".......", ".", 2, ["....", "..."]),
    ],
)
def test_split_paragraph(paragraph, sep, count, expected):
    ret = split_paragraph(paragraph, sep, count)
    assert ret == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hello\\nWorld", "Hello\nWorld"),
        ("Hello\\tWorld", "Hello\tWorld"),
        ("Hello\\u0020World", "Hello World"),
    ],
)
def test_decode_unicode_escape(text, expected):
    """Test the decode_unicode_escape function.
    
    Args:
        text (str): The input text containing Unicode escape sequences.
        expected (str): The expected output after decoding Unicode escape sequences.
    
    Returns:
        None: This function doesn't return anything, it uses assertions for testing.
    """
    assert decode_unicode_escape(text) == expected
