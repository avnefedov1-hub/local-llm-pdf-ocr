OCR_PROMPT = (
    "Extract text from this image. "
    "Return only text."
)

CHAT_SYSTEM = (
    "You are Vikhr, a Russian-speaking AI assistant. "
    "Always respond in Russian, clearly and concisely."
)

CHAT_WITH_DOCUMENT = (
    "You are Vikhr, a Russian-speaking AI assistant. "
    "Always respond in Russian. Use the provided document context. "
    "If the answer is not in the document, say so explicitly."
)

SUMMARIZE_PROMPT = (
    "Create a concise summary of the following document in Russian. "
    "Highlight key points as a bullet list."
)

TRANSLATE_PROMPT_RU = "Translate the following text into Russian. Preserve structure and formatting."
TRANSLATE_PROMPT_EN = "Translate the following text into English. Preserve structure and formatting."


def build_chat_system(document_text: str | None, use_document: bool) -> str:
    if use_document and document_text and document_text.strip():
        return CHAT_WITH_DOCUMENT
    return CHAT_SYSTEM


def translate_prompt(target_lang: str) -> str:
    if target_lang.lower() in ("ru", "russian"):
        return TRANSLATE_PROMPT_RU
    return TRANSLATE_PROMPT_EN
