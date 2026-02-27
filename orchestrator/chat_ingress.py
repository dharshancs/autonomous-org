"""
chat_ingress.py — Converts founder messages into org tasks.

This is called by:
1. The frontend (when you type in the chat UI)
2. The email webhook (when you reply to an org email)

It finds the right agent, creates a task, and returns immediately.
The orchestrator picks up the task on its next 5-minute run.
For "instant" feel in the frontend, we also run the agent synchronously here.
"""
import os
import json
from datetime import datetime, timezone
from supabase import create_client, Client
from agent_runner import run_agent
from main import process_actions

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    return create_client(url, key)

def detect_agent(message: str, sb) -> dict | None:
    """Detect which agent the founder is addressing by name."""
    message_lower = message.lower()
    
    # Get all agent names from DB
    agents = sb.table("agents").select("*").eq("active", True).execute()
    
    for agent in (agents.data or []):
        name_lower = agent["name"].lower()
        # Check for "hey X", "X,", "@X", or just "X " at start
        if (f"hey {name_lower}" in message_lower or
            f"@{name_lower}" in message_lower or
            message_lower.startswith(f"{name_lower} ") or
            message_lower.startswith(f"{name_lower},") or
            f", {name_lower}" in message_lower):
            return agent
    
    # Default to ARIA (CEO)
    for agent in (agents.data or []):
        if agent["name"].upper() == "ARIA":
            return agent
    
    return agents.data[0] if agents.data else None

def handle_founder_message(message: str, session_id: str = "default") -> dict:
    """
    Process a message from the founder.
    Runs the agent synchronously for immediate response in the UI.
    Returns: {"agent": {...}, "response": "...", "actions_taken": [...]}
    """
    sb = get_supabase()
    
    # Detect which agent to address
    agent = detect_agent(message, sb)
    if not agent:
        return {"agent": None, "response": "No agents found. Run seed.sql first.", "actions_taken": []}
    
    # Store the conversation
    sb.table("conversations").insert({
        "session_id": session_id,
        "role": "user",
        "content": message,
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()
    
    # Build task for this agent
    # Get recent conversation context for this session
    recent_convos = sb.table("conversations").select(
        "role, content, agent_id"
    ).eq("session_id", session_id).order(
        "created_at", desc=True
    ).limit(10).execute()
    
    convo_context = ""
    if recent_convos.data:
        # Reverse to chronological order
        msgs = list(reversed(recent_convos.data))
        convo_context = "\n".join([
            f"{'Founder' if m['role']=='user' else 'Agent'}: {m['content'][:200]}"
            for m in msgs[:-1]  # exclude current message
        ])
    
    task = {
        "id": f"chat-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "assigned_to": agent["id"],
        "assigned_by": None,
        "parent_task_id": None,
        "description": f"Respond to founder message: {message}",
        "context": f"CONVERSATION HISTORY (recent):\n{convo_context}\n\nThis is a direct message from the founder. Respond conversationally and take any necessary actions.",
        "priority": 10,  # Founder messages are highest priority
        "status": "pending",
        "retry_count": 0,
        "last_error": None,
        "agents": agent
    }
    
    # Run agent synchronously for immediate response
    try:
        result = run_agent(sb, task)
        
        # Process all actions
        process_actions(sb, task, result.get("actions", []))
        
        response_text = result.get("response", "Done.")
        
        # Store agent response in conversation
        sb.table("conversations").insert({
            "session_id": session_id,
            "role": "assistant",
            "agent_id": agent["id"],
            "content": response_text,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        
        return {
            "agent": agent,
            "response": response_text,
            "thought": result.get("thought", ""),
            "actions_taken": result.get("actions", [])
        }
    
    except Exception as e:
        error_response = f"I hit an error processing that: {str(e)[:200]}. I've logged it and will self-correct."
        
        # Store error response
        sb.table("conversations").insert({
            "session_id": session_id,
            "role": "assistant",
            "agent_id": agent["id"],
            "content": error_response,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        
        return {
            "agent": agent,
            "response": error_response,
            "thought": str(e),
            "actions_taken": []
        }

if __name__ == "__main__":
    # Test from command line: python chat_ingress.py "Hey Riya, find me 3 SaaS ideas"
    import sys
    msg = " ".join(sys.argv[1:]) or "Hey ARIA, give me a status update"
    result = handle_founder_message(msg)
    print(f"\n{result['agent']['name']}: {result['response']}")
