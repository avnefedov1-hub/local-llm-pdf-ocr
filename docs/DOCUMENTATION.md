# PDF OCR + Ollama Chat

**Код:** `C:\Проекты\Local LLM`

## Суть

OCR for scanned PDFs via `qwen2.5vl` Quick actions: summarize, translate, custom prompt Full chat with Vikhr, with or without document context

## Ключевые пункты

- OCR for scanned PDFs via `qwen2.5vl`
- Quick actions: summarize, translate, custom prompt
- Full chat with Vikhr, with or without document context
- Streaming responses, local chat history in browser
- Python 3.11+
- [Ollama](https://ollama.com) 0.7.0+
- ~8-12 GB RAM

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

ollama pull qwen2.5vl:7b ollama pull rscr/vikhr_llama3.1_8b:Q4_K_M


## Run

cd "c:\Users\av_nefedov\Local LLM" python -m venv .venv .venv\Scripts\activate pip install -r requirements.txt copy .env.example .env uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 Open: http://127.0.0.1:8000

