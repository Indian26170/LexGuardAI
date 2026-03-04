import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

JURISDICTION_LAWS = {
    "India": [
        "Indian Contract Act 1872",
        "Specific Relief Act 1963",
        "Arbitration and Conciliation Act 1996",
        "Information Technology Act 2000",
        "Transfer of Property Act 1882",
    ],
    "USA": [
        "Uniform Commercial Code (UCC)",
        "Federal Arbitration Act",
        "Americans with Disabilities Act",
        "Fair Labor Standards Act",
        "GDPR (California Consumer Privacy Act - CCPA)",
    ],
    "UK": [
        "Contracts (Rights of Third Parties) Act 1999",
        "Unfair Contract Terms Act 1977",
        "Sale of Goods Act 1979",
        "Employment Rights Act 1996",
    ],
    "EU": [
        "GDPR (EU) 2016/679",
        "EU Consumer Rights Directive",
        "Rome I Regulation (contract law)",
    ]
}


def get_jurisdiction_prompt(document_text: str, jurisdiction: str) -> str:
    """
    Build a targeted cross-border conflict check prompt.
    Automatically includes relevant law references.
    """
    # Determine which law sets to include
    laws_context = []
    for region, laws in JURISDICTION_LAWS.items():
        if region.lower() in jurisdiction.lower():
            laws_context.extend(laws)

    laws_str = "\n".join([f"- {l}" for l in laws_context]) if laws_context else \
        "- General international contract law principles"

    return f"""
You are a cross-border legal specialist. Review the document below and identify 
clauses that may be UNENFORCEABLE or ILLEGAL under the following applicable laws:

{laws_str}

For each conflict found, return a JSON array:
[
  {{
    "clause": "<problematic clause text>",
    "conflict": "<specific issue — what makes it unenforceable or risky>",
    "applicable_law": "<specific Act, Section, or Regulation>"
  }}
]

Return ONLY the JSON array, no markdown, no explanation outside JSON.
If no conflicts found, return an empty array: []

DOCUMENT:
{str(document_text)[:6000]}
"""


def check_jurisdiction_conflicts(document_text: str, jurisdiction: str) -> list:
    """
    Run a targeted jurisdiction conflict check.
    Returns list of JurisdictionFlag dicts.
    """
    prompt = get_jurisdiction_prompt(document_text, jurisdiction)

    try:
        response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=2048,
    )
)
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        return []  # Non-fatal — main analysis still returns