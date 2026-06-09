import json
import re

VALIDATION_PROMPT = """
You are a Senior Software Architect reviewing a software pipeline JSON.

APPLICATION CONTEXT:
- App type: {app_type}
- Only flag issues relevant to this application type

You must detect ALL of the following problem categories. Tag each issue with its type.

1. INVALID_JSON — malformed, truncated, or unparseable sections
2. MISSING_KEY — required fields absent from an entity/service/schema
3. HALLUCINATED_FIELD — fields that make no sense for this app type
   (e.g. "cart_id" in a CRM, "stripe_payment" in an internal tool)
4. SCHEMA_MISMATCH — type or structural conflicts between sections
   (e.g. architecture declares "UserService" but app_design calls it "AccountService")
5. LOGICAL_INCONSISTENCY — contradictions in the design
   (e.g. endpoint marked Public but requires Admin role,
    service depends_on a service that doesn't exist,
    entity has foreign key to undefined entity)

For each issue, return an object with:
- "type": one of the 5 categories above
- "section": which top-level key it lives in (intent/architecture/app_design)
- "target": the specific service/entity/field name involved
- "issue": a precise description referencing actual names from the JSON

Return ONLY a valid JSON array. No markdown. No preamble.
Empty array if no issues: []

Example output:
[
  {{
    "type": "MISSING_KEY",
    "section": "architecture",
    "target": "DashboardService",
    "issue": "DashboardService has no foreign key relationship defined with UserService"
  }},
  {{
    "type": "LOGICAL_INCONSISTENCY",
    "section": "app_design",
    "target": "GET /orders",
    "issue": "GET /orders endpoint has authLevel 'Public' but OrderService requires authentication"
  }},
  {{
    "type": "HALLUCINATED_FIELD",
    "section": "architecture",
    "target": "ContactService",
    "issue": "ContactService defines 'cart_items' field which has no relevance to a CRM application"
  }}
]

Project JSON:
{project_json}
"""


def validate(pipeline_memory: dict, client, model: str) -> list[dict]:
    print("\n--- VALIDATION: Sending pipeline to LLM for review ---")

    app_type = "general application"
    intent = pipeline_memory.get("intent", {})
    if isinstance(intent, dict):
        app_type = intent.get("intent_name", app_type)

    prompt = VALIDATION_PROMPT.format(
        app_type=app_type,
        project_json=json.dumps(pipeline_memory, indent=2, default=str)
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a Senior Software Architect. Return only a JSON array of issue objects. No markdown."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        issues = json.loads(raw)
        if not isinstance(issues, list):
            print("⚠  LLM returned non-list — treating as no issues")
            return []

        # Normalize: support both old string format and new object format
        normalized = []
        for item in issues:
            if isinstance(item, str):
                normalized.append({
                    "type": "LOGICAL_INCONSISTENCY",
                    "section": "architecture",
                    "target": "unknown",
                    "issue": item
                })
            elif isinstance(item, dict) and "issue" in item:
                normalized.append(item)

        return normalized

    except json.JSONDecodeError as e:
        print(f"⚠  Could not parse validation response: {e}")
        print(f"   Raw: {raw[:300]}")
        return []