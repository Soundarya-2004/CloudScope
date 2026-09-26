# CloudScope Agent Workflow

## The 11-Stage Structured Lifecycle

CloudScope executes a deterministic, auditable multi-stage lifecycle:

```
DISCOVER
   ↓
OBSERVE
   ↓
ANALYZE
   ↓
ESTIMATE COST
   ↓
IDENTIFY CANDIDATES
   ↓
GENERATE CLEANUP PLAN
   ↓
RISK ANALYSIS
   ↓
HUMAN APPROVAL CHECKPOINT (PAUSE)
   ↓
SANDBOXED EXECUTION
   ↓
VERIFY RESULT
   ↓
AUDIT LOG
```

---

### Stage 1: DISCOVER
- Connects to the target AWS account using SDK credential resolution.
- Calls `sts.get_caller_identity()` to verify AWS Account ID, principal ARN, and region.
- Enumerates compute instances (`ec2.describe_instances()`), storage volumes (`ec2.describe_volumes()`), and load balancers (`elbv2.describe_load_balancers()`).

### Stage 2: OBSERVE
- Inspects operational runtime indicators.
- Queries AWS CloudWatch for average and peak `CPUUtilization` metrics over an observation window (default 7 days).
- Queries ELB target groups, listener configurations, and target health descriptions (`describe_target_health()`).
- Checks EBS volume attachment status, volume age, and snapshot lineage.

### Stage 3: ANALYZE
- Evaluates resources against analytical waste heuristics:
  - **Running EC2** with average CPU < 5% and peak CPU < 15% → `potentially_idle`.
  - **Stopped EC2** incurring passive storage costs → `candidate_for_cleanup`.
  - **Unattached EBS** volume in `available` state → `likely_orphaned`.
  - **Load Balancer** with zero target groups or zero registered targets → `unused_load_balancer`.
- **Production Safeguards**: Tags containing `prod`, `production`, `live`, or `critical` downgrade recommendations to `review_required` to prevent accidental deletion of critical infrastructure.

### Stage 4: ESTIMATE COST
- Evaluates monthly cost using real AWS billing data (Cost Explorer) or published regional on-demand benchmarks.
- Attributes cost source, calculation formula, and currency.
- Calculates monthly and annual potential savings.

### Stage 5: IDENTIFY CANDIDATES
- Flags waste candidates and persists `ResourceSnapshot` records in the database.
- Calculates aggregated savings across all candidate resources.

### Stage 6: GENERATE CLEANUP PLAN
- Compiles candidate teardown actions into a structured `CleanupPlan`.
- Computes a deterministic SHA-256 cryptographic hash of all sorted candidate IDs and actions.
- Seals the plan version.

### Stage 7: RISK ANALYSIS
- Analyzes dependencies: attached EBS root volumes, network interfaces, parent snapshots.
- Assigns risk classification (`HIGH`, `MEDIUM`, `LOW`).

### Stage 8: HUMAN APPROVAL CHECKPOINT (PAUSE)
- **CRITICAL GATE**: The agent immediately pauses autonomous execution.
- Generates individual `ApprovalRequest` records with 2-hour expiration timestamps.
- Dispatches multi-channel alerts:
  - Broadcasts live WebSocket event to connected browsers.
  - Fires browser Notification API alert: `"CloudJanitor needs your approval"`.
  - Dispatches Amazon SES email alert if configured.
  - Updates in-app Notification Center.
- **Remains paused until an explicit user decision (`APPROVED` or `REJECTED`) is recorded.**

### Stage 9: SANDBOXED EXECUTION
- Only proceeds if the specific action is `APPROVED`, the plan hash is intact, and the agent is in `ACTION` mode.
- Performs pre-deletion safety verification: re-queries live AWS API to ensure the resource still exists and matches expected state.
- Generates targeted cleanup Python code.
- Executes code inside an isolated subprocess with strict environment scrubbing and a 25-second timeout.

### Stage 10: VERIFY RESULT
- Re-queries AWS live infrastructure after execution.
- Verifies instance transitioned to `terminating` or `terminated`.
- Verifies volume or load balancer returned `NotFound`.

### Stage 11: AUDIT LOG
- Records structured `AuditEvent` in database with timestamp, user, AWS account, action, status, and execution duration.
