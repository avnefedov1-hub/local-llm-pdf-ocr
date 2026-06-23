# PDF OCR + Ollama Chat

A local web app for scanned PDF OCR through Ollama and chat with a Russian-capable model.

## Features

- OCR for scanned PDFs via `qwen2.5vl`
- Quick actions: summarize, translate, custom prompt
- Full chat with Vikhr, with or without document context
- Streaming responses, local chat history in browser

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) 0.7.0+
- ~8-12 GB RAM

## Pull models

```powershell
ollama pull qwen2.5vl:7b
ollama pull rscr/vikhr_llama3.1_8b:Q4_K_M
```

## Run

```powershell
cd "c:\Users\av_nefedov\Local LLM"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open: http://127.0.0.1:8000

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_VISION_MODEL` | `qwen2.5vl:7b` | OCR model |
| `OLLAMA_TEXT_MODEL` | `rscr/vikhr_llama3.1_8b:Q4_K_M` | Chat model |
| `OCR_DPI` | `200` | PDF rendering quality |
| `CHAT_MAX_HISTORY` | `20` | Messages sent to chat API |
| `CHAT_DOCUMENT_CHUNK_SIZE` | `4000` | Chunk size for document context |
