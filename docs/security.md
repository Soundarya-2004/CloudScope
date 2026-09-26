# CloudScope Security & Governance Architecture

## Security Principles

CloudScope is designed for real enterprise cloud accounts where safety, data protection, and principle of least privilege are non-negotiable.

---

## 1. Zero Secret Exposure in Sandboxed Code
Generated Python execution scripts are run inside an isolated subprocess (`sandbox.py`).
- **Denylist Filtering**: The sandbox explicitly strips sensitive environment variables:
  - `OPENAI_API_KEY`
  - `TRUEFOUNDRY_API_KEY`
  - `SECRET_KEY`
  - `JWT_SECRET`
  - `DATABASE_URL`
- Generated execution scripts never receive host environment credentials.
- Execution directory is restricted to a dedicated temporary scratch folder (`sandbox_scratch/`).

## 2. At-Rest Encryption of Stored AWS Credentials
- When credentials are provided via the UI/API, the `aws_secret_key` is encrypted at rest using **Fernet Symmetric Encryption** (AES-128-CBC with HMAC-SHA256 authentication).
- Stored keys are decrypted in memory solely for the duration of the active request.
- The `aws_access_key` is masked in all client responses (e.g. `****ABCD`).

## 3. Server-Side Approval Verification
- The backend **never trusts client-side state**. Even if a user alters client state or sends an execution request, the server independently validates:
  1. The approval record exists.
  2. The status is explicitly `APPROVED`.
  3. The request has not expired.
  4. The cryptographic plan hash matches the active plan.
  5. The authenticated user is authorized.
  6. The agent is in `ACTION` mode.

## 4. Cryptographic Plan Hashing
- The agent calculates a SHA-256 hash over the sorted resource IDs, resource types, actions, account ID, and region.
- If the cleanup plan changes after approval is granted (e.g., resources are added or removed), the new plan hash invalidates previous approvals.

## 5. Live Pre-Deletion Safety Check
- Infrastructure changes rapidly. A resource approved at 2:00 PM could have been repurposed by 2:05 PM.
- Before executing any destructive command, CloudScope re-queries the AWS API to verify:
  - The resource still exists.
  - The resource is still in the expected state (e.g., EC2 is not already terminating; EBS volume is still `available`).
- If any discrepancy is detected, execution immediately aborts.

## 6. Immutable Audit Trail
- Every action produces an event in `audit_events` with UTC timestamp, user, account, resource, status, reason, duration, and error codes.
- Audit records cannot be modified or deleted through the API.
