from schemas import AppDesignSchema, IntentSchema, ArchitectureSchema

import re
import json


def clean_and_parse(raw: str, schema):
    raw = raw.strip()
    raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'```$', '', raw, flags=re.MULTILINE)
    raw = raw.strip()
    data = json.loads(raw)
    return schema(**data)


def get_app_design_prompt(intent_data: IntentSchema, arch_data: ArchitectureSchema):
    prompt = f"""
    Generate the technical configuration specifications based on the historical design chain below.
    
    [STAGE 1: INTENT]
    Name: {intent_data.intent_name}
    Goal: {intent_data.user_goal}
    
    [STAGE 2: ARCHITECTURE]
    Style: {arch_data.architecture_pattern}
    Tech Stack: {', '.join(f"{k}: {v}" for k, v in arch_data.tech_stack.items())}
    Components: {', '.join(s.name for s in arch_data.services)}
    
    Task: Respond with ONLY a valid JSON object — no markdown, no explanation, no code fences.
    The JSON must contain ALL of these keys:
    
    - "entities": list of objects with "name", "description", "attributes" (list), "relationships" (list)
    - "roles": list of objects with "name", "permissions" (list), "description"
    - "flows": list of objects with "name", "steps" (list), "actors" (list)
    - "ui_config": dict describing pages, components, themes
    - "api_config": dict describing base_url, auth headers, etc.
    - "api_endpoints": list of objects with "method", "route", "name", "authLevel"
    - "db_schema": dict describing tables/collections and their fields
    - "auth_rules": dict describing roles, access rules, token strategy
    
    Do NOT return plain text. Return ONLY the raw JSON object.
    """
    return prompt, AppDesignSchema