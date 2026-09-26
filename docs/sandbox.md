# CloudScope Sandbox Execution Layer

## Overview
When an approved remediation action is authorized by an engineer, CloudScope generates standalone, auditable Python execution code to interface with AWS APIs. To guarantee safety and prevent host contamination, **generated code is never executed directly in the host application process**.

---

## Sandbox Architecture

```mermaid
graph TD
    App[FastAPI / ApprovalService]
    Sandbox[ExecutionSandbox]
    TempDir[Temporary Scratch Directory<br/>sandbox_scratch/]
    Subprocess[Isolated Subprocess<br/>sys.executable]
    AWS_API[AWS Cloud APIs]

    App -->|Generate Execution Code| Sandbox
    Sandbox -->|Write Script| TempDir
    Sandbox -->|Sanitize Environment Variables| Subprocess
    Sandbox -->|Enforce 25s Timeout| Subprocess
    Subprocess -->|Invoke Scoped Boto3 Action| AWS_API
    Subprocess -->|Capture stdout / stderr| Sandbox
    Sandbox -->|Clean Up Script File| TempDir
    Sandbox -->|Return Structured Result| App
```

---

## Isolation Guarantees

1. **Subprocess Boundary**: Generated code executes in a separate process spawned via `subprocess.Popen([sys.executable, script_path])`.
2. **Environment Scrubbing**: Sensitive environment variables are removed prior to spawning:
   - `OPENAI_API_KEY`
   - `TRUEFOUNDRY_API_KEY`
   - `SECRET_KEY`
   - `JWT_SECRET`
   - `DATABASE_URL`
3. **Execution Timeout**: Enforced hard limit (default: 25 seconds). If a hanging API call or network partition occurs, the process is killed (`process.kill()`).
4. **Captured Output**: Captures standard output, standard error, exit code, and execution time in milliseconds.
5. **Post-Execution Cleanup**: Temporary script files are removed immediately upon execution completion or failure.
