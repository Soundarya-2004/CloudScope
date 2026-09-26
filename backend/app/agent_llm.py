import os
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional

# Load .env from current dir, backend/, or parent
for p in [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env", Path(__file__).resolve().parent.parent.parent / ".env"]:
    if p.exists():
        load_dotenv(dotenv_path=p)


class TrueFoundryGatewayClient:
    """
    Connects to the TrueFoundry AI Gateway (vm-polaris/openai) using the configured model endpoint.
    Provides structured tool-calling and natural language reasoning over discovered AWS infrastructure.
    """
    def __init__(self):
        self.api_key = os.environ.get("TRUEFOUNDRY_API_KEY", "")
        self.base_url = os.environ.get("TRUEFOUNDRY_BASE_URL", "https://gateway.truefoundry.ai").rstrip("/")
        self.model_id = os.environ.get("TRUEFORGE_MODEL", "vm-polaris/openai")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def generate_reasoning_explanation(
        self,
        resource: Dict[str, Any],
        user_question: Optional[str] = None
    ) -> str:
        """
        Generates deep, context-aware reasoning for why a specific resource is flagged as waste.
        """
        if not self.is_configured():
            # Return high-fidelity local analytical explanation if API key is not yet configured in .env
            evidence_str = "\n• " + "\n• ".join(resource.get("evidence", ["Low utilization detected"]))
            dep_str = ", ".join(resource.get("dependencies", ["None"])) if resource.get("dependencies") else "None"
            return (
                f"**CloudJanitor Analysis for `{resource.get('resource_id')}` ({resource.get('resource_type').upper()}):**\n\n"
                f"**Observed Evidence:**{evidence_str}\n\n"
                f"**Dependencies:** {dep_str}\n\n"
                f"**Financial Impact:** Estimated monthly cost of ${resource.get('monthly_cost', 0):.2f}/mo. "
                f"Cleaning this resource will save ${resource.get('monthly_cost', 0) * 12:.2f}/year.\n\n"
                f"**Recommendation:** {resource.get('recommended_action', 'review').capitalize()} "
                f"(Confidence: {int(resource.get('confidence', 0) * 100)}%). Action is paused awaiting human approval."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = (
            "You are CloudScope's expert AWS Cost Janitor. Explain clearly and concisely to an engineer "
            "why the following AWS resource was identified as potentially wasteful. Highlight the exact evidence, "
            "financial impact, dependencies, and risks. Note that destructive actions are paused awaiting explicit approval."
        )

        user_content = f"Resource details:\n{json.dumps(resource, indent=2)}\n\nUser question: {user_question or 'Why is this resource flagged for cleanup?'}"

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.2
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(f"{self.base_url}/v1/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"TrueFoundry Gateway response ({resp.status_code}): {resp.text}"
        except Exception as e:
            return f"Reasoning generation note: {str(e)}"

truefoundry_client = TrueFoundryGatewayClient()
