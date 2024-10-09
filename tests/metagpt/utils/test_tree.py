from pathlib import Path
from typing import List

import pytest

from metagpt.utils.tree import _print_tree, tree


@pytest.mark.parametrize(
    ("root", "rules"),
    [
        (str(Path(__file__).parent / "../.."), None),
        (str(Path(__file__).parent / "../.."), str(Path(__file__).parent / "../../../.gitignore")),
    ],
)
def test_tree(root: str, rules: str):
    """
    Test the tree function with given root directory and gitignore rules.
    
    Args:
        root (str): The root directory path to start the tree generation.
        rules (str): The gitignore rules to apply during tree generation.
    
    Returns:
        None: This function uses an assertion and does not return a value.
    """
    v = tree(root=root, gitignore=rules)
    assert v


@pytest.mark.parametrize(
    ("root", "rules"),
    [
        (str(Path(__file__).parent / "../.."), None),
        (str(Path(__file__).parent / "../.."), str(Path(__file__).parent / "../../../.gitignore")),
    ],
)
def test_tree_command(root: str, rules: str):
    """
    Test the tree command functionality with specified root and gitignore rules.
    
    Args:
        root (str): The root directory path for the tree command.
        rules (str): The gitignore rules to be applied during the tree command execution.
    
    Returns:
        None: This function doesn't return a value, but asserts the result of the tree command.
    """
    v = tree(root=root, gitignore=rules, run_command=True)
    assert v


@pytest.mark.parametrize(
    ("tree", "want"),
    [
        ({"a": {"b": {}, "c": {}}}, ["a", "+-- b", "+-- c"]),
        ({"a": {"b": {}, "c": {"d": {}}}}, ["a", "+-- b", "+-- c", "    +-- d"]),
        (
            {"a": {"b": {"e": {"f": {}, "g": {}}}, "c": {"d": {}}}},
            ["a", "+-- b", "|   +-- e", "|       +-- f", "|       +-- g", "+-- c", "    +-- d"],
        ),
        (
            {"h": {"a": {"b": {"e": {"f": {}, "g": {}}}, "c": {"d": {}}}, "i": {}}},
            [
                "h",
                "+-- a",
                "|   +-- b",
                "|   |   +-- e",
                "|   |       +-- f",
                "|   |       +-- g",
                "|   +-- c",
                "|       +-- d",
                "+-- i",
            ],
        ),
    ],
)
def test__print_tree(tree: dict, want: List[str]):
    """Test the _print_tree function with given input and expected output.
    
    Args:
        tree (dict): The input tree structure represented as a dictionary.
        want (List[str]): The expected output as a list of strings.
    
    Returns:
        None: This function doesn't return anything, it uses assertions for testing.
    """    v = _print_tree(tree)
    assert v == want


if __name__ == "__main__":
    pytest.main([__file__, "-s"])
