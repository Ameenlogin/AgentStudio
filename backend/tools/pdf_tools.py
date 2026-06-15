"""PDF tools: extract text, inspect, and create PDFs from text/Markdown — all
sandboxed to the workspace. Degrades with a clear message if the optional
libraries aren't installed yet."""
import os
from tools.sandbox import resolve, rel


def pdf_read(path: str, max_pages: int = 50) -> str:
    """Extract text from a PDF file."""
    p = resolve(path)
    if not os.path.isfile(p):
        return f"Error: file not found: {rel(p)}"
    try:
        from pypdf import PdfReader
    except Exception:
        return "Error: PDF support not installed. Run: pip install pypdf"
    try:
        reader = PdfReader(p)
        out = []
        for i, page in enumerate(reader.pages[:max_pages], 1):
            text = (page.extract_text() or "").strip()
            out.append(f"--- page {i} ---\n{text}")
        joined = "\n\n".join(out)
        if len(reader.pages) > max_pages:
            joined += f"\n\n[...{len(reader.pages) - max_pages} more pages]"
        return joined[:60000] or "[no extractable text — may be a scanned PDF]"
    except Exception as e:
        return f"Error reading PDF {rel(p)}: {e}"


def pdf_info(path: str) -> str:
    """Report page count and metadata for a PDF."""
    p = resolve(path)
    if not os.path.isfile(p):
        return f"Error: file not found: {rel(p)}"
    try:
        from pypdf import PdfReader
    except Exception:
        return "Error: PDF support not installed. Run: pip install pypdf"
    try:
        reader = PdfReader(p)
        meta = reader.metadata or {}
        lines = [f"{rel(p)} — {len(reader.pages)} page(s)"]
        for k in ("/Title", "/Author", "/Subject", "/Creator"):
            if meta.get(k):
                lines.append(f"{k[1:]}: {meta.get(k)}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def pdf_create(path: str, content: str, title: str = "") -> str:
    """Create a PDF from plain text / light Markdown (#, ##, - bullets)."""
    p = resolve(path)
    if not p.lower().endswith(".pdf"):
        p += ".pdf"
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
    except Exception:
        return "Error: PDF creation not installed. Run: pip install fpdf2"
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_margins(18, 18, 18)
        pdf.add_page()

        def line_cell(h, text):
            # Keep the cursor at the left margin so each line gets full width.
            pdf.multi_cell(0, h, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if title:
            pdf.set_font("Helvetica", "B", 18)
            line_cell(9, title)
            pdf.ln(2)
        for raw in (content or "").split("\n"):
            line = raw.rstrip()
            # latin-1 safe (fpdf core fonts); drop unsupported glyphs gracefully
            safe = line.encode("latin-1", "replace").decode("latin-1")
            if line.startswith("# "):
                pdf.set_font("Helvetica", "B", 16); line_cell(8, safe[2:])
            elif line.startswith("## "):
                pdf.set_font("Helvetica", "B", 13); line_cell(7, safe[3:])
            elif line.startswith(("- ", "* ")):
                pdf.set_font("Helvetica", "", 11); line_cell(6, "  -  " + safe[2:])
            elif not line:
                pdf.ln(3)
            else:
                pdf.set_font("Helvetica", "", 11); line_cell(6, safe)
        pdf.output(p)
        return f"Created PDF {rel(p)} ({os.path.getsize(p)} bytes)."
    except Exception as e:
        return f"Error creating PDF: {e}"
