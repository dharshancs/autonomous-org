"""
llm.py — GitHub Models client
Free LLMs via your GitHub token. No credit card. No limits that matter.

Available models (all free):
- gpt-4o-mini         → Fast, great for most agent tasks
- Meta-Llama-3.3-70B-Instruct → Powerful open-source, great for reasoning
- Phi-4               → Microsoft's small but smart model
- Mistral-small-2503  → Fast European model
"""
import os
import json
from openai import OpenAI

MODELS = {
    "fast":      "gpt-4o-mini",
    "smart":     "Meta-Llama-3.3-70B-Instruct",
    "code":      "gpt-4o-mini",
    "reasoning": "Meta-Llama-3.3-70B-Instruct",
    "default":   "gpt-4o-mini",
}

def get_client():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not set. GitHub Models requires a GitHub token.")
    return OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=token,
    )

def call_llm(messages: list, model: str = None, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    """
    Call GitHub Models API. Completely free.
    Falls back through models if one fails.
    """
    if model is None:
        model = os.environ.get("DEFAULT_MODEL", MODELS["default"])

    fallback_chain = [model, "gpt-4o-mini", "Meta-Llama-3.3-70B-Instruct", "Phi-4"]
    seen = set()
    
    for m in fallback_chain:
        if m in seen:
            continue
        seen.add(m)
        try:
            client = get_client()
            response = client.chat.completions.create(
                model=m,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if content:
                return content
        except Exception as e:
            print(f"[LLM] Model {m} failed: {e}. Trying next...")
            continue
    
    raise Exception("All LLM models failed. Check GITHUB_TOKEN and network.")

def call_llm_json(messages: list, model: str = None, max_retries: int = 3) -> dict:
    """
    Call LLM and guarantee a JSON response.
    Retries with correction prompt if JSON parsing fails.
    """
    msgs = list(messages)
    
    for attempt in range(max_retries):
        try:
            raw = call_llm(msgs, model=model)
            
            # Strip markdown code blocks if present
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            return json.loads(cleaned)
            
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                # Self-heal: ask the model to fix its output
                msgs.append({"role": "assistant", "content": raw})
                msgs.append({
                    "role": "user",
                    "content": f"Your response was not valid JSON. Error: {e}. Respond with ONLY valid JSON, no markdown, no explanation, just the JSON object."
                })
            else:
                raise Exception(f"Failed to get valid JSON after {max_retries} attempts. Last raw: {raw[:200]}")

def choose_model(task_type: str) -> str:
    """Pick the best free model for the task type."""
    return MODELS.get(task_type, MODELS["default"])
