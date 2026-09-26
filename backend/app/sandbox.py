import os
import sys
import tempfile
import subprocess
import time
from typing import Dict, Any, Optional

# Denylist of sensitive environment variables that MUST NEVER be passed into the sandbox
SENSITIVE_ENV_KEYS = [
    "OPENAI_API_KEY",
    "TRUEFOUNDRY_API_KEY",
    "SECRET_KEY",
    "JWT_SECRET",
    "DATABASE_URL",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "AWS_SECRET_ACCESS_KEY", # Raw host secrets redacted unless explicitly scoped
    "AWS_SESSION_TOKEN"
]

class ExecutionSandbox:
    """
    Safely executes generated AWS remediation code inside an isolated subprocess sandbox.
    Enforces strict environment scrubbing, execution timeouts, stdout/stderr capture,
    and returns structured execution results.
    """
    def __init__(self, timeout_seconds: int = 25):
        self.timeout_seconds = timeout_seconds
        self.scratch_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sandbox_scratch"))
        os.makedirs(self.scratch_dir, exist_ok=True)

    def _build_sanitized_env(self, scoped_aws_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Creates a minimal sanitized environment containing only essential system variables"""
        clean_env = {}
        
        # Pass essential system paths for python execution
        for key in ["PATH", "SystemRoot", "SYSTEMROOT", "windir", "TEMP", "TMP"]:
            if key in os.environ:
                clean_env[key] = os.environ[key]

        clean_env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        clean_env["SANDBOX_ACTIVE"] = "true"

        # Explicitly scrub all sensitive keys
        for key in SENSITIVE_ENV_KEYS:
            clean_env.pop(key, None)

        # Inject only explicitly scoped variables for this single operation
        if scoped_aws_env:
            for k, v in scoped_aws_env.items():
                clean_env[k] = v

        return clean_env

    def execute_python_code(
        self,
        code_content: str,
        action_name: str,
        resource_id: str,
        scoped_aws_env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Writes the generated Python execution code to an isolated temp file and runs it with strict timeout.
        """
        start_time = time.time()
        temp_file_path = None

        try:
            # Create a sandboxed script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', dir=self.scratch_dir, delete=False, encoding='utf-8') as f:
                temp_file_path = f.name
                f.write(code_content)

            sanitized_env = self._build_sanitized_env(scoped_aws_env)

            # Execute with sys.executable in isolated subprocess
            process = subprocess.Popen(
                [sys.executable, temp_file_path],
                cwd=self.scratch_dir,
                env=sanitized_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(timeout=self.timeout_seconds)
            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": process.returncode == 0,
                "exit_code": process.returncode,
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "duration_ms": duration_ms,
                "action": action_name,
                "resource_id": resource_id,
                "sandboxed": True,
                "error": None if process.returncode == 0 else f"Execution failed with code {process.returncode}: {stderr.strip()}"
            }

        except subprocess.TimeoutExpired:
            process.kill()
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Sandbox execution timeout exceeded ({self.timeout_seconds} seconds)",
                "duration_ms": duration_ms,
                "action": action_name,
                "resource_id": resource_id,
                "sandboxed": True,
                "error": "Execution timed out and was forcefully terminated"
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": duration_ms,
                "action": action_name,
                "resource_id": resource_id,
                "sandboxed": True,
                "error": str(e)
            }
        finally:
            # Clean up temporary script
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass

# Singleton instance
sandbox = ExecutionSandbox()
