from schemas import ArchitectureSchema, IntentSchema


# def get_architecture_instructions():
#     return "STAGE 2 - BLUEPRINT DESIGN: Based on the intent, goal, and audience identified in Stage 1, design a software architecture layout including style, tech stack, entities, access roles, data flows, and services."



def get_architecture_prompt(intent_data: IntentSchema):
    # MEMORY PASSING: We insert the validated intent from the previous file into this prompt
    prompt = f"""
    Based on the following validated user intent, design a software architecture layout:
    Intent: {intent_data.intent_name}
    Goal: {intent_data.user_goal}
    Audience: {intent_data.target_audience}
    For each service, include an "endpoints" list with objects containing:
    - method: GET/POST/PUT/DELETE
    - route: the URL path (e.g. /api/users)
    - name: short description
    - authLevel: Public or Authenticated
    Provide an architecture style, tech stack, and a list of core system components.
    """
    return prompt, ArchitectureSchema
