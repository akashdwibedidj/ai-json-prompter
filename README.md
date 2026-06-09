# 🤖 AI JSON Prompter

An AI-powered multi-stage pipeline that transforms a plain-English app idea into a fully structured, executable application — complete with UI schema, API schema, database schema, auth rules, and generated code. Supports multiple LLM providers via an OpenAI-compatible interface, with a real-time streaming web UI.

---

## ⚠️ Important — Read Before Starting

> **Please define your API key in the top ribbon before starting the pipeline. You can ignore this if it's already set.**

- I used the **Ollama provider with the `mistral` model** to avoid running out of tokens. If your model has a low token limit, it will break halfway through the pipeline — make sure your model can handle long completions.
- Please ensure your API key is correctly configured in the settings panel before running.
- If the hosted version doesn't work, you can watch the demo video or download the code from GitHub, follow the instructions below, and run it in your local environment.
- **About JSON repairing:** The repair engine works, but occasionally the repair itself introduces new logical errors (not syntax errors). This appears to be an inherent LLM behaviour — the model sometimes finds problems where there are none. If this happens, you can safely ignore those logical warnings and proceed.

---

## 🧩 Problem Statement

Users input open-ended instructions like:

> *"Build a CRM with login, contacts, dashboard, role-based access, and premium plan with payments. Admins can see analytics."*

The system converts this into a strict, complete, and reliable configuration that includes:

- **UI schema** — pages, components, layouts
- **API schema** — endpoints, methods, validation
- **Database schema** — tables, relations
- **Auth system** — roles, permissions
- **Business logic** — premium gating, role access

---

## ✨ Features

- **Multi-stage AI pipeline** — Intent → Architecture → App Design → Validation → Repair → Codegen
- **Real-time streaming output** — Watch every pipeline stage execute live in the browser via Server-Sent Events (SSE)
- **Strict schema enforcement** — Valid JSON guaranteed, required fields enforced, cross-layer consistency checked
- **Validation + repair engine** — Automatically detects and repairs structural issues before code generation
- **Execution-ready output** — Pipeline output directly generates a runnable FastAPI app, no manual fixes needed
- **Multi-provider support** — Works with OpenAI, Google Gemini, Anthropic Claude, OpenRouter, and local Ollama
- **Persistent config** — Provider, model, and API key saved to `config.json`; switchable from the UI

---

## 🏗️ Pipeline Architecture

```
User Input (natural language)
        │
        ▼
┌─────────────────┐
│  Stage 1        │  Intent Extraction      → intent_name, user_goal, entities
├─────────────────┤
│  Stage 2        │  System Design Layer    → architecture, modules, roles, flows
├─────────────────┤
│  Stage 3        │  Schema Generation      → UI config, API config, DB schema, Auth rules
├─────────────────┤
│  Stage 4        │  Validation             → detect missing keys, mismatches, hallucinations
├─────────────────┤
│  Stage 5        │  Repair (if needed)     → auto-fix specific issues (not blind full retry)
├─────────────────┤
│  Stage 6        │  Re-validation          → confirm clean state
├─────────────────┤
│  Codegen        │  Code generation        → generates working app in generated_app/
└─────────────────┘
```

All pipeline state is saved to `final_output.json` on completion.

> **Single prompt architecture = immediate rejection.** Every stage is mandatory and isolated.

---

## 🚀 What This System Addresses

### 1. Multi-Stage Generation Pipeline
The pipeline is broken into discrete stages — no single monolithic prompt. Each stage builds on the last with structured, validated output.

### 2. Strict Schema Enforcement
- Valid JSON is always guaranteed
- Required fields are enforced via Pydantic schemas
- Cross-layer consistency: API fields match DB schema, UI fields map to API endpoints

### 3. Validation + Repair Engine
The system detects and handles:
- Invalid JSON
- Missing keys
- Hallucinated fields
- Schema mismatches
- Logical inconsistencies

Repair targets specific broken parts — not a blind full retry.

### 4. Deterministic Behaviour
Achieved through structured prompting, Pydantic-constrained decoding, and modular generation. Same input produces consistent output within reasonable variance.

### 5. Execution Awareness ✅
**This is how it's proven:** After the pipeline finishes (via `server.py`, `main.py`, or `original_main.py`), it automatically creates a `generated_app/` directory containing a fully runnable FastAPI application. Run it and it opens in your browser at `http://localhost:8000/docs` — no manual fixes required.

### 6. Failure Handling
The pipeline handles vague, conflicting, or underspecified inputs by making reasonable documented assumptions and continuing rather than crashing.

---

## 📁 Project Structure

```
.
├── server.py             # FastAPI backend — SSE streaming, config, routes
├── main.py               # Core pipeline orchestration (with web UI)
├── original_main.py      # Standalone CLI pipeline (no server needed)
├── intents.py            # Stage 1: intent extraction prompt + schema
├── architecture.py       # Stage 2: architecture generation prompt + schema
├── app_design.py         # Stage 3: app design prompt + schema
├── validation.py         # Stage 4: pipeline validation logic
├── repair.py             # Stage 5: auto-repair logic
├── codegen.py            # Code generation from final_output.json
├── config.json           # Saved provider/model/API key (auto-created)
├── final_output.json     # Structured output of the last pipeline run
├── generated_app/        # ✅ The runnable app produced by the pipeline
├── static/               # Frontend static assets (CSS, JS)
└── templates/
    └── index.html        # Jinja2 web UI template
```

---

## 🛠️ How the Pipeline Works

Each stage calls the LLM with a structured prompt and a Pydantic schema, using `client.beta.chat.completions.parse` for validated structured output. If the response fails schema validation, the pipeline automatically retries with the error message injected into the next prompt.

After all three generation stages complete, a dedicated **validation** step inspects the full `pipeline_memory` for logical or structural inconsistencies. Any issues found trigger an automated **repair** pass, followed by a second validation to confirm the fix.

Finally, `codegen.py` consumes `final_output.json` to generate the actual application files.

---

## ⚙️ Setup

### Prerequisites

- Python 3.10+
- pip
- (Optional) [Ollama](https://ollama.com/) for free local inference

### Installation

```bash
git clone https://github.com/your-username/ai-json-prompter.git
cd ai-json-prompter
pip install -r requirements.txt
```

---

## 🖥️ How to Run

### Option 1 — Web UI (recommended)

```bash
python server.py or llm/server.py
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

1. Set your API key and provider in the top ribbon settings
2. Type your app idea in plain English
3. Click **Run** and watch the pipeline stream in real time
4. When it finishes, your generated app is in `generated_app/`

### Option 2 — Terminal only (no server)

```bash
python original_main.py
```

Edit the `user_idea` variable inside the file to change the input. Results are written to `final_output.json` and `generated_app/` is created automatically.

### Running the Generated App

After either option completes:

```bash
cd generated_app
python main.py
```

Then open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser to see the fully interactive API documentation of your generated application.

---

## 🔧 Configuration

Configuration is stored in `config.json` and editable from the UI settings panel.

```json
{
  "provider": "ollama",
  "api_key": "",
  "model": "mistral",
  "base_url": "http://localhost:11434/v1"
}
```

### Supported Providers

| Provider   | Base URL                                                   | Default Model                    |
|------------|------------------------------------------------------------|----------------------------------|
| Ollama     | `http://localhost:11434/v1`                                | `mistral` ✅ recommended          |
| OpenAI     | `https://api.openai.com/v1`                                | `gpt-4o`                         |
| Gemini     | `https://generativelanguage.googleapis.com/v1beta/openai`  | `gemini-1.5-pro`                 |
| Claude     | `https://api.anthropic.com/v1`                             | `claude-sonnet-4-6`              |
| OpenRouter | `https://openrouter.ai/api/v1`                             | `mistralai/mistral-7b-instruct`  |

> **Recommended:** Use Ollama with `mistral` locally — free, unlimited, and no rate limits.

---

## 🌐 API Reference

### `POST /run-pipeline`
Runs the full pipeline and streams stdout via SSE.
```json
{ "user_input": "a task management app with teams and deadlines" }
```
**Response:** `text/event-stream` ending with `data: [DONE]`

### `GET /output-json`
Returns `final_output.json` from the last pipeline run.

### `GET /get-config`
Returns current config (API key masked).

### `POST /save-config`
Saves provider/model/API key to `config.json`.

### `GET /presets`
Returns all built-in provider presets.

### `GET /health`
Returns `{ "status": "ok" }`.

---

## 📦 Dependencies

```
fastapi
uvicorn
openai
pydantic
python-dotenv
sqlalchemy
jinja2
python-multipart
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
