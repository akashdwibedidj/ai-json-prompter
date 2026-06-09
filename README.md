# 🚀 AI JSON prompter

An AI-powered application development pipeline that transforms a plain-English idea into a structured app design — complete with intent extraction, architecture generation, validation, and code generation. Supports multiple LLM providers via an OpenAI-compatible API interface, with a real-time streaming web UI.

---

## ✨ Features

- **Multi-stage AI pipeline** — Intent → Architecture → App Design → Validation → Repair → Codegen
- **Real-time streaming output** — Watch every pipeline stage execute live in the browser via Server-Sent Events (SSE)
- **Multi-provider support** — Works with OpenAI, Google Gemini, Anthropic Claude, OpenRouter, and local Ollama models
- **Self-repairing pipeline** — Automatically detects and repairs structural issues before code generation
- **Persistent config** — Provider, model, and API key saved to `config.json`; switchable from the UI
- **REST API** — Clean FastAPI backend with endpoints for pipeline runs, config management, and output retrieval

---

## 🏗️ Architecture

```
User Input (natural language)
        │
        ▼
┌───────────────┐
│  Stage 1      │  Intent Extraction      → intent_name, user_goal
├───────────────┤
│  Stage 2      │  Architecture Layout    → project_name, modules, structure
├───────────────┤
│  Stage 3      │  App Design             → full application spec
├───────────────┤
│  Stage 4      │  Validation             → detect structural issues
├───────────────┤
│  Stage 5      │  Repair (if needed)     → auto-fix issues
├───────────────┤
│  Stage 6      │  Re-validation          → confirm clean state
├───────────────┤
│  Codegen      │  Code generation        → output files from final_output.json
└───────────────┘
```

All pipeline state is accumulated in `pipeline_memory` and saved to `final_output.json` on completion.

---

## 📁 Project Structure

```
.
├── server.py           # FastAPI backend — SSE streaming, config, routes
├── main.py             # Core pipeline orchestration
├── intents.py          # Stage 1: intent extraction prompt + schema
├── architecture.py     # Stage 2: architecture generation prompt + schema
├── app_design.py       # Stage 3: app design prompt + schema
├── validation.py       # Stage 4: pipeline validation logic
├── repair.py           # Stage 5: auto-repair logic
├── codegen.py          # Code generation from final_output.json
├── config.json         # Saved provider/model/API key (auto-created)
├── final_output.json   # Output of the last pipeline run
├── static/             # Frontend static assets (CSS, JS)
└── templates/
    └── index.html      # Jinja2 web UI template
```

---

## ⚙️ Setup

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
git clone https://github.com/your-username/pipeline-runner.git
cd pipeline-runner
pip install -r requirements.txt
```

### Running the Server

```bash
python server.py
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

Alternatively, with uvicorn directly:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🔧 Configuration

Configuration is stored in `config.json` and can be updated from the web UI or directly via the API.

```json
{
  "provider": "ollama",
  "api_key": "",
  "model": "mistral",
  "base_url": "http://localhost:11434/v1"
}
```

### Supported Providers

| Provider    | Base URL                                                  | Default Model               |
|-------------|-----------------------------------------------------------|-----------------------------|
| OpenAI      | `https://api.openai.com/v1`                               | `gpt-4o`                    |
| Gemini      | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-1.5-pro`            |
| Claude      | `https://api.anthropic.com/v1`                            | `claude-sonnet-4-6`         |
| OpenRouter  | `https://openrouter.ai/api/v1`                            | `mistralai/mistral-7b-instruct` |
| Ollama      | `http://localhost:11434/v1`                               | `mistral`                   |

---

## 🖥️ Usage

### Via the Web UI

1. Open [http://localhost:8000](http://localhost:8000)
2. Configure your provider and model in the settings panel
3. Enter your app idea in plain English (e.g. *"a video streaming app with user login, uploads, comments, and likes"*)
4. Click **Run** and watch the pipeline execute in real time

### Via the CLI (standalone)

You can also run the pipeline directly without the server:

```bash
python main.py
```

Edit the `user_idea` variable at the bottom of `main.py` to change the input. The pipeline will read from `config.json` for provider settings and write results to `final_output.json`.

---

## 🌐 API Reference

### `POST /run-pipeline`

Runs the full pipeline and streams stdout via SSE.

**Request body:**
```json
{ "user_input": "a task management app with teams and deadlines" }
```

**Response:** `text/event-stream` — one SSE `data:` line per log message, ending with `data: [DONE]`.

---

### `GET /output-json`

Returns the `final_output.json` produced by the last pipeline run.

---

### `GET /get-config`

Returns the current config. The `api_key` field is masked (last 4 characters visible).

---

### `POST /save-config`

Saves provider/model/API key settings.

**Request body:**
```json
{
  "provider": "openai",
  "api_key": "sk-...",
  "model": "gpt-4o",
  "base_url": "https://api.openai.com/v1"
}
```

---

### `GET /presets`

Returns all built-in provider presets (base URLs and default models).

---

### `GET /health`

Returns `{ "status": "ok" }`.

---

## 🛠️ How the Pipeline Works

Each stage calls the LLM with a structured prompt and a Pydantic schema, using `client.beta.chat.completions.parse` for validated structured output. If the response fails schema validation, the pipeline automatically retries with the error message injected into the next prompt.

After all three generation stages complete, a dedicated **validation** step inspects the full `pipeline_memory` for logical or structural inconsistencies. Any issues found trigger an automated **repair** pass, followed by a second validation to confirm the fix.

Finally, `codegen.py` consumes `final_output.json` to generate the actual application files.

---

## 📦 Dependencies

Key packages (see `requirements.txt` for full list):

```
fastapi
uvicorn
openai
pydantic
jinja2
python-multipart
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
