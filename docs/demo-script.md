# CloudScope 3-to-5 Minute Judge Demo Script

**Primary Theme**: Cloud Cost Janitor  
**Core Thesis**: *"CloudScope doesn't just show you where your money went. It investigates real live infrastructure, quantifies waste, stops before anything dangerous, requests human permission, and safely executes approved cleanup inside a sandbox."*

---

## Step-by-Step Presentation Flow

### 1. Introduction (30 seconds)
- **Speaker**: *"Judges, this is CloudScope, built for the Agents That Act hackathon. We built an autonomous Cloud Cost Janitor that connects to real AWS accounts, discovers wasteful infrastructure, calculates savings, and enforces a non-negotiable Human Approval Gate before any destructive remediation."*
- **Screen**: Open Dashboard at `http://localhost:5173`. Show top cards (AWS Account ID, Region, Monthly Spend, Mode: `READ_ONLY`).

### 2. Live Agent Deployment (60 seconds)
- **Speaker**: *"Let's deploy the agent right now against our AWS environment."*
- **Action**: Navigate to `/agent` (Agent Control Center). Click **Deploy Janitor Agent** with prompt:  
  `"Find the AWS resources that are costing me money but appear unused."`
- **Showcase**: Point out the live WebSocket activity log streaming in real time:
  - `● Connecting to AWS...`
  - `✓ Connected to AWS Account XXX in us-east-1`
  - `✓ Scanning EC2 compute instances & CloudWatch CPU metrics...`
  - `✓ Scanning EBS storage for unattached/orphaned volumes...`
  - `✓ Scanning Load Balancers for inactive target routing...`
  - `✓ Evaluating cost and savings benchmarks...`
  - `✓ Generated cleanup plan (Plan Hash: a9f8e...)`
  - `⏸ WAITING FOR HUMAN APPROVAL`

### 3. The Human Approval Gate & Reasoning (60 seconds)
- **Speaker**: *"Notice what just happened. The agent discovered wasteful resources, but it DID NOT blindly delete them. It generated a cryptographically sealed cleanup plan and immediately paused at the approval checkpoint."*
- **Action**: 
  - Point out the prominent **HUMAN APPROVAL REQUIRED** banner with identified monthly savings.
  - Inspect a waste candidate card (e.g., Orphaned EBS volume or idle EC2).
  - Click **AI Reasoning** to show contextual justification powered by TrueFoundry AI Gateway (`vm-polaris/openai`).
  - Demonstrate browser notification popup: *"CloudJanitor needs your approval"*.

### 4. Selective Decision & Sandboxed Execution (60 seconds)
- **Action**: Navigate to `/approvals`.
  - Approve Resource #1 (e.g. unattached EBS volume).
  - Reject Resource #2.
  - Explain: *"Notice individual resource sovereignty. Approving Resource 1 does not authorize Resource 2."*
  - Enable `ACTION` mode in Settings (with safety confirmation checkbox).
  - Click **Execute in Sandbox** for the approved resource.
- **Showcase**:
  - Live pre-deletion safety verification check against AWS.
  - Sandboxed execution in an isolated subprocess with stripped environment variables.
  - Post-deletion verification confirming the resource state transitioned in AWS.

### 5. Audit Trail & Verification (30 seconds)
- **Action**: Navigate to `/audit`.
  - Show the complete, immutable event timeline:
    `AGENT_STARTED` → `AWS_CONNECTED` → `DISCOVERY_STARTED` → `CANDIDATE_IDENTIFIED` → `PLAN_GENERATED` → `APPROVAL_REQUESTED` → `APPROVAL_APPROVED` → `EXECUTION_STARTED` → `EXECUTION_COMPLETED` → `VERIFICATION_COMPLETED`.
- **Conclusion**: *"ACT → STOP → ASK → ACT. A real agent that acts with real enterprise governance."*
