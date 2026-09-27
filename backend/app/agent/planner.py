import json

from google import genai
from google.genai import types

from app.agent.prompts import build_investigation_prompt


class InvestigationPlanner:

    def __init__(self, client: genai.Client, model: str):
        self.client = client
        self.model = model

    def create_plan(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        issue: dict,
        repository_path: str
    ) -> dict:

        prompt = build_investigation_prompt(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            issue=issue,
            repository_path=repository_path
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )

        try:

            return json.loads(
                response.text
            )

        except Exception:

            text = response.text or ""

            start = text.find("{")
            end = text.rfind("}")

            if start != -1 and end != -1:

                try:
                    return json.loads(
                        text[start:end + 1]
                    )

                except Exception:
                    pass

            return {
                "error": (
                    "Could not determine "
                    "investigation targets."
                ),
                "raw_response": text
            }