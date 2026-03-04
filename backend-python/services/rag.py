import os
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ".", " "]
)


def chunk_and_store(text: str, session_id: str) -> Chroma:
    """
    Split document into 500-token chunks, embed, and store in ChromaDB.
    Returns the vectorstore for this session.
    """
    chunks = splitter.split_text(text)
    vectorstore = Chroma.from_texts(
        texts=chunks,
        embedding=embeddings,
        collection_name=session_id,
        persist_directory=CHROMA_DIR
    )
    return vectorstore


def retrieve_relevant_chunks(vectorstore: Chroma, query: str, k: int = 8) -> str:
    """
    Semantic search: retrieve top-k chunks most relevant to a query.
    Returns them as a single joined string for the LLM prompt.
    """
    docs = vectorstore.similarity_search(query, k=k)
    return "\n\n---\n\n".join([doc.page_content for doc in docs])


def cleanup_session(session_id: str):
    """Delete a collection after the session is done (optional, saves disk)."""
    try:
        vectorstore = Chroma(
            collection_name=session_id,
            embedding_function=embeddings,
            persist_directory=CHROMA_DIR
        )
        vectorstore.delete_collection()
    except Exception:
        pass  # Non-critical cleanup