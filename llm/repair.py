import json
import re


# ── Repair strategies per issue type ─────────────────────────────────────────

REPAIR_PROMPTS = {

    "MISSING_KEY": """
You are a Senior Software Architect.
The section below is missing required keys/fields.
Add ONLY the missing fields. Keep everything else exactly as-is.
Return only the repaired JSON for this section. Start with {{ end with }}.
No markdown, no explanation.

Section key: {section_key}
Issue: {issue}
Target: {target}

Section JSON:
{section_json}
""",

    "HALLUCINATED_FIELD": """
You are a Senior Software Architect.
The section below contains fields that do not belong in a {app_type} application.
Remove ONLY the hallucinated fields described in the issue.
Keep everything else exactly as-is.
Return only the repaired JSON. Start with {{ end with }}.
No markdown, no explanation.

Section key: {section_key}
Issue: {issue}
Target: {target}

Section JSON:
{section_json}
""",

    "SCHEMA_MISMATCH": """
You are a Senior Software Architect.
There is a naming or structural mismatch between sections.
Fix the mismatch described in the issue by updating this section to be consistent.
Return only the repaired JSON for this section. Start with {{ end with }}.
No markdown, no explanation.

Section key: {section_key}
Issue: {issue}
Target: {target}

Section JSON:
{section_json}
""",

    "LOGICAL_INCONSISTENCY": """
You are a Senior Software Architect.
The section below has a logical inconsistency.
Fix only the described inconsistency. Do not restructure anything else.
Return only the repaired JSON for this section. Start with {{ end with }}.
No markdown, no explanation.

Section key: {section_key}
Issue: {issue}
Target: {target}

Section JSON:
{section_json}
""",

    "INVALID_JSON": """
You are a Senior Software Architect.
The JSON section below is malformed or incomplete.
Reconstruct it as valid JSON, inferring missing closing brackets/braces.
Preserve all parseable content. Do not invent new content.
Return only valid JSON. Start with {{ end with }}.
No markdown, no explanation.

Section key: {section_key}
Issue: {issue}

Raw broken content:
{section_json}
"""
}


# ── Bracket auto-closer ───────────────────────────────────────────────────────

def _fix_truncated_json(raw: str) -> str:
    """Close unclosed brackets so json.loads can parse truncated output."""
    stack = []
    in_string = False
    escape = False

    for ch in raw:
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append('}' if ch == '{' else ']')
        elif ch in '}]' and stack and stack[-1] == ch:
            stack.pop()

    return raw.rstrip().rstrip(',') + ''.join(reversed(stack))


def _extract_json(raw: str) -> str:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    else:
        start = raw.find("{")
        end   = raw.rfind("}")
        candidate = raw[start:end + 1] if start != -1 and end > start else raw

    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        return _fix_truncated_json(candidate)


# ── Deep merge ────────────────────────────────────────────────────────────────

def _deep_merge(base: dict, patch: dict) -> dict:
    result = dict(base)
    for key, val in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        elif key in result and isinstance(result[key], list) and isinstance(val, list):
            existing_names = {
                item.get("name"): i
                for i, item in enumerate(result[key])
                if isinstance(item, dict) and "name" in item
            }
            merged_list = list(result[key])
            for item in val:
                name = item.get("name") if isinstance(item, dict) else None
                if name and name in existing_names:
                    merged_list[existing_names[name]] = _deep_merge(
                        merged_list[existing_names[name]], item
                    )
                else:
                    merged_list.append(item)
            result[key] = merged_list
        else:
            result[key] = val
    return result


# ── Extract only the broken subsection ───────────────────────────────────────

def _extract_subsection(section: dict, target: str) -> dict:
    """
    Pull out only the service/entity named in target so we send
    the smallest possible JSON to the LLM.
    """
    for list_key in ("services", "entities", "endpoints"):
        items = section.get(list_key, [])
        for item in items:
            if isinstance(item, dict) and item.get("name", "") == target:
                return {list_key: [item]}
    return section  # fallback: full section


# ── Main repair function ──────────────────────────────────────────────────────

def repair(
    pipeline_memory: dict,
    issues: list[dict],          # now receives structured issue objects
    client,
    model: str,
    retries: int = 3,
) -> dict:
    print("\n--- REPAIR: Targeted repair by issue type ---")

    app_type = pipeline_memory.get("intent", {}).get("intent_name", "general application") \
        if isinstance(pipeline_memory.get("intent"), dict) else "general application"

    result = dict(pipeline_memory)

    for issue_obj in issues:
        # Support both old string format and new object format
        if isinstance(issue_obj, str):
            issue_obj = {
                "type": "LOGICAL_INCONSISTENCY",
                "section": "architecture",
                "target": "unknown",
                "issue": issue_obj
            }

        issue_type = issue_obj.get("type", "LOGICAL_INCONSISTENCY")
        section_key = issue_obj.get("section", "architecture")
        target      = issue_obj.get("target", "")
        issue_text  = issue_obj.get("issue", "")

        print(f"\n  [{issue_type}] {section_key} → {target}")
        print(f"  Issue: {issue_text}")

        if section_key not in result or not isinstance(result[section_key], dict):
            print(f"  ⚠  Section '{section_key}' not found — skipping")
            continue

        # Extract the smallest relevant subsection
        subsection = _extract_subsection(result[section_key], target)

        prompt_template = REPAIR_PROMPTS.get(issue_type, REPAIR_PROMPTS["LOGICAL_INCONSISTENCY"])
        prompt = prompt_template.format(
            section_key=section_key,
            issue=issue_text,
            target=target,
            app_type=app_type,
            section_json=json.dumps(subsection, indent=2, default=str)
        )

        success = False
        for attempt in range(1, retries + 1):
            print(f"  Attempt {attempt}/{retries}...")
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Return ONLY the minimal repaired JSON. "
                                "Do NOT reproduce unchanged fields. "
                                "Start with { and end with }. No markdown."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,
                    max_tokens=1500,
                )

                raw     = response.choices[0].message.content.strip()
                cleaned = _extract_json(raw)
                patched = json.loads(cleaned)

                # Merge patch back into the section
                result[section_key] = _deep_merge(result[section_key], patched)
                print(f"  ✅ Fixed [{issue_type}] in '{section_key}'")
                success = True
                break

            except json.JSONDecodeError as e:
                print(f"  ⚠  Invalid JSON on attempt {attempt}: {e}")
            except Exception as e:
                print(f"  ⚠  Error on attempt {attempt}: {e}")

        if not success:
            print(f"  ❌ Could not fix [{issue_type}] → {target} — skipping")

    return result