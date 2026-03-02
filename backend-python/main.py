import os
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="LexGuard AI Python Backend")

class AnalyzeRequest(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"message": "LexGuard AI Python Backend running"}

@app.post("/analyze")
def analyze_endpoint(request: AnalyzeRequest):
    # Placeholder for running langchain or document analysis
    # e.g. use langchain, google-generativeai, etc.
    return {"status": "success", "result": f"Analyzed: {request.text[:20]}..."}

@app.post("/upload")
def upload_document(file: UploadFile = File(...)):
    # Placeholder for pypdf2, python-docx, chromadb processing
    return {"filename": file.filename, "status": "processed"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
