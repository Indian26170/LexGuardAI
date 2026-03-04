import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.analyze import router as analyze_router

load_dotenv()

app = FastAPI(
    title="LexGuard AI — Python Brain",
    description="FastAPI service for legal document analysis using Gemini + LangChain",
    version="1.0.0"
)

# CORS — allow Node.js backend and local frontend
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(analyze_router, prefix="")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)