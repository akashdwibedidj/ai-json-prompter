from schemas import IntentSchema


# def get_intent_instructions():
#     return "STAGE 1 - INTENT ANALYSIS: Analyze the user request. Identify the core intent, application goal, and target audience."


def get_intent_prompt(user_input: str):
    prompt = f"Analyze this user request for a new software application: '{user_input}'. Identify the core intent, goal, and target audience."
    return prompt, IntentSchema
