import pytest
from unittest.mock import Mock
from minion.main.check import TestMinion
from minion.main.input import Input


class MockBrain:
    """Mock brain class for testing"""
    def __init__(self):
        self.llm = Mock()


@pytest.fixture
def test_minion():
    """Create a TestMinion instance with mock brain for testing"""
    mock_brain = MockBrain()
    mock_input = Input()  # Create an Input instance
    return TestMinion(brain=mock_brain, input=mock_input)  # Pass input to TestMinion


def test_extract_doctest_basic(test_minion):
    query = '''
    def add(x, y):
        """Add two numbers together.
        >>> add(2, 3)
        5
        >>> add(-1, 1)
        0
        """
    '''
    expected = [
        "assert add(2, 3) == 5",
        "assert add(-1, 1) == 0"
    ]
    
    result = test_minion.extract_doctest(query)
    assert result == expected


def test_extract_doctest_with_strings(test_minion):
    query = '''
    def greet(name):
        """Return a greeting string.
        >>> greet("Alice")
        'Hello, Alice!'
        >>> greet("Bob")
        "Hi, Bob!"
        """
    '''
    expected = [
        "assert greet(\"Alice\") == 'Hello, Alice!'",
        "assert greet(\"Bob\") == \"Hi, Bob!\""
    ]
    
    result = test_minion.extract_doctest(query)
    assert result == expected


def test_extract_doctest_empty(test_minion):
    query = '''
    def empty():
        """A function without doctests."""
        pass
    '''
    result = test_minion.extract_doctest(query)
    assert result == []


def test_extract_doctest_complex_types(test_minion):
    query = '''
    def process_list(items):
        """Process a list of items.
        >>> process_list([1, 2, 3])
        [2, 4, 6]
        >>> process_list([])
        []
        """
    '''
    expected = [
        "assert process_list([1, 2, 3]) == [2, 4, 6]",
        "assert process_list([]) == []"
    ]
    
    result = test_minion.extract_doctest(query)
    assert result == expected


def test_extract_doctest_multiline(test_minion):
    query = '''
    def format_data(data):
        """Format the data.
        >>> format_data({"name": "test"})
        {
            'name': 'test'
        }
        """
    '''
    expected = [
        "assert format_data({\"name\": \"test\"}) == {\n            'name': 'test'\n        }"
    ]
    
    result = test_minion.extract_doctest(query)
    assert result == expected


def test_extract_doctest_with_mixed_quotes(test_minion):
    query = '''
    def format_string(s):
        """Test with different quote styles.
        >>> format_string('single')
        "double quoted"
        >>> format_string("double")
        'single quoted'
        >>> format_string(123)
        456
        """
    '''
    expected = [
        "assert format_string('single') == \"double quoted\"",
        "assert format_string(\"double\") == 'single quoted'",
        "assert format_string(123) == 456"
    ]
    
    result = test_minion.extract_doctest(query)
    assert result == expected


def test_extract_doctest_with_complex_multiline(test_minion):
    query = '''
    def complex_output():
        """Test with complex multiline output.
        >>> complex_output()
        {
            'key1': 'value1',
            'key2': {
                'nested': 'value'
            }
        }
        """
    '''
    expected = [
        "assert complex_output() == {\n            'key1': 'value1',\n            'key2': {\n                'nested': 'value'\n            }\n        }"
    ]
    
    result = test_minion.extract_doctest(query)
    assert result == expected