import json


def build_investigation_prompt(
    owner: str,
    repo: str,
    issue_number: int,
    issue: dict,
    repository_path: str
) -> str:

    return f"""
You are investigating GitHub issue #{issue_number}
from {owner}/{repo}.

GitHub issue:

Title:
{issue.get("title", "")}

Description:
{issue.get("body", "")}

Comments:
{json.dumps(issue.get("comments", []), indent=2)}

Repository path:
{repository_path}

Your job is to decide what repository code should
be inspected to understand the issue.

Return ONLY valid JSON in this format:

{{
    "searches": [
        {{
            "query": "keyword or function",
            "path": ""
        }}
    ],
    "files": [
        {{
            "path": "path/to/file",
            "line_start": 1,
            "line_end": 100
        }}
    ]
}}

Rules:

- Maximum 3 searches.
- Maximum 3 files.
- Prefer specific functions/classes/symbols.
- Do not search generic words.
- Do not inspect the whole repository.
- Only request code that is likely relevant.
- Prefer source files directly related to the issue.
- Use paths relative to the repository root.
- Search for concrete symbols, functions, classes, methods,
  error messages, or distinctive identifiers from the issue.
- Do not propose a fix yet.
- Do not modify any files.
- Do not return markdown.
- Return only JSON.
"""


def build_analysis_prompt(
    owner: str,
    repo: str,
    issue_number: int,
    issue: dict,
    evidence: list
) -> str:

    return f"""
You are a senior software engineer investigating
GitHub issue #{issue_number} in {owner}/{repo}.

ISSUE:

{json.dumps(issue, indent=2)}

REPOSITORY EVIDENCE:

{json.dumps(evidence, indent=2)}

Analyze the issue using ONLY the repository evidence
provided above.

Determine:

1. The actual root cause.
2. Why the current implementation produces the issue.
3. The smallest source-code change required.

Return ONLY valid JSON in exactly this format:

{{
    "root_cause": "clear explanation",
    "explanation": "why the bug happens",
    "patch": {{
        "file": "path/to/file",
        "old_text": "EXACT existing code",
        "new_text": "replacement code"
    }}
}}

IMPORTANT PATCH RULES:

- Only modify source code directly related to the issue.
- Do not modify tests.
- Do not modify package files.
- Do not modify configuration.
- old_text MUST be copied EXACTLY from the provided evidence.
- Preserve indentation exactly.
- old_text must identify exactly one location.
- new_text must contain the complete replacement.
- Make the smallest possible correction.
- Do not invent code that was not supported by the evidence.
- Do not return a diff.
- Do not return markdown.
- Do not include explanations outside the JSON.
"""


def build_repair_prompt(
    patch: dict,
    test_result: dict
) -> str:

    return f"""
You are repairing a source-code patch for a GitHub issue.

The previous patch was:

{json.dumps(patch, indent=2)}

The repository test result was:

{json.dumps(test_result, indent=2)}

Determine whether the patch needs correction.

If correction is required, return ONLY valid JSON:

{{
    "patch": {{
        "file": "path/to/file",
        "old_text": "EXACT current text from the file",
        "new_text": "replacement text"
    }},
    "explanation": "why this correction is required"
}}

Rules:

- Only modify code related to the original issue.
- Do not modify tests.
- Do not modify package files.
- old_text MUST exactly match the current repository file.
- Preserve indentation exactly.
- Make the smallest possible correction.
- Do not return markdown.
- Do not return a diff.
- Return only JSON.
"""