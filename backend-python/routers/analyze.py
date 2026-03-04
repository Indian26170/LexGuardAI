import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional

from models.schemas import AnalyzeRequest, AnalyzeResponse
from services.parser import parse_document
from services.rag import chunk_and_store, cleanup_session
from services.gemini import analyze_document
from services.jurisdiction import check_jurisdiction_conflicts

router = APIRouter()

DEMO_RESPONSE = {
    "legalScore": 23,
    "document_type_detected": "Employment Contract",
    "clauses": [
        {
            "text": "The Employer shall own all inventions, ideas, code, designs, and creative works produced by the Employee, whether during work hours or personal time.",
            "classification": "RED",
            "reason": "Extreme IP grab clause — employer claims ownership even of work done in your personal time with your own resources. This is unenforceable under Indian Contract Act Section 23 as it is against public policy.",
            "counterDraft": "Employer owns work created during working hours using company resources only. Employee retains full rights to personal projects created outside work hours without use of company resources."
        },
        {
            "text": "The Employer reserves the right to terminate this agreement at any time, for any reason or no reason, without prior notice, severance pay, or explanation.",
            "classification": "RED",
            "reason": "Completely one-sided termination clause. Under Indian labour law, termination without notice or severance is challengeable, especially after 240 days of continuous employment.",
            "counterDraft": "Either party may terminate with 30 days written notice. Employer shall provide severance of one month salary per year of service for terminations without cause."
        },
        {
            "text": "Any disputes shall be resolved exclusively through private arbitration chosen by the Employer. Employee waives all rights to approach any court of law.",
            "classification": "RED",
            "reason": "Forced arbitration where the employer picks the arbitrator is heavily biased. Waiving court access entirely may be unenforceable under the Arbitration and Conciliation Act 1996.",
            "counterDraft": "Disputes shall be resolved through arbitration with a mutually agreed neutral arbitrator. Either party retains the right to approach courts for urgent injunctive relief."
        },
        {
            "text": "Employee agrees not to work for any competitor or start any business for 5 years after termination, worldwide.",
            "classification": "RED",
            "reason": "Non-compete clauses are largely unenforceable in India under Section 27 of the Indian Contract Act. A 5-year worldwide ban is excessive and would not hold up in any Indian court.",
            "counterDraft": "Employee agrees not to directly solicit the company's existing clients for 6 months post-termination within the same city of employment."
        },
        {
            "text": "Employee shall be personally liable for any losses, damages, or legal costs incurred by the Employer, with no upper limit on liability amount.",
            "classification": "RED",
            "reason": "Unlimited personal liability is extremely dangerous. This could expose you to financial ruin for decisions made in good faith during employment.",
            "counterDraft": "Employee liability shall be limited to direct damages caused by proven gross negligence or wilful misconduct, capped at three months gross salary."
        },
        {
            "text": "Compensation shall be determined at the sole discretion of the Employer and may be revised downward at any time without prior notice or consent.",
            "classification": "RED",
            "reason": "Allowing the employer to cut your salary without notice or agreement is a fundamental breach of contract principles and violates basic employment protections.",
            "counterDraft": "Salary may only be revised downward with 60 days written notice and written consent of the Employee. Annual increments shall be performance-linked and reviewed mutually."
        },
        {
            "text": "Employee shall never disclose salary or working conditions to any third party including family members, for life.",
            "classification": "YELLOW",
            "reason": "Lifetime confidentiality on salary is unreasonable and likely unenforceable. Reasonable confidentiality on business secrets is standard, but personal compensation is your own information.",
            "counterDraft": "Employee agrees to keep proprietary business information, client data, and trade secrets confidential during employment and for 2 years post-termination. Salary confidentiality applies during employment only."
        }
    ],
    "summary": [
        "This contract scores 23/100 — it is one of the most one-sided employment agreements possible and should not be signed without major revisions.",
        "You would permanently give up rights to everything you create, even in your own time — this is an extreme IP grab that Indian courts often reject.",
        "The employer can fire you instantly with no notice or pay, while you must give 90 days notice — this imbalance is legally challengeable after 240 days of employment.",
        "The forced arbitration clause and blanket court waiver may be unenforceable under the Arbitration and Conciliation Act 1996 — you likely retain the right to approach labour tribunals.",
        "The 5-year worldwide non-compete is almost certainly void under Section 27 of the Indian Contract Act — Indian courts consistently refuse to enforce such broad restrictions."
    ],
    "jurisdiction_flags": [
        {
            "clause": "Unlimited personal liability with no cap",
            "conflict": "Violates principles of reasonable contract terms under Indian Contract Act 1872",
            "applicable_law": "Indian Contract Act 1872, Section 23 — agreements against public policy are void"
        },
        {
            "clause": "5 year worldwide non-compete",
            "conflict": "Restraint of trade is void in India regardless of reasonableness",
            "applicable_law": "Indian Contract Act 1872, Section 27 — agreements in restraint of trade are void"
        },
        {
            "clause": "Termination without notice or severance",
            "conflict": "Violates Industrial Disputes Act protections for employees with 240+ days service",
            "applicable_law": "Industrial Disputes Act 1947, Section 25F — retrenchment compensation mandatory"
        }
    ],
    "summary_translated": None
}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    target_language: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    jurisdiction: Optional[str] = Form(None),
    demo: Optional[str] = Form(None),
):
    # --- DEMO MODE --- returns instantly, no Gemini call needed
    if demo and demo.lower() == "true":
        return JSONResponse(content=DEMO_RESPONSE)

    # --- 1. Extract text ---
    if file:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        try:
            document_text = parse_document(file.filename, file_bytes)
        except ValueError as e:
            raise HTTPException(status_code=415, detail=str(e))
    elif text:
        document_text = text.strip()
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a file upload or raw text."
        )

    if len(document_text) < 100:
        raise HTTPException(
            status_code=422,
            detail="Document text too short to analyze. Minimum 100 characters."
        )

    # --- 2. RAG: chunk and embed ---
    session_id = str(uuid.uuid4())
    try:
        vectorstore = chunk_and_store(document_text, session_id)
    except Exception:
        vectorstore = None

    # --- 3. Run Gemini analysis ---
    try:
        result = analyze_document(
            document_text=document_text,
            jurisdiction=jurisdiction,
            target_language=target_language
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI analysis failed: {str(e)}"
        )

    # --- 4. Cross-border jurisdiction check ---
    if jurisdiction and jurisdiction.strip():
        try:
            jurisdiction_flags = check_jurisdiction_conflicts(document_text, jurisdiction)
            if jurisdiction_flags:
                result["jurisdiction_flags"] = jurisdiction_flags
        except Exception:
            pass

    # --- 5. Cleanup ChromaDB session in background ---
    if vectorstore:
        background_tasks.add_task(cleanup_session, session_id)

    return JSONResponse(content=result)


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "LexGuard AI Python Brain"}