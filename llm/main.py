import os
import json
from openai import OpenAI
from pydantic import BaseModel

from intents import get_intent_prompt
from architecture import get_architecture_prompt
from app_design import get_app_design_prompt
from validation import validate
from repair import repair
from codegen import run_codegen


# ── Called by server.py with a pre-built client + model string ────────────────

def call_llm_with_structure(
    prompt: str,
    schema_model: BaseModel,
    client: OpenAI,
    model: str,
    error_feedback: str = None,
):
    system_instruction = "You are an expert software architect executing structural JSON pipelines."

    if error_feedback:
        prompt += (
            f"\n\nCRITICAL: Your previous response failed validation with this error: "
            f"{error_feedback}. Please correct your JSON mapping."
        )

    try:
        response = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user",   "content": prompt},
            ],
            response_format=schema_model,
        )

        if hasattr(response, "usage") and response.usage:
            print(
                f"📊 [Token Usage] Prompt: {response.usage.prompt_tokens} | "
                f"Completion: {response.usage.completion_tokens} | "
                f"Total: {response.usage.total_tokens}"
            )
        else:
            print("📊 [Token Usage] Metadata not returned by provider.")

        return response.choices[0].message.parsed

    except Exception as e:
        print(f"⚠️  Validation error caught: {e}. Initiating self-repair attempt...")
        return call_llm_with_structure(
            prompt, schema_model, client, model, error_feedback=str(e)
        )


def serialize_pipeline(pipeline_memory: dict) -> dict:
    """Convert Pydantic models in pipeline_memory to plain dicts."""
    serializable = {}
    for key, value in pipeline_memory.items():
        if hasattr(value, "model_dump"):
            serializable[key] = value.model_dump()
        elif hasattr(value, "dict"):
            serializable[key] = value.dict()
        else:
            serializable[key] = value
    return serializable


def save_pipeline_to_json(pipeline_memory: dict, output_path: str = "final_output.json"):
    serializable = serialize_pipeline(pipeline_memory)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
    print(f"✅ Saved to {output_path}")


def run_development_pipeline(user_input: str, client: OpenAI, model: str):
    
    pipeline_memory = {
        "user_input": user_input,
        "intent": None,
        "architecture": None,
        "app_design": None,
    }

    print("\n--- STAGE 1: Extracting User Intent ---")
    prompt, schema = get_intent_prompt(pipeline_memory["user_input"])
    pipeline_memory["intent"] = call_llm_with_structure(prompt, schema, client, model)
    print(
        f"Extracted Intent: {pipeline_memory['intent'].intent_name} "
        f"with goal: {pipeline_memory['intent'].user_goal}"
    )
    print("Validated Intent Object saved to pipeline memory.")

    print("\n--- STAGE 2: Generating Architecture Layout ---")
    prompt, schema = get_architecture_prompt(pipeline_memory["intent"])
    pipeline_memory["architecture"] = call_llm_with_structure(prompt, schema, client, model)
    print(f"Generated Architecture: {pipeline_memory['architecture'].project_name}")
    print("Validated Architecture Object saved to pipeline memory.")

    print("\n--- STAGE 3: Producing Final Application Design ---")
    prompt, schema = get_app_design_prompt(
        pipeline_memory["intent"], pipeline_memory["architecture"]
    )
    pipeline_memory["app_design"] = call_llm_with_structure(prompt, schema, client, model)
    print(f"Generated App Design: {pipeline_memory['app_design']}")
    print("Validated App Design Object saved to pipeline memory.")

    serialized = serialize_pipeline(pipeline_memory)

    print("\n--- STAGE 4: Validating Pipeline Memory ---")
    issues = validate(serialized, client, model)

    if not issues:
        print("✅ No issues found — pipeline is clean")
    else:
        print(f"\n⚠  Found {len(issues)} issue(s):\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. [{issue.get('type', '?')}] {issue.get('target', '?')} — {issue.get('issue', '')}")

        # ── STAGE 5: Repair ───────────────────────────────────────────────────────
        print("\n--- STAGE 5: Repairing Pipeline Memory ---")
        serialized = repair(serialized, issues, client, "mistral")

        # ── STAGE 6: Re-validate ──────────────────────────────────────────────────
        print("\n--- STAGE 6: Re-Validating After Repair ---")
        remaining = validate(serialized, client, "mistral")

        if not remaining:
            print("✅ All issues resolved — pipeline is clean")
        else:
            print(f"\n⚠  {len(remaining)} issue(s) still remain after repair:\n")
            for i, issue in enumerate(remaining, 1):
                print(f"  {i}. [{issue.get('type', '?')}] {issue.get('target', '?')} — {issue.get('issue', '')}")

    return serialized


# ── Standalone entry point (bypasses UI, uses config.json) ───────────────────
if __name__ == "__main__":
    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)

    _client = OpenAI(
        api_key=cfg.get("api_key") or "ollama",
        base_url=cfg.get("base_url", "http://localhost:11434/v1"),
    )
    _model = cfg.get("model", "mistral")

    user_idea = "give me an application for video streaming with user login, video upload, comments, and likes."
    final_state = run_development_pipeline(user_idea, _client, _model)

    save_pipeline_to_json(final_state, "final_output.json")
    run_codegen("final_output.json")

    print("\n================ PIPELINE SUCCESS ================")