import io
import PyPDF2
from docx import Document


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract raw text from a PDF file (bytes)."""
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text.strip())
    return "\n\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract raw text from a DOCX file (bytes)."""
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Decode plain text file."""
    return file_bytes.decode("utf-8", errors="ignore")


def parse_document(filename: str, file_bytes: bytes) -> str:
    """Route to correct parser based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return extract_text_from_docx(file_bytes)
    elif ext == "txt":
        return extract_text_from_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")