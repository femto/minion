#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from pathlib import Path

import pytest

from metagpt.utils.repo_to_markdown import repo_to_markdown


@pytest.mark.parametrize(
    ["repo_path", "output"],
    [(Path(__file__).parent.parent, Path(__file__).parent.parent.parent / f"workspace/unittest/{uuid.uuid4().hex}.md")],
)
@pytest.mark.asyncio
async def test_repo_to_markdown(repo_path: Path, output: Path):
    """Asynchronously tests the repo_to_markdown function.
    
    Args:
        repo_path (Path): The path to the repository to be converted to markdown.
        output (Path): The path where the output markdown file will be saved.
    
    Returns:
        None: This function doesn't return anything, but it asserts the expected behavior.
    """
    markdown = await repo_to_markdown(repo_path=repo_path, output=output)
    assert output.exists()
    assert markdown

    output.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-s"])
