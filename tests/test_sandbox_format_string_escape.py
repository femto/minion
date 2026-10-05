"""Regression tests for GHSA-m5v3-6ccr-cfgx: str.format field access bypassing the dunder check."""
import pytest

from minion.main.async_python_executor import AsyncPythonExecutor
from minion.main.local_python_executor import InterpreterError, LocalPythonExecutor


def secret_tool():
    return "ok"


SECRET = "super-secret-value"
secret_tool.api_key = SECRET

MALICIOUS_SNIPPETS = [
    'result = "{0.__globals__}".format(secret_tool)',
    'result = "{t.__globals__}".format(t=secret_tool)',
    'result = "{x.__dict__}".format_map({"x": secret_tool})',
    'f = "{0.__globals__}".format\nresult = f(secret_tool)',
    'result = str.format("{0.__globals__}", secret_tool)',
    'result = getattr("{0.__dict__}", "format")(secret_tool)',
    'result = "{0:{1.__dict__}}".format(1, secret_tool)',
    'result = "{0[a].__globals__}".format({"a": secret_tool})',
]

BENIGN_SNIPPETS = [
    ('result = "{0} {name}".format(1, name="x")', "1 x"),
    ('result = "{0[k]}-{0[k]:>3}".format({"k": "v"})', "v-  v"),
    ('result = "{0.real}".format(3)', "3"),
    ('result = str.format("{}!", "hi")', "hi!"),
    ('result = "{x}".format_map({"x": 5})', "5"),
]


def _make_local():
    executor = LocalPythonExecutor(additional_authorized_imports=[])
    executor.send_variables({"secret_tool": secret_tool})
    executor.send_tools({})
    return executor


def _make_async():
    executor = AsyncPythonExecutor(additional_authorized_imports=[])
    executor.send_variables({"secret_tool": secret_tool})
    executor.send_tools({})
    return executor


@pytest.mark.parametrize("code", MALICIOUS_SNIPPETS)
def test_local_executor_blocks_format_dunder_access(code):
    executor = _make_local()
    with pytest.raises(InterpreterError, match="dunder"):
        executor(code)


@pytest.mark.parametrize("code,expected", BENIGN_SNIPPETS)
def test_local_executor_allows_benign_format(code, expected):
    executor = _make_local()
    executor(code)
    assert executor.state["result"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("code", MALICIOUS_SNIPPETS)
async def test_async_executor_blocks_format_dunder_access(code):
    executor = _make_async()
    with pytest.raises(InterpreterError, match="dunder"):
        await executor(code)


@pytest.mark.asyncio
@pytest.mark.parametrize("code,expected", BENIGN_SNIPPETS)
async def test_async_executor_allows_benign_format(code, expected):
    executor = _make_async()
    await executor(code)
    assert executor.state["result"] == expected


@pytest.mark.parametrize(
    "code",
    [
        'import string\nresult = string.Formatter().format("{0.__globals__}", secret_tool)',
        'import string\nresult = string.Formatter().vformat("{0.__globals__}", (secret_tool,), {})',
        'import string\nresult = string.Formatter.format(string.Formatter(), "{0.__globals__}", secret_tool)',
    ],
)
def test_local_executor_blocks_string_formatter_dunder_access(code):
    executor = LocalPythonExecutor(additional_authorized_imports=["string"])
    executor.send_variables({"secret_tool": secret_tool})
    executor.send_tools({})
    with pytest.raises(InterpreterError, match="dunder"):
        executor(code)
