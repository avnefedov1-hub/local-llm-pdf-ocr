const STORAGE_KEY = "pdf-ollama-chat-history";

const els = {
  health: document.getElementById("health-status"),
  uploadZone: document.getElementById("upload-zone"),
  fileInput: document.getElementById("file-input"),
  browseBtn: document.getElementById("browse-btn"),
  progress: document.getElementById("ocr-progress"),
  documentText: document.getElementById("document-text"),
  summarizeBtn: document.getElementById("summarize-btn"),
  translateBtn: document.getElementById("translate-btn"),
  translateLang: document.getElementById("translate-lang"),
  customPrompt: document.getElementById("custom-prompt"),
  customBtn: document.getElementById("custom-btn"),
  chatMessages: document.getElementById("chat-messages"),
  chatInput: document.getElementById("chat-input"),
  chatSend: document.getElementById("chat-send"),
  chatStop: document.getElementById("chat-stop"),
  chatClear: document.getElementById("chat-clear"),
  useDocument: document.getElementById("use-document"),
};

let chatHistory = loadHistory();
let chatAbortController = null;

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
}

function renderChat() {
  els.chatMessages.innerHTML = "";
  for (const msg of chatHistory) appendMessage(msg.role, msg.content, false);
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}

function appendMessage(role, content, persist = true) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = content;
  els.chatMessages.appendChild(div);
  els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
  if (persist) {
    chatHistory.push({ role, content });
    saveHistory();
  }
  return div;
}

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (!data.ok) {
      els.health.textContent = "Ollama unavailable";
      els.health.className = "health error";
      return;
    }
    const parts = [];
    parts.push(data.vision_available ? "OCR OK" : "OCR model missing");
    parts.push(data.text_available ? "Chat OK" : "Chat model missing");
    els.health.textContent = parts.join(" ? ");
    els.health.className = data.vision_available && data.text_available ? "health ok" : "health error";
  } catch {
    els.health.textContent = "Ollama unavailable";
    els.health.className = "health error";
  }
}

async function uploadPdf(file) {
  els.progress.classList.remove("hidden");
  els.progress.textContent = "Uploading and running OCR...";

  const form = new FormData();
  form.append("file", file);

  const res = await fetch("/api/upload", { method: "POST", body: form });
  if (!res.ok) {
    els.progress.textContent = "Upload failed";
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = JSON.parse(line.slice(6));
      if (payload.type === "progress") {
        const stageText = payload.message ? ` - ${payload.message}` : "";
        const inPage = typeof payload.page_progress === "number" ? ` (${payload.page_progress}%)` : "";
        els.progress.textContent = `Processing page ${payload.current} of ${payload.total}${inPage}${stageText}`;
      } else if (payload.type === "complete") {
        els.documentText.value = payload.text;
        els.progress.textContent = "OCR complete";
        appendMessage("assistant", "Document recognized. You can now ask questions in chat.");
      } else if (payload.type === "error") {
        els.progress.textContent = `Error: ${payload.message}`;
      }
    }
  }
}

function setupUpload() {
  els.browseBtn.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", () => {
    if (els.fileInput.files[0]) uploadPdf(els.fileInput.files[0]);
  });

  els.uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    els.uploadZone.classList.add("dragover");
  });
  els.uploadZone.addEventListener("dragleave", () => els.uploadZone.classList.remove("dragover"));
  els.uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    els.uploadZone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file && file.name.toLowerCase().endsWith(".pdf")) uploadPdf(file);
  });
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

async function runAction(endpoint, userLabel, body = {}) {
  const text = els.documentText.value.trim();
  if (!text) {
    alert("Upload and process a PDF first");
    return;
  }

  appendMessage("user", userLabel);
  try {
    const data = await postJson(endpoint, { text, ...body });
    appendMessage("assistant", data.result);
  } catch (err) {
    appendMessage("assistant", `Error: ${err.message}`);
  }
}

async function streamChat() {
  const content = els.chatInput.value.trim();
  if (!content) return;

  appendMessage("user", content);
  els.chatInput.value = "";

  const assistantEl = appendMessage("assistant", "", false);
  chatHistory.push({ role: "assistant", content: "" });

  chatAbortController = new AbortController();
  els.chatSend.classList.add("hidden");
  els.chatStop.classList.remove("hidden");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: chatHistory.slice(0, -1),
        document_text: els.documentText.value,
        use_document: els.useDocument.checked,
      }),
      signal: chatAbortController.signal,
    });

    if (!res.ok || !res.body) {
      throw new Error("Chat request failed");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let full = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));
        if (payload.type === "token") {
          full += payload.token;
          assistantEl.textContent = full;
          els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
        } else if (payload.type === "error") {
          assistantEl.textContent = `Error: ${payload.message}`;
          full = assistantEl.textContent;
        }
      }
    }

    chatHistory[chatHistory.length - 1].content = full;
    saveHistory();
  } catch (err) {
    if (err.name !== "AbortError") {
      assistantEl.textContent = `Error: ${err.message}`;
      chatHistory[chatHistory.length - 1].content = assistantEl.textContent;
      saveHistory();
    } else {
      chatHistory.pop();
      assistantEl.remove();
      saveHistory();
    }
  } finally {
    chatAbortController = null;
    els.chatSend.classList.remove("hidden");
    els.chatStop.classList.add("hidden");
  }
}

els.summarizeBtn.addEventListener("click", () =>
  runAction("/api/summarize", "Summarize this document", {})
);

els.translateBtn.addEventListener("click", () =>
  runAction("/api/translate", `Translate document to ${els.translateLang.value.toUpperCase()}`, {
    target_lang: els.translateLang.value,
  })
);

els.customBtn.addEventListener("click", () => {
  const prompt = els.customPrompt.value.trim();
  if (!prompt) {
    alert("Enter a custom prompt");
    return;
  }
  runAction("/api/custom", prompt, { prompt });
});

els.chatSend.addEventListener("click", streamChat);
els.chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    streamChat();
  }
});

els.chatStop.addEventListener("click", () => chatAbortController?.abort());
els.chatClear.addEventListener("click", () => {
  chatHistory = [];
  saveHistory();
  renderChat();
});

setupUpload();
renderChat();
checkHealth();
