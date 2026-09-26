from typing import Dict, Any, List
from ..cost_engine import CompositeCostEstimator

DEPRECATED_RUNTIMES = [
    "nodejs10.x", "nodejs12.x", "nodejs14.x", "nodejs16.x",
    "python2.7", "python3.6", "python3.7", "python3.8",
    "dotnetcore2.1", "dotnetcore3.1", "ruby2.5", "ruby2.7", "java8"
]

class LambdaAnalyzer:
    """
    Analyzes AWS Lambda serverless functions.
    Identifies functions running on deprecated, unsupported runtimes or abandoned functions.
    """
    def __init__(self, session, cost_estimator: CompositeCostEstimator):
        self.session = session
        self.cost_estimator = cost_estimator

    def analyze_functions(self) -> List[Dict[str, Any]]:
        candidates = []
        try:
            lmb = self.session.client('lambda')
            resp = lmb.list_functions()
        except Exception:
            return []

        for fn in resp.get('Functions', []):
            name = fn.get('FunctionName')
            runtime = fn.get('Runtime', 'unknown')
            code_size = fn.get('CodeSize', 0)
            last_mod = fn.get('LastModified')
            arn = fn.get('FunctionArn')

            is_deprecated = runtime.lower() in DEPRECATED_RUNTIMES
            evidence = [
                f"Runtime: {runtime}",
                f"Package Size: {round(code_size / 1024 / 1024, 2)} MB",
                f"Last modified: {last_mod}"
            ]
            if is_deprecated:
                evidence.append(f"SECURITY RISK: Runtime '{runtime}' is deprecated and no longer receives AWS security updates")

            candidates.append({
                "resource_id": name,
                "resource_type": "lambda",
                "region": self.session.region_name or "us-east-1",
                "name": name,
                "state": "active",
                "instance_type_or_size": runtime,
                "monthly_cost": 0.20, # Baseline execution tier
                "cost_source": "aws_pricing_derived",
                "cost_method": "AWS Lambda invocation rate: $0.20/1M requests",
                "is_waste": is_deprecated,
                "confidence": 0.85 if is_deprecated else 0.40,
                "waste_finding": "deprecated_runtime" if is_deprecated else None,
                "evidence": evidence,
                "dependencies": [f"ARN: {arn}"],
                "recommended_action": "review" if is_deprecated else "retain",
                "requires_approval": False,
                "tags": {},
                "created_at": last_mod
            })

        return candidates
