"""
main.py — The Org's Heartbeat

This runs every 5 minutes on GitHub Actions.
It checks for pending tasks, runs the right agent, processes actions, self-heals on errors.
This is the entire org operating autonomously.
"""
import os
import json
import sys
from datetime import datetime, timezone
from supabase import create_client, Client
from agent_runner import run_agent

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in GitHub Secrets.")
    return create_client(url, key)

def get_agent_id(sb, name: str) -> str | None:
    """Get agent UUID by name (case-insensitive)."""
    result = sb.table("agents").select("id").ilike("name", name).eq("active", True).execute()
    return result.data[0]["id"] if result.data else None

def process_actions(sb, task: dict, actions: list):
    """Process all actions an agent wants to take."""
    
    for action in actions:
        atype = action.get("type", "")
        
        try:
            if atype == "create_task":
                agent_id = get_agent_id(sb, action["assigned_to"])
                if agent_id:
                    sb.table("tasks").insert({
                        "assigned_to": agent_id,
                        "assigned_by": task["assigned_to"],
                        "parent_task_id": task["id"],
                        "description": action["description"],
                        "context": action.get("context", ""),
                        "priority": action.get("priority", 5),
                        "status": "pending"
                    }).execute()
                    print(f"    → Task created for {action['assigned_to']}: {action['description'][:60]}")
                    sb.table("org_messages").insert({
                        "from_agent": task["assigned_to"],
                        "to_agent": agent_id,
                        "task_id": task["id"],
                        "type": "delegation",
                        "content": f"Delegated task: {action['description']}"
                    }).execute()
                else:
                    print(f"    ⚠ Agent not found: {action['assigned_to']}. Skipping task creation.")
            
            elif atype == "store_memory":
                sb.table("memory").upsert({
                    "key": action["key"],
                    "value": str(action["value"]),
                    "category": action.get("category", "general"),
                    "updated_by": task["assigned_to"],
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).execute()
                print(f"    → Memory stored: {action['key']}")
            
            elif atype == "send_email":
                from tools.email_tool import send_email
                recipient = action.get("to") or os.environ.get("FOUNDER_EMAIL")
                if recipient:
                    send_email(
                        to=recipient,
                        subject=action.get("subject", "Update from your org"),
                        body=action.get("body", "")
                    )
                    print(f"    → Email sent: {action.get('subject','')[:50]}")
                else:
                    print("    ⚠ No recipient for email. Set FOUNDER_EMAIL in secrets.")
            
            elif atype == "log_decision":
                sb.table("decisions").insert({
                    "made_by": task["assigned_to"],
                    "description": action["description"],
                    "reasoning": action.get("reasoning", ""),
                    "task_id": task["id"],
                    "needs_approval": action.get("needs_approval", False),
                    "approved_by_human": False
                }).execute()
                sb.table("org_messages").insert({
                    "from_agent": task["assigned_to"],
                    "to_agent": None,
                    "task_id": task["id"],
                    "type": "decision",
                    "content": action["description"]
                }).execute()
                print(f"    → Decision logged: {action['description'][:60]}")
            
            elif atype == "add_agent":
                # Self-expanding: org adds its own team members
                existing = sb.table("agents").select("id").ilike(
                    "name", action["name"]
                ).execute()
                if not existing.data:
                    sb.table("agents").insert({
                        "name": action["name"],
                        "role": action.get("role", "Specialist"),
                        "emoji": action.get("emoji", "🤖"),
                        "color": action.get("color", "#6366f1"),
                        "system_prompt": action["system_prompt"],
                        "active": True
                    }).execute()
                    print(f"    → NEW AGENT CREATED: {action['name']} ({action.get('role','')})")
                    
                    # Email founder about new team member
                    founder_email = os.environ.get("FOUNDER_EMAIL")
                    if founder_email:
                        from tools.email_tool import send_email
                        send_email(
                            to=founder_email,
                            subject=f"🆕 New team member joined: {action['name']}",
                            body=f"The org added a new agent to the team:\n\nName: {action['name']}\nRole: {action.get('role','')}\n\nThis was done automatically to handle a capability gap.\nNo action needed from you."
                        )
            
            elif atype == "add_integration":
                sb.table("integrations").upsert({
                    "name": action["name"],
                    "type": action.get("type", "tool"),
                    "status": "active",
                    "config": action.get("config", {}),
                    "notes": action.get("notes", ""),
                    "added_by": task["assigned_to"]
                }).execute()
                print(f"    → Integration added: {action['name']}")
            
            elif atype == "update_product":
                update_data = {k: v for k, v in action.items() 
                               if k not in ["type", "name"] and v is not None}
                update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                result = sb.table("products").update(update_data).eq(
                    "name", action["name"]
                ).execute()
                if not result.data:
                    # Product doesn't exist, create it
                    sb.table("products").insert({
                        "name": action["name"],
                        **{k: v for k, v in update_data.items() if k != "updated_at"}
                    }).execute()
                print(f"    → Product updated: {action['name']}")
            
            elif atype == "create_product":
                existing = sb.table("products").select("id").eq(
                    "name", action["name"]
                ).execute()
                if not existing.data:
                    sb.table("products").insert({
                        "name": action["name"],
                        "description": action.get("description", ""),
                        "target_user": action.get("target_user", ""),
                        "status": action.get("status", "ideation")
                    }).execute()
                    print(f"    → Product created: {action['name']}")
        
        except Exception as e:
            print(f"    ⚠ Action '{atype}' failed: {e}")
            # Log but don't crash — other actions should still run

def handle_task_error(sb, task: dict, error_msg: str):
    """Self-healing: retry with context, escalate after 3 failures."""
    
    attempts = task.get("retry_count", 0)
    
    # Log the error
    sb.table("error_log").insert({
        "task_id": task["id"],
        "agent_id": task.get("assigned_to"),
        "error": error_msg,
        "attempt": attempts + 1,
        "resolved": False,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).execute()
    
    print(f"  ⚡ Self-healing attempt {attempts + 1}/3 for task {task['id'][:8]}...")
    
    if attempts < 3:
        # Reset to pending with error context — different approach on retry
        sb.table("tasks").update({
            "status": "pending",
            "retry_count": attempts + 1,
            "last_error": error_msg[:1000],
            "started_at": None,
            "context": (task.get("context") or "") + f"\n\n[RETRY {attempts+1}] Previous attempt failed: {error_msg[:300]}. Try a completely different approach."
        }).eq("id", task["id"]).execute()
        print(f"  → Task re-queued for retry {attempts + 1}")
    
    else:
        # 3 failures — escalate to human
        sb.table("tasks").update({
            "status": "failed",
            "last_error": error_msg[:1000],
            "completed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", task["id"]).execute()
        
        founder_email = os.environ.get("FOUNDER_EMAIL")
        if founder_email:
            try:
                from tools.email_tool import send_email
                # Get agent name for context
                agent_name = "Unknown"
                if task.get("assigned_to"):
                    agent = sb.table("agents").select("name").eq(
                        "id", task["assigned_to"]
                    ).execute()
                    if agent.data:
                        agent_name = agent.data[0]["name"]
                
                send_email(
                    to=founder_email,
                    subject=f"🔴 Task needs your attention — {agent_name}",
                    body=f"""A task failed after 3 automatic retry attempts and needs your input.

Agent: {agent_name}
Task: {task['description']}
Last Error: {error_msg[:500]}
Task ID: {task['id']}

What to do:
1. Check the task in your Supabase dashboard
2. Reply to this email with instructions if you want it retried differently
3. Or just ignore it if it's not critical

Your org is still running normally — this task has been paused.
"""
                )
                print(f"  → Escalation email sent to founder")
            except Exception as e:
                print(f"  ⚠ Could not send escalation email: {e}")
        else:
            print("  ⚠ Task failed 3 times but no FOUNDER_EMAIL set for escalation")

def run_orchestrator():
    sb = get_supabase()

    max_cycles = 10  # safety guard
    cycle = 0

    while cycle < max_cycles:
        cycle += 1

        result = sb.table("tasks").select(
            "*, agents!tasks_assigned_to_fkey(*)"
        ).eq("status", "pending") \
         .order("priority", desc=True) \
         .order("created_at") \
         .limit(20).execute()

        tasks = result.data or []

        if not tasks:
            break

        print(f"Cycle {cycle}: {len(tasks)} task(s)")

        for task in tasks:
            task_id = task["id"]

            sb.table("tasks").update({
                "status": "in_progress",
                "started_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", task_id).execute()

            try:
                result = run_agent(sb, task)
                process_actions(sb, task, result.get("actions", []))

                sb.table("tasks").update({
                    "status": "complete",
                    "output": result.get("response", ""),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", task_id).execute()

            except Exception as e:
                handle_task_error(sb, task, str(e))

    print("✓ Queue drained.")
if __name__ == "__main__":
    run_orchestrator()
