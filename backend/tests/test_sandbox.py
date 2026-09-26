import pytest
from backend.app.sandbox import sandbox, SENSITIVE_ENV_KEYS

def test_sandbox_executes_valid_code_safely():
    code = "import sys; print('SANDBOX_TEST_OK'); sys.exit(0)"
    res = sandbox.execute_python_code(code, "test_action", "test-res-1")
    assert res["success"] is True
    assert res["exit_code"] == 0
    assert "SANDBOX_TEST_OK" in res["stdout"]
    assert res["sandboxed"] is True

def test_sandbox_scrubs_sensitive_env():
    import os
    os.environ["OPENAI_API_KEY"] = "sk-secret-leak-test"
    os.environ["SECRET_KEY"] = "super-secret-key"

    code = """
import os, sys
leaks = []
for k in ['OPENAI_API_KEY', 'SECRET_KEY']:
    if k in os.environ:
        leaks.append(k)
if leaks:
    print(f"LEAKED: {','.join(leaks)}")
    sys.exit(1)
print("NO_LEAKS")
sys.exit(0)
"""
    res = sandbox.execute_python_code(code, "test_env_scrub", "test-res-2")
    assert res["success"] is True
    assert "NO_LEAKS" in res["stdout"]

def test_sandbox_enforces_execution_timeout():
    # Use a small custom sandbox instance with 1 second timeout
    from backend.app.sandbox import ExecutionSandbox
    quick_sandbox = ExecutionSandbox(timeout_seconds=1)
    infinite_loop_code = "import time; time.sleep(5)"
    res = quick_sandbox.execute_python_code(infinite_loop_code, "test_timeout", "test-res-3")
    assert res["success"] is False
    assert "timed out" in res["error"].lower() or "timeout" in res["error"].lower()
