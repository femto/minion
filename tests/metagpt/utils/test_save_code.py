# -*- coding: utf-8 -*-
# @Date    : 12/12/2023 4:17 PM
# @Author  : stellahong (stellahong@fuzhi.ai)
# @Desc    :

import nbformat
import pytest

from metagpt.actions.di.execute_nb_code import ExecuteNbCode
from metagpt.utils.common import read_json_file
from metagpt.utils.save_code import DATA_PATH, save_code_file


def test_save_code_file_python():
    """Test the save_code_file function for Python code.
    
    Args:
        None
    
    Returns:
        None: This function doesn't return anything, but performs assertions to check if the file is created and contains the correct content.
    """
    save_code_file("example", "print('Hello, World!')")
    file_path = DATA_PATH / "output" / "example" / "code.py"
    assert file_path.exists(), f"File does not exist: {file_path}"
    content = file_path.read_text()
    assert "print('Hello, World!')" in content, "File content does not match"


def test_save_code_file_json():
    """Tests the save_code_file function with JSON format output.
    
    This function verifies that the save_code_file function correctly saves code content
    in JSON format and that the saved file contains the expected data.
    
    Args:
        None
    
    Returns:
        None: This test function doesn't return anything, but raises an AssertionError
              if the test conditions are not met.
    """
    save_code_file("example_json", "print('Hello, JSON!')", file_format="json")
    file_path = DATA_PATH / "output" / "example_json" / "code.json"
    data = read_json_file(file_path)
    assert "code" in data, "JSON key 'code' is missing"
    assert data["code"] == "print('Hello, JSON!')", "JSON content does not match"


@pytest.mark.asyncio
async def test_save_code_file_notebook():
    """Test saving code as a Jupyter Notebook file.
    
    Args:
        None
    
    Returns:
        None: This function doesn't return anything, but performs assertions to verify the saved notebook.
    """    code = "print('Hello, World!')"
    executor = ExecuteNbCode()
    await executor.run(code)
    # Save as a Notebook file
    save_code_file("example_nb", executor.nb, file_format="ipynb")
    file_path = DATA_PATH / "output" / "example_nb" / "code.ipynb"
    assert file_path.exists(), f"Notebook file does not exist: {file_path}"

    # Additional checks specific to notebook format
    notebook = nbformat.read(file_path, as_version=4)
    assert len(notebook.cells) > 0, "Notebook should have at least one cell"
    first_cell_source = notebook.cells[0].source
    assert "print" in first_cell_source, "Notebook cell content does not match"
