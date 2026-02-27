"""
agent_runner.py — Runs any agent on any task with full org context.

This is the core engine. For every task:
1. Load the agent's personality/prompt from the database
2. Build full context: org memory, recent decisions, conversation history, parent tasks
3. Call the LLM with everything
4. Parse the structured response
5. Return actions + response

Self-healing is handled at the orchestrator level (retries with error context).
"""
import json
import os
from datetime import datetime, timezone
from llm import call_llm_json, choose_model

# ── META INSTRUCTIONS ─────────────────────────────────────────────────────────
# These are injected into EVERY agent's system prompt, on top of their own personality.
# This is what gives them the ability to delegate, create agents, etc.
META_INSTRUCTIONS = """
== AUTONOMOUS ORG OPERATING INSTRUCTIONS ==

You are an AI agent in a fully autonomous SaaS organization.
You receive tasks, complete them, and can delegate sub-tasks to other agents.

ALWAYS respond with a single valid JSON object in this exact structure:
{
  "thought": "Your internal reasoning about this task",
  "actions": [...],
  "response": "Natural language summary of what you did and what happens next"
}

AVAILABLE ACTIONS (include any combination in the "actions" array):

1. Create a task for another agent:
   {"type": "create_task", "assigned_to": "<agent name>", "description": "<what to do>", "context": "<relevant info>", "priority": <1-10>}

2. Store something in org memory:
   {"type": "store_memory", "key": "<memory key>", "value": "<value>", "category": "<config|strategy|engineering|finance|ops>"}

3. Send an email to the founder:
   {"type": "send_email", "subject": "<subject>", "body": "<email body>"}

4. Log a decision:
   {"type": "log_decision", "description": "<what was decided>", "reasoning": "<why>", "needs_approval": <true/false>}

5. Create a new specialized agent (if capability is missing):
   {"type": "add_agent", "name": "<Name>", "role": "<role title>", "emoji": "<emoji>", "color": "<hex>", "system_prompt": "<full personality and instructions>"}

6. Add a new integration:
   {"type": "add_integration", "name": "<tool name>", "type": "<llm|email|analytics|payments|comms>", "config": {...}, "notes": "<setup notes>"}

7. Update a product:
   {"type": "update_product", "name": "<product name>", "status": "<ideation|planning|building|testing|live|paused>", "repo_url": "<url>", "live_url": "<url>"}

8. Create a new product record:
   {"type": "create_product", "name": "<name>", "description": "<desc>", "target_user": "<who>", "status": "ideation"}

SELF-HEALING RULES:
- If something is unclear, make a reasonable assumption and note it in your thought
- If you are retrying after an error, try a completely different approach
- Never refuse a task — find a way or create an agent who can do it
- If a tool or integration is missing, add it via add_integration action

DELEGATION RULES:
- Break complex tasks into sub-tasks assigned to the right agent
- Include all context the receiving agent needs (they don't have memory of your thought process)
- Use priority 8-10 for urgent/blocking tasks, 5-7 for normal, 1-4 for background work
"""

def build_context(sb, task: dict) -> str:
    """Build the full context string for an agent to work with."""
    
    # 1. Org memory
    memories = sb.table("memory").select("key, value, category").execute()
    mem_by_cat = {}
    for m in (memories.data or []):
        cat = m.get("category", "general")
        if cat not in mem_by_cat:
            mem_by_cat[cat] = []
        mem_by_cat[cat].append(f"  {m['key']}: {m['value']}")
    
    memory_str = ""
    for cat, items in mem_by_cat.items():
        memory_str += f"\n[{cat.upper()}]\n" + "\n".join(items)
    
    # 2. Recent decisions (last 15)
    decisions = sb.table("decisions").select("description, created_at").order(
        "created_at", desc=True).limit(15).execute()
    decisions_str = "\n".join([
        f"  • {d['description']}" for d in (decisions.data or [])
    ]) or "  No decisions yet."
    
    # 3. Active products
    products = sb.table("products").select("name, status, description").execute()
    products_str = "\n".join([
        f"  • {p['name']} [{p['status']}] — {p.get('description','')}"
        for p in (products.data or [])
    ]) or "  No products yet."
    
    # 4. Recent task completions (context on what's been done)
    recent_tasks = sb.table("tasks").select(
        "description, output, completed_at"
    ).eq("status", "complete").order(
        "completed_at", desc=True
    ).limit(10).execute()
    
    recent_str = "\n".join([
        f"  ✓ {t['description'][:80]}" for t in (recent_tasks.data or [])
    ]) or "  No completed tasks yet."
    
    # 5. Parent task context (if this is a sub-task)
    parent_str = ""
    if task.get("parent_task_id"):
        parent = sb.table("tasks").select(
            "description, context, output"
        ).eq("id", task["parent_task_id"]).execute()
        if parent.data:
            p = parent.data[0]
            parent_str = f"""
PARENT TASK (this is a sub-task of):
  Description: {p['description']}
  Context: {p.get('context', 'none')}
  Output so far: {p.get('output', 'none')}
"""
    
    # 6. Retry context
    retry_str = ""
    if task.get("retry_count", 0) > 0:
        retry_str = f"""
⚠️ RETRY ATTEMPT {task['retry_count'] + 1}:
Previous attempt failed with: {task.get('last_error', 'unknown error')}
Try a completely different approach this time.
"""
    
    return f"""
== ORG MEMORY =={memory_str}

== RECENT DECISIONS ==
{decisions_str}

== ACTIVE PRODUCTS ==
{products_str}

== RECENTLY COMPLETED TASKS ==
{recent_str}
{parent_str}
{retry_str}
== YOUR CURRENT TASK ==
{task['description']}

ADDITIONAL CONTEXT PROVIDED:
{task.get('context', 'No additional context.')}
"""

def run_agent(sb, task: dict) -> dict:
    """
    Run an agent on a task. Returns the parsed response dict.
    
    The response always has:
    - thought: str
    - actions: list
    - response: str
    """
    
    # Load agent data
    agent_data = task.get("agents") or {}
    if not agent_data and task.get("assigned_to"):
        agent_row = sb.table("agents").select("*").eq(
            "id", task["assigned_to"]
        ).execute()
        agent_data = agent_row.data[0] if agent_row.data else {}
    
    agent_name = agent_data.get("name", "Unknown Agent")
    agent_prompt = agent_data.get("system_prompt", "You are a helpful AI agent.")
    
    # Get list of all available agents for delegation
    all_agents = sb.table("agents").select("name, role").eq("active", True).execute()
    agents_roster = "\n".join([
        f"  • {a['name']}: {a['role']}" for a in (all_agents.data or [])
    ])
    
    # Build full context
    context = build_context(sb, task)
    
    # Compose messages
    messages = [
        {
            "role": "system",
            "content": f"{META_INSTRUCTIONS}\n\n== YOUR IDENTITY AND ROLE ==\n{agent_prompt}\n\n== AGENTS YOU CAN DELEGATE TO ==\n{agents_roster}"
        },
        {
            "role": "user",
            "content": context
        }
    ]
    
    # Determine model based on task type
    description_lower = task.get("description", "").lower()
    if any(w in description_lower for w in ["build", "code", "develop", "implement", "schema"]):
        model = "gpt-4o-mini"  # Strong at code
    elif any(w in description_lower for w in ["research", "analyze", "plan", "strategy", "decide"]):
        model = "Meta-Llama-3.3-70B-Instruct"  # Strong at reasoning
    else:
        model = None  # Use default
    
    print(f"  [{agent_name}] Running task: {task['description'][:70]}...")
    
    result = call_llm_json(messages, model=model)
    # Log internal reasoning (summary)
    try:
        sb.table("org_messages").insert({
            "from_agent": task.get("assigned_to"),
            "to_agent": None,
            "task_id": task.get("id"),
            "type": "thought",
            "content": result.get("thought", "")[:1000]
        }).execute()
    except:
        pass
    
    # Ensure required keys exist
    if "actions" not in result:
        result["actions"] = []
    if "response" not in result:
        result["response"] = result.get("thought", "Task processed.")
    if "thought" not in result:
        result["thought"] = "No thought logged."
    
    print(f"  [{agent_name}] Done. {len(result['actions'])} actions. Response: {result['response'][:80]}...")
    
    return result
