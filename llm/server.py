"""
server.py — FastAPI backend
- Serves the frontend via Jinja2 templates
- Streams pipeline stdout in real-time via SSE
- Persists model/provider config in config.json
"""

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from pydantic import BaseModel as PydanticModel

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
OUTPUT_PATH = BASE_DIR / "final_output.json"

# ── Provider presets ──────────────────────────────────────────────────────────
PROVIDER_PRESETS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-1.5-pro",
    },
    "claude": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-6",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "mistralai/mistral-7b-instruct",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "mistral",
    },
}

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Pipeline Runner", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ── Config helpers ────────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "provider": "ollama",
        "api_key": "",
        "model": "mistral",
        "base_url": "http://localhost:11434/v1",
    }


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def build_client(cfg: dict) -> tuple[OpenAI, str]:
    """Return (OpenAI client, model string) from config dict."""
    api_key  = cfg.get("api_key") or "ollama"   # ollama ignores the key
    base_url = cfg.get("base_url", "http://localhost:11434/v1")
    model    = cfg.get("model", "mistral")
    client   = OpenAI(api_key=api_key, base_url=base_url)
    return client, model


# ── Pydantic request schemas ──────────────────────────────────────────────────
class PipelineRequest(PydanticModel):
    user_input: str


class ConfigRequest(PydanticModel):
    provider:  str
    api_key:   str
    model:     str
    base_url:  str


# ── Real-time stdout capture ──────────────────────────────────────────────────
class StreamCapture:
    """
    Replaces sys.stdout/sys.stderr during the pipeline run.
    Every write() immediately pushes complete lines into the asyncio queue.
    Partial lines (no trailing newline) are also flushed so nothing is lost.
    """

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue
        self._buf   = ""

    def write(self, text: str):
        self._buf += text
        # flush every complete line immediately
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._queue.put_nowait(line)
        # also flush partial content so the browser sees it right away
        if self._buf:
            self._queue.put_nowait(self._buf)
            self._buf = ""

    def flush(self):
        if self._buf:
            self._queue.put_nowait(self._buf)
            self._buf = ""

    # Make it look like a real file object
    def isatty(self):   return False
    def fileno(self):   raise OSError("StreamCapture has no fileno")
    def readable(self): return False
    def writable(self): return True
    def seekable(self): return False


# ── Pipeline runner (thread) ──────────────────────────────────────────────────
async def stream_pipeline(user_input: str) -> AsyncIterator[str]:
    """
    Runs the pipeline in a thread-pool executor.
    Yields SSE-formatted strings as lines arrive.
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _run():
        # Force unbuffered output
        os.environ["PYTHONUNBUFFERED"] = "1"

        capture          = StreamCapture(queue)
        original_stdout  = sys.stdout
        original_stderr  = sys.stderr
        sys.stdout       = capture
        sys.stderr       = capture

        try:
            # Add this file's parent to path so pipeline modules are importable
            parent = str(BASE_DIR)
            if parent not in sys.path:
                sys.path.insert(0, parent)

            cfg            = load_config()
            client, model  = build_client(cfg)

            from main import run_development_pipeline, save_pipeline_to_json
            from codegen import run_codegen

            final_state = run_development_pipeline(user_input, client, model)
            save_pipeline_to_json(final_state, str(OUTPUT_PATH))
            run_codegen(str(OUTPUT_PATH))

            print("\n================ PIPELINE SUCCESS ================")

        except ImportError as e:
            print(f"[ERROR] Could not import pipeline modules: {e}")
            print("[ERROR] Make sure main.py, codegen.py etc. are in the same directory as server.py")
        except Exception:
            print(f"[ERROR] Pipeline crashed:\n{traceback.format_exc()}")
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            queue.put_nowait(None)   # sentinel — tells the async loop we're done

    fut = loop.run_in_executor(None, _run)

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=300.0)
        except asyncio.TimeoutError:
            yield "data: [ERROR] Pipeline timed out after 5 minutes.\n\n"
            break

        if item is None:
            yield "data: [DONE]\n\n"
            break

        # SSE format — escape embedded newlines so the protocol isn't broken
        escaped = item.replace("\n", "\\n")
        yield f"data: {escaped}\n\n"

    await fut


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def index(request: Request):
    cfg = load_config()
    return templates.TemplateResponse(
    request=request,
    name="index.html",
    context={
        "provider": cfg.get("provider", "ollama"),
        "model":    cfg.get("model", "mistral"),
    },
)

@app.post("/run-pipeline")
async def run_pipeline(req: PipelineRequest):
    """SSE endpoint — streams pipeline stdout line by line."""
    if not req.user_input.strip():
        return JSONResponse({"error": "user_input is required"}, status_code=400)

    return StreamingResponse(
        stream_pipeline(req.user_input),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering":"no",   # disable nginx buffering
            "Connection":       "keep-alive",
        },
    )


@app.get("/output-json")
async def get_output_json():
    """Returns final_output.json produced by the last pipeline run."""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            return json.load(f)
    return JSONResponse({"error": "No output yet. Run the pipeline first."}, status_code=404)


@app.get("/get-config")
async def get_config():
    """Returns current config (api_key is masked)."""
    cfg = load_config()
    safe = dict(cfg)
    if safe.get("api_key"):
        safe["api_key"] = "••••••••" + safe["api_key"][-4:]
    return safe


@app.post("/save-config")
async def save_config_endpoint(req: ConfigRequest):
    """Saves provider/model/api_key to config.json."""
    cfg = {
        "provider": req.provider,
        "api_key":  req.api_key,
        "model":    req.model,
        "base_url": req.base_url,
    }
    save_config(cfg)
    return {"status": "saved"}


@app.get("/presets")
async def get_presets():
    return PROVIDER_PRESETS


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)