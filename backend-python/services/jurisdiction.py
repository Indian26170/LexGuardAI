import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

MODEL = "meta/llama-3.1-70b-instruct"

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
        "California Consumer Privacy Act (CCPA)",
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
    laws_context = []
    for region, laws in JURISDICTION_LAWS.items():
        if region.lower() in jurisdiction.lower():
            laws_context.extend(laws)

    laws_str = "\n".join([f"- {l}" for l in laws_context]) if laws_context else \
        "- General international contract law principles"

    return f"""
Review the document below and identify clauses that may be UNENFORCEABLE or ILLEGAL 
under the following applicable laws:

{laws_str}

For each conflict found, return a JSON array:
[
  {{
    "clause": "<problematic clause text>",
    "conflict": "<specific issue>",
    "applicable_law": "<specific Act, Section, or Regulation>"
  }}
]

Return ONLY the JSON array, no markdown, no explanation.
If no conflicts found, return: []

DOCUMENT:
{str(document_text)[:6000]}
"""


def check_jurisdiction_conflicts(document_text: str, jurisdiction: str) -> list:
    prompt = get_jurisdiction_prompt(document_text, jurisdiction)

    try:
        full_response = ""
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a cross-border legal specialist. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            top_p=0.7,
            max_tokens=2048,
            stream=True
        )

        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                full_response += chunk.choices[0].delta.content

        raw = full_response.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        return []