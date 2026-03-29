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

MASTER_SYSTEM_PROMPT = """
You are LexGuard AI, an expert legal auditor with deep expertise in contract law, 
international trade law, employment law, and real estate law.

You will be given the text of a legal document. Your task is to perform a comprehensive 
legal audit and return a STRICT JSON response — nothing else, no markdown, no explanation 
outside the JSON.

Return this exact JSON structure:

{
  "legalScore": <integer 0-100>,
  "document_type_detected": "<string: e.g. Employment Contract, Rental Agreement, NDA>",
  "clauses": [
    {
      "text": "<exact or paraphrased clause text>",
      "classification": "<RED | YELLOW | GREEN>",
      "reason": "<plain English explanation of why this is risky or safe>",
      "counterDraft": "<rewritten safer version of this clause, or null if GREEN>"
    }
  ],
  "summary": [
    "<bullet 1>",
    "<bullet 2>",
    "<bullet 3>",
    "<bullet 4>",
    "<bullet 5>"
  ],
  "jurisdiction_flags": [
    {
      "clause": "<clause text>",
      "conflict": "<what law it conflicts with>",
      "applicable_law": "<e.g. Indian Contract Act Section 23, US UCC 2-207>"
    }
  ]
}

SCORING RULES — penalize heavily for:
- Unlimited liability clauses: -20 points
- Unilateral termination without cause: -15 points
- IP grab clauses (employer owns all inventions): -15 points
- Forced arbitration removing court access: -10 points
- Auto-renewal with no opt-out: -10 points
- Vague payment terms: -8 points
- One-sided indemnification: -10 points
- Missing dispute resolution: -8 points

Start score at 100 and subtract. Floor is 0.

CLASSIFICATION RULES:
- RED: Clause poses serious legal risk, heavily one-sided, or potentially unenforceable
- YELLOW: Clause has moderate risk or ambiguity — should be reviewed
- GREEN: Clause is fair, balanced, and standard

Identify ALL significant clauses, minimum 5, maximum 20.
Write summary in plain English a non-lawyer can understand.
Be specific, concrete, and actionable.
Return ONLY the JSON object. No markdown, no explanation, no extra text.
"""


def build_analysis_prompt(document_text: str, jurisdiction: Optional[str] = None) -> str:
    prompt = MASTER_SYSTEM_PROMPT

    if jurisdiction and jurisdiction.strip():
        prompt += f"""

JURISDICTION CONTEXT:
This document involves parties from: {jurisdiction}
Flag any clauses that conflict with the laws of these jurisdictions.
Reference specific Acts and sections where relevant (e.g., Indian Contract Act 1872, 
US Uniform Commercial Code, UK Contracts Act 1999).
"""

    prompt += f"""

DOCUMENT TEXT TO AUDIT:
{document_text}
"""
    return prompt


def build_translation_prompt(summary_bullets: list, target_language: str) -> str:
    bullets_text = "\n".join([f"{i+1}. {b}" for i, b in enumerate(summary_bullets)])
    return f"""
Translate the following 5 legal summary bullets into {target_language}.
Preserve legal accuracy — do NOT simplify terms that change meaning.
Return ONLY a JSON array of 5 translated strings, no markdown, no extra text.

Original bullets:
{bullets_text}
"""


def call_nvidia(system_prompt: str, user_content: str, max_tokens: int = 4096) -> str:
    """
    Call NVIDIA NIM API with streaming and collect full response.
    """
    full_response = ""
    
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.2,
        top_p=0.7,
        max_tokens=max_tokens,
        stream=True
    )
    
    for chunk in completion:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            full_response += chunk.choices[0].delta.content
    
    return full_response.strip()


def analyze_document(
    document_text: str,
    jurisdiction: Optional[str] = None,
    target_language: Optional[str] = None
) -> dict:
    """
    Run the full NVIDIA NIM analysis on document text.
    Returns parsed JSON result dict.
    """
    # Step 1: Main legal analysis
    analysis_prompt = build_analysis_prompt(document_text, jurisdiction)
    
    raw_text = call_nvidia(
        system_prompt="You are LexGuard AI, a legal auditor. Always respond with valid JSON only.",
        user_content=analysis_prompt,
        max_tokens=4096
    )

    # Strip markdown code fences if model wraps in ```json
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    result = json.loads(raw_text)

    # Step 2: Multilingual translation (optional)
    if target_language and target_language.strip().lower() not in ("english", "en"):
        try:
            translation_prompt = build_translation_prompt(
                result.get("summary", []), target_language
            )
            trans_raw = call_nvidia(
                system_prompt="You are a legal translator. Always respond with a valid JSON array only.",
                user_content=translation_prompt,
                max_tokens=1024
            )
            trans_raw = re.sub(r"^```(?:json)?\s*", "", trans_raw)
            trans_raw = re.sub(r"\s*```$", "", trans_raw)
            result["summary_translated"] = json.loads(trans_raw)
        except Exception:
            result["summary_translated"] = None

    return result