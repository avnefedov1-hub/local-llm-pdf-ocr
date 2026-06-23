import base64
from collections.abc import Callable
from pathlib import Path

import fitz

from app.config import OCR_DPI, OCR_FRAGMENT_COUNT, OCR_FRAGMENT_DPI, OCR_FRAGMENT_OVERLAP
from app.ollama_client import vision_ocr


def chunk_document(text: str, chunk_size: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            split_at = text.rfind("\n\n", start, end)
            if split_at > start:
                end = split_at
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def find_relevant_chunk(document_text: str, query: str, chunk_size: int) -> str:
    chunks = chunk_document(document_text, chunk_size)
    if not chunks:
        return ""
    if len(chunks) == 1:
        return chunks[0]
    query_words = {w.lower() for w in query.split() if len(w) > 2}
    if not query_words:
        return chunks[0]
    best = chunks[0]
    best_score = -1
    for chunk in chunks:
        lower = chunk.lower()
        score = sum(1 for w in query_words if w in lower)
        if score > best_score:
            best_score = score
            best = chunk
    return best


def _merge_text_blocks(texts: list[str]) -> str:
    merged_lines: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                if merged_lines and merged_lines[-1] != "":
                    merged_lines.append("")
                continue
            key = " ".join(line.lower().split())
            if key in seen:
                continue
            seen.add(key)
            merged_lines.append(line)
    return "\n".join(merged_lines).strip()


def _fragment_clips(page_rect: fitz.Rect, count: int, overlap: float) -> list[fitz.Rect]:
    count = max(1, count)
    overlap = min(max(overlap, 0.0), 0.4)
    h = page_rect.height
    segment = h / count
    clips: list[fitz.Rect] = []
    for i in range(count):
        y0 = page_rect.y0 + i * segment
        y1 = page_rect.y0 + (i + 1) * segment
        pad = segment * overlap
        if i > 0:
            y0 -= pad
        if i < count - 1:
            y1 += pad
        clips.append(fitz.Rect(page_rect.x0, max(page_rect.y0, y0), page_rect.x1, min(page_rect.y1, y1)))
    return clips


async def extract_text_from_pdf(
    pdf_path: Path,
    on_progress: Callable[[dict], None] | None = None,
) -> str:
    doc = fitz.open(pdf_path)
    total = doc.page_count
    pages_text: list[str] = []
    try:
        for index in range(total):
            page = doc.load_page(index)
            page_num = index + 1
            page_texts: list[str] = []
            if on_progress:
                on_progress(
                    {
                        "current": page_num,
                        "total": total,
                        "page_progress": 5,
                        "stage": "render",
                        "message": "Rendering page image",
                    }
                )
            pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
            png_bytes = pix.tobytes("png")
            image_b64 = base64.b64encode(png_bytes).decode("ascii")
            if on_progress:
                on_progress(
                    {
                        "current": page_num,
                        "total": total,
                        "page_progress": 30,
                        "stage": "ocr_pass_1",
                        "message": "Running OCR pass 1",
                    }
                )
            text = await vision_ocr(image_b64)
            if text.strip():
                page_texts.append(text)

            clips = _fragment_clips(page.rect, OCR_FRAGMENT_COUNT, OCR_FRAGMENT_OVERLAP)
            for frag_index, clip in enumerate(clips, start=1):
                if on_progress:
                    step_progress = 30 + int((frag_index / max(1, len(clips))) * 50)
                    on_progress(
                        {
                            "current": page_num,
                            "total": total,
                            "page_progress": step_progress,
                            "stage": f"fragment_{frag_index}",
                            "message": f"OCR fragment {frag_index}/{len(clips)}",
                        }
                    )
                frag_pix = page.get_pixmap(dpi=OCR_FRAGMENT_DPI, alpha=False, clip=clip)
                frag_b64 = base64.b64encode(frag_pix.tobytes("png")).decode("ascii")
                frag_text = await vision_ocr(frag_b64)
                if frag_text.strip():
                    page_texts.append(frag_text)
            if on_progress:
                on_progress(
                    {
                        "current": page_num,
                        "total": total,
                        "page_progress": 70,
                        "stage": "finalize",
                        "message": "Finalizing page text",
                    }
                )
            merged_text = _merge_text_blocks(page_texts)
            pages_text.append(f"--- Page {index + 1} ---\n{merged_text}")
            if on_progress:
                on_progress(
                    {
                        "current": page_num,
                        "total": total,
                        "page_progress": 100,
                        "stage": "done",
                        "message": "Page complete",
                    }
                )
    finally:
        doc.close()
    return "\n\n".join(pages_text)
