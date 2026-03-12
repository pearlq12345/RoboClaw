import pytest
from bridge_core.sandbox import exec_in_env


class TestExecInEnv:
    async def test_simple_expression(self):
        result = await exec_in_env("print(1 + 2)")
        assert "3" in result["stdout"]
        assert result["success"] is True

    async def test_import_and_compute(self):
        result = await exec_in_env("import math; print(math.pi)")
        assert "3.14159" in result["stdout"]

    async def test_syntax_error(self):
        result = await exec_in_env("def (")
        assert result["success"] is False
        assert "SyntaxError" in result["stderr"]

    async def test_timeout(self):
        result = await exec_in_env("import time; time.sleep(10)", timeout=1)
        assert result["success"] is False
        assert "timeout" in result["error"].lower()

    async def test_multiline_code(self):
        code = """
items = [1, 2, 3]
total = sum(items)
print(f"total={total}")
"""
        result = await exec_in_env(code)
        assert "total=6" in result["stdout"]

    async def test_exception_captured(self):
        result = await exec_in_env("raise ValueError('test error')")
        assert result["success"] is False
        assert "ValueError" in result["stderr"]
