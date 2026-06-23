import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "rscr/vikhr_llama3.1_8b:Q4_K_M")
OCR_DPI = int(os.getenv("OCR_DPI", "200"))
OCR_FRAGMENT_DPI = int(os.getenv("OCR_FRAGMENT_DPI", "280"))
OCR_FRAGMENT_COUNT = int(os.getenv("OCR_FRAGMENT_COUNT", "3"))
OCR_FRAGMENT_OVERLAP = float(os.getenv("OCR_FRAGMENT_OVERLAP", "0.12"))
APP_LANGUAGE = os.getenv("APP_LANGUAGE", "ru")
CHAT_MAX_HISTORY = int(os.getenv("CHAT_MAX_HISTORY", "20"))
CHAT_DOCUMENT_CHUNK_SIZE = int(os.getenv("CHAT_DOCUMENT_CHUNK_SIZE", "4000"))

UPLOAD_DIR.mkdir(exist_ok=True)
