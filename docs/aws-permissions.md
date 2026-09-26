# AWS IAM Permissions Specification

CloudScope enforces a **Two-Phase Permission Model**:
1. **READ MODE**: Non-destructive discovery and metric analysis.
2. **ACTION MODE**: Destructive remediation actions executable **only after human approval**.

---

## 1. Discovery & Cost Analysis (Read-Only)

Attach this policy to the IAM User or IAM Role running the agent during discovery:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudScopeIdentityValidation",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudScopeComputeDiscovery",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeInstanceAttribute",
        "ec2:DescribeSnapshots"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudScopeLoadBalancerDiscovery",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:DescribeListeners"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudScopeMetricsObservation",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudScopeCostExplorer",
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetDimensionValues"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 2. Destructive Cleanup (Action Mode — Approval Required)

These permissions should only be granted if the team intends to demonstrate live cleanup. They are **never invoked without explicit human approval recorded on the server**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudScopeEC2Termination",
      "Effect": "Allow",
      "Action": [
        "ec2:TerminateInstances"
      ],
      "Resource": "arn:aws:ec2:*:*:instance/*"
    },
    {
      "Sid": "CloudScopeEBSDeletion",
      "Effect": "Allow",
      "Action": [
        "ec2:DeleteVolume"
      ],
      "Resource": "arn:aws:ec2:*:*:volume/*"
    },
    {
      "Sid": "CloudScopeELBDeletion",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DeleteLoadBalancer"
      ],
      "Resource": "arn:aws:elasticloadbalancing:*:*:loadbalancer/*"
    }
  ]
}
```

---

## 3. Email Notification (Amazon SES — Optional)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudScopeSESNotification",
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Graceful Permission Degradation

If any permission is missing:
- **Cost Explorer unavailable**: The agent clearly displays *"Billing data unavailable — missing AWS permission"* and transparently uses verified regional on-demand benchmark rates.
- **CloudWatch unavailable**: The agent reports *"CloudWatch metric query unavailable"* in the evidence list and proceeds based on instance state and tags.
- **Destructive permission denied**: If approval is granted but the AWS credentials lack `ec2:TerminateInstances`, CloudScope catches the `UnauthorizedOperation` error, reports the exact missing action, and updates the audit log to `EXECUTION_FAILED`.
