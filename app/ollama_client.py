import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import OLLAMA_HOST, OLLAMA_TEXT_MODEL, OLLAMA_VISION_MODEL
from app.prompts import OCR_PROMPT


class OllamaError(Exception):
    pass


def _is_vision_model(name: str) -> bool:
    lower = name.lower()
    return "vision" in lower or "vl" in lower or "ocr" in lower


def _pick_available_model(preferred: str, models: list[str], vision: bool) -> str | None:
    if not models:
        return None
    preferred_base = preferred.split(":")[0]
    for model in models:
        if model == preferred or model.startswith(f"{preferred_base}:"):
            if _is_vision_model(model) == vision:
                return model
    for model in models:
        if _is_vision_model(model) == vision:
            return model
    return None


async def check_health() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
        try:
            response = await client.get(f"{OLLAMA_HOST}/api/tags")
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            return {"ok": False, "error": str(exc), "models": []}

        models = [m.get("name", "") for m in data.get("models", [])]
        resolved_vision_model = _pick_available_model(OLLAMA_VISION_MODEL, models, vision=True)
        resolved_text_model = _pick_available_model(OLLAMA_TEXT_MODEL, models, vision=False)
        vision_ok = resolved_vision_model is not None
        text_ok = resolved_text_model is not None
        return {
            "ok": True,
            "models": models,
            "vision_model": OLLAMA_VISION_MODEL,
            "text_model": OLLAMA_TEXT_MODEL,
            "vision_available": vision_ok,
            "text_available": text_ok,
            "resolved_vision_model": resolved_vision_model,
            "resolved_text_model": resolved_text_model,
        }


async def vision_ocr(image_b64: str, model: str | None = None, prompt: str | None = None) -> str:
    model = model or OLLAMA_VISION_MODEL
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt or OCR_PROMPT,
                "images": [image_b64],
            }
        ],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
        response = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        if response.status_code >= 400:
            raise OllamaError(response.text)
        data = response.json()
        return data.get("message", {}).get("content", "").strip()


async def chat_complete(messages: list[dict[str, str]], model: str | None = None) -> str:
    requested_model = model or OLLAMA_TEXT_MODEL
    health = await check_health()
    available_models = health.get("models", [])
    model = _pick_available_model(requested_model, available_models, vision=False) or requested_model
    payload = {"model": model, "messages": messages, "stream": False}
    async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
        response = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        if response.status_code >= 400:
            raise OllamaError(response.text)
        data = response.json()
        return data.get("message", {}).get("content", "").strip()


async def chat_stream(messages: list[dict[str, str]], model: str | None = None) -> AsyncIterator[str]:
    requested_model = model or OLLAMA_TEXT_MODEL
    health = await check_health()
    available_models = health.get("models", [])
    model = _pick_available_model(requested_model, available_models, vision=False) or requested_model
    payload = {"model": model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
        async with client.stream("POST", f"{OLLAMA_HOST}/api/chat", json=payload) as response:
            if response.status_code >= 400:
                body = await response.aread()
                raise OllamaError(body.decode())
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
                if data.get("done"):
                    break
