import asyncio
import json
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import CHAT_DOCUMENT_CHUNK_SIZE, CHAT_MAX_HISTORY, STATIC_DIR, UPLOAD_DIR
from app.ocr import extract_text_from_pdf, find_relevant_chunk
from app.ollama_client import OllamaError, chat_complete, chat_stream, check_health
from app.prompts import SUMMARIZE_PROMPT, build_chat_system, translate_prompt

app = FastAPI(title="PDF OCR + Ollama Chat")


class TextRequest(BaseModel):
    text: str


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "en"


class CustomRequest(BaseModel):
    text: str
    prompt: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    document_text: str = ""
    use_document: bool = False


@app.get("/api/health")
async def health():
    return await check_health()


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    save_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"
    content = await file.read()
    save_path.write_bytes(content)

    async def event_stream():
        progress_queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
        result: dict[str, str] = {"text": ""}
        error: dict[str, str] = {"msg": ""}

        def on_progress(payload: dict) -> None:
            progress_queue.put_nowait(("progress", payload))

        async def run_ocr() -> None:
            try:
                result["text"] = await extract_text_from_pdf(save_path, on_progress=on_progress)
            except Exception as exc:  # noqa: BLE001
                error["msg"] = str(exc)
            finally:
                progress_queue.put_nowait(("done", {}))

        task = asyncio.create_task(run_ocr())

        try:
            while True:
                kind, payload = await progress_queue.get()
                if kind == "progress":
                    yield f"data: {json.dumps({'type': 'progress', **payload}, ensure_ascii=False)}\n\n"
                elif kind == "done":
                    await task
                    if error["msg"]:
                        yield f"data: {json.dumps({'type': 'error', 'message': error['msg']}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'complete', 'text': result['text']}, ensure_ascii=False)}\n\n"
                    break
        finally:
            save_path.unlink(missing_ok=True)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/summarize")
async def summarize(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Document text is empty")
    messages = [
        {"role": "system", "content": "You are Vikhr, a Russian-speaking AI assistant."},
        {"role": "user", "content": f"{SUMMARIZE_PROMPT}\n\n{req.text}"},
    ]
    try:
        result = await chat_complete(messages)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"result": result}


@app.post("/api/translate")
async def translate(req: TranslateRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Document text is empty")
    prompt = translate_prompt(req.target_lang)
    messages = [
        {"role": "system", "content": "You are Vikhr, a Russian-speaking AI assistant."},
        {"role": "user", "content": f"{prompt}\n\n{req.text}"},
    ]
    try:
        result = await chat_complete(messages)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"result": result}


@app.post("/api/custom")
async def custom(req: CustomRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Document text is empty")
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    messages = [
        {"role": "system", "content": "You are Vikhr, a Russian-speaking AI assistant."},
        {"role": "user", "content": f"{req.prompt}\n\nDocument:\n{req.text}"},
    ]
    try:
        result = await chat_complete(messages)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"result": result}


def _trim_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return messages[-CHAT_MAX_HISTORY:]


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="Chat history is empty")

    history = [{"role": m.role, "content": m.content} for m in req.messages if m.role in ("user", "assistant")]
    history = _trim_history(history)
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")

    system = build_chat_system(req.document_text, req.use_document)
    if req.use_document and req.document_text.strip():
        chunk = find_relevant_chunk(req.document_text, last_user, CHAT_DOCUMENT_CHUNK_SIZE)
        system = f"{system}\n\nDocument context:\n{chunk}"

    payload_messages = [{"role": "system", "content": system}, *history]

    async def event_stream():
        try:
            async for token in chat_stream(payload_messages):
                yield f"data: {json.dumps({'type': 'token', 'token': token}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except OllamaError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
