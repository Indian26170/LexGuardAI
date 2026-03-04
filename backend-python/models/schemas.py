from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class Classification(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class Clause(BaseModel):
    text: str
    classification: Classification
    reason: str
    counterDraft: Optional[str] = None


class JurisdictionFlag(BaseModel):
    clause: str
    conflict: str
    applicable_law: str


class AnalyzeRequest(BaseModel):
    text: Optional[str] = None          # raw text (if no file)
    target_language: Optional[str] = None  # e.g. "Hindi", "Punjabi"
    document_type: Optional[str] = None   # e.g. "employment", "rental"
    jurisdiction: Optional[str] = None    # e.g. "India-USA", "India"


class AnalyzeResponse(BaseModel):
    legalScore: int                        # 0–100
    clauses: List[Clause]
    summary: List[str]                     # 5 bullet points
    summary_translated: Optional[List[str]] = None
    jurisdiction_flags: Optional[List[JurisdictionFlag]] = None
    document_type_detected: Optional[str] = None