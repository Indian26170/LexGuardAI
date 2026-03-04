import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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
"""


def build_analysis_prompt(document_text: str, jurisdiction: Optional[str] = None) -> str:
    """Build the full prompt with optional jurisdiction context."""
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
    """Prompt to translate summary bullets into target language."""
    bullets_text = "\n".join([f"{i+1}. {b}" for i, b in enumerate(summary_bullets)])
    return f"""
Translate the following 5 legal summary bullets into {target_language}.
Preserve legal accuracy — do NOT simplify terms that change meaning.
Return ONLY a JSON array of 5 translated strings, no markdown.

Original bullets:
{bullets_text}
"""


def analyze_document(
    document_text: str,
    jurisdiction: Optional[str] = None,
    target_language: Optional[str] = None
) -> dict:
    """
    Run the full Gemini analysis on document text.
    Returns parsed JSON result dict.
    """
    # Step 1: Main legal analysis
    analysis_prompt = build_analysis_prompt(document_text, jurisdiction)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=analysis_prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=4096,
        )
    )
    raw_text = response.text.strip()

    # Strip markdown code fences if Gemini wraps in ```json
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    result = json.loads(raw_text)

    # Step 2: Multilingual translation (optional)
    if target_language and target_language.strip().lower() not in ("english", "en"):
        try:
            translation_prompt = build_translation_prompt(
                result.get("summary", []), target_language
            )
            trans_response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=translation_prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            trans_raw = trans_response.text.strip()
            trans_raw = re.sub(r"^```(?:json)?\s*", "", trans_raw)
            trans_raw = re.sub(r"\s*```$", "", trans_raw)
            result["summary_translated"] = json.loads(trans_raw)
        except Exception as e:
            result["summary_translated"] = None  # Non-fatal

    return result