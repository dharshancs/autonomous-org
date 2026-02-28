"""
agent_runner.py — Agents that take REAL ACTIONS using tools.
"""
import os
import json
from datetime import datetime, timezone
from llm import call_llm_json

META = """
== AUTONOMOUS ORG — AGENT OPERATING SYSTEM ==

You are an AI agent in a fully autonomous SaaS organization.
You do NOT just respond with words. You TAKE REAL ACTIONS using tools.
Every task must result in ACTUAL WORK: code written, pages deployed, data researched, emails sent.

RESPOND with this exact JSON:
{
  "thought": "What I understand and my approach",
  "tool_calls": [
    {"tool": "search|github|vercel|code", "action": "method_name", "params": {...}}
  ],
  "org_actions": [
    {"type": "create_task", "assigned_to": "AgentName", "description": "...", "context": "...", "priority": 7},
    {"type": "store_memory", "key": "...", "value": "...", "category": "config|strategy|engineering|finance|ops"},
    {"type": "send_email", "subject": "...", "body": "..."},
    {"type": "log_decision", "description": "...", "reasoning": "..."},
    {"type": "add_agent", "name": "...", "role": "...", "emoji": "...", "color": "#hex", "system_prompt": "..."},
    {"type": "update_product", "name": "...", "status": "ideation|planning|building|testing|live", "repo_url": "...", "live_url": "..."},
    {"type": "create_product", "name": "...", "description": "...", "target_user": "...", "status": "ideation"}
  ],
  "response": "Plain English summary of what was actually done"
}

AVAILABLE TOOLS:

[search] Real web search — no API key needed
  search.search(query, max_results) → [{title, url, snippet}]
  search.fetch_page(url, max_chars) → text
  search.research_saas_opportunity(topic) → {reddit_signals, competitors, demand_signals}

[github] Write real code to GitHub repos — uses GITHUB_TOKEN (auto-provided)
  github.create_repo(name, description, private=False) → {success, repo_url, name}
  github.write_file(repo, path, content, message) → {success, path}
  github.write_multiple_files(repo, files=[{path,content}], commit_message) → {success, files_written}
  github.read_file(repo, path) → {success, content}
  github.list_files(repo, path) → {success, files}
  github.scaffold_nextjs_saas(repo, product_name, description) → {success}

[vercel] Deploy products — needs VERCEL_TOKEN in secrets
  vercel.create_project(name, github_repo) → {success, project_id, url}
  vercel.set_env_vars(project_id, env_vars={key:val}) → {success}
  vercel.get_deployments(project_name) → {deployments}
  vercel.check_deployment_status(deployment_id) → {state, ready, url}

[code] Run and fix code — self-healing
  code.run_python(code, timeout) → {success, stdout, stderr}
  code.run_shell(command, cwd) → {success, stdout, stderr}
  code.validate_python(code) → {valid, errors}
  code.analyze_error(error_text) → {type, fix, suggestion}
  code.test_api_endpoint(url) → {success, status, response}

RULES:
1. ALWAYS use tools to do real work. Never say what you "would" do.
2. Tool fails? Read the error, analyze it, retry with different approach.
3. Missing capability? Create a new specialized agent via add_agent.
4. Big task? Break it into sub-tasks and delegate via create_task.
5. Important findings? Store in memory so other agents can use them.
6. Major milestone? Email the founder.
7. GITHUB_TOKEN is always available automatically — use it freely.
"""

def execute_tool_calls(tool_calls: list) -> list:
    results = []
    for call in tool_calls:
        tool_name = call.get("tool", "")
        action_name = call.get("action", "")
        params = call.get("params", {})
        print(f"    🔧 {tool_name}.{action_name}({list(params.keys())})")
        try:
            if tool_name == "search":
                from tools.search_tool import search, fetch_page, research_saas_opportunity
                fns = {"search": search, "fetch_page": fetch_page, "research_saas_opportunity": research_saas_opportunity}
            elif tool_name == "github":
                from tools.github_tool import (create_repo, write_file, write_multiple_files,
                    read_file, list_files, scaffold_nextjs_saas)
                fns = {"create_repo": create_repo, "write_file": write_file,
                    "write_multiple_files": write_multiple_files, "read_file": read_file,
                    "list_files": list_files, "scaffold_nextjs_saas": scaffold_nextjs_saas}
            elif tool_name == "vercel":
                from tools.vercel_tool import (create_project, set_env_vars,
                    get_deployments, check_deployment_status, get_project_url)
                fns = {"create_project": create_project, "set_env_vars": set_env_vars,
                    "get_deployments": get_deployments, "check_deployment_status": check_deployment_status,
                    "get_project_url": get_project_url}
            elif tool_name == "code":
                from tools.code_tool import run_python, run_shell, validate_python, analyze_error, test_api_endpoint
                fns = {"run_python": run_python, "run_shell": run_shell,
                    "validate_python": validate_python, "analyze_error": analyze_error,
                    "test_api_endpoint": test_api_endpoint}
            else:
                results.append({"tool": tool_name, "action": action_name, "result": {"error": f"Unknown tool: {tool_name}"}})
                continue
            
            fn = fns.get(action_name)
            if not fn:
                results.append({"tool": tool_name, "action": action_name, "result": {"error": f"Unknown action: {action_name}"}})
                continue
            
            result = fn(**params)
            results.append({"tool": tool_name, "action": action_name, "result": result})
            
            # Truncate large results for logging
            result_str = str(result)
            print(f"    ✓ {result_str[:120]}{'...' if len(result_str) > 120 else ''}")
            
        except Exception as e:
            results.append({"tool": tool_name, "action": action_name, "result": {"error": str(e)}})
            print(f"    ✗ Error: {e}")
    return results

def build_context(sb, task: dict) -> str:
    try:
        memories = sb.table("memory").select("key, value, category").execute()
        mem_str = "\n".join([f"  {m['key']}: {m['value']}" for m in (memories.data or [])]) or "  (empty)"
    except:
        mem_str = "  (could not load)"

    try:
        products = sb.table("products").select("name, status, repo_url, live_url, description").execute()
        prod_str = "\n".join([
            f"  {p['name']} [{p['status']}] repo:{p.get('repo_url') or '-'} live:{p.get('live_url') or '-'}"
            for p in (products.data or [])
        ]) or "  None"
    except:
        prod_str = "  (could not load)"

    try:
        decisions = sb.table("decisions").select("description").order("created_at", desc=True).limit(8).execute()
        dec_str = "\n".join([f"  • {d['description']}" for d in (decisions.data or [])]) or "  None"
    except:
        dec_str = "  None"

    try:
        done = sb.table("tasks").select("description").eq("status", "complete").order("completed_at", desc=True).limit(8).execute()
        done_str = "\n".join([f"  ✓ {t['description'][:70]}" for t in (done.data or [])]) or "  None"
    except:
        done_str = "  None"

    retry_str = ""
    if task.get("retry_count", 0) > 0:
        retry_str = f"\n⚠️ RETRY {task['retry_count']}/3\nPrevious error: {task.get('last_error', '')[:300]}\nTry a completely different approach.\n"

    parent_str = ""
    if task.get("parent_task_id"):
        try:
            p = sb.table("tasks").select("description, output").eq("id", task["parent_task_id"]).execute()
            if p.data:
                parent_str = f"\nPARENT TASK: {p.data[0]['description']}\nOutput so far: {(p.data[0].get('output') or '')[:200]}\n"
        except:
            pass

    return f"""
== ORG MEMORY ==
{mem_str}

== ACTIVE PRODUCTS ==
{prod_str}

== RECENT DECISIONS ==
{dec_str}

== RECENTLY COMPLETED ==
{done_str}

== CREDENTIALS ==
  GITHUB_OWNER: {os.environ.get('GITHUB_OWNER', '(not set — add to secrets)')}
  GITHUB_TOKEN: {"✓ available" if os.environ.get("GITHUB_TOKEN") else "✗ missing"}
  VERCEL_TOKEN: {"✓ available" if os.environ.get("VERCEL_TOKEN") else "✗ not set yet"}
  EMAIL: {"✓ available" if os.environ.get("RESEND_API_KEY") else "✗ not set yet"}
{parent_str}{retry_str}
== YOUR TASK ==
{task['description']}

CONTEXT:
{task.get('context', 'None')}
"""

def run_agent(sb, task: dict) -> dict:
    # Load agent
    agent_data = task.get("agents") or {}
    if not agent_data and task.get("assigned_to"):
        row = sb.table("agents").select("*").eq("id", task["assigned_to"]).execute()
        agent_data = row.data[0] if row.data else {}

    agent_name = agent_data.get("name", "Agent")
    agent_prompt = agent_data.get("system_prompt", "You are a helpful AI agent.")

    all_agents = sb.table("agents").select("name, role").eq("active", True).execute()
    roster = "\n".join([f"  {a['name']}: {a['role']}" for a in (all_agents.data or [])])

    context = build_context(sb, task)

    messages = [
        {"role": "system", "content": f"{META}\n\n== YOUR IDENTITY ==\n{agent_prompt}\n\n== TEAM ==\n{roster}"},
        {"role": "user", "content": context},
    ]

    desc_lower = task.get("description", "").lower()
    if any(w in desc_lower for w in ["build", "code", "scaffold", "develop", "implement", "write"]):
        model = "Meta-Llama-3.3-70B-Instruct"
    elif any(w in desc_lower for w in ["research", "analyze", "plan", "strategy", "find"]):
        model = "Meta-Llama-3.3-70B-Instruct"
    else:
        model = None

    print(f"\n  [{agent_name}] → {task['description'][:70]}")

    result = call_llm_json(messages, model=model)

    # Execute tools
    tool_calls = result.get("tool_calls", [])
    tool_results = []

    if tool_calls:
        print(f"  [{agent_name}] Running {len(tool_calls)} tool(s)...")
        tool_results = execute_tool_calls(tool_calls)

        # Second pass: agent sees what actually happened
        tool_summary = json.dumps(tool_results, indent=2)[:3000]
        messages.append({"role": "assistant", "content": json.dumps(result)})
        messages.append({
            "role": "user",
            "content": f"""Tool results:
{tool_summary}

Now:
1. Confirm what succeeded and what failed
2. If something failed, add retry tool_calls or different approach
3. Update org_actions based on what actually happened
4. Write a response summarizing the ACTUAL outcome

Respond with the same JSON structure."""
        })
        result = call_llm_json(messages, model=model)

    result.setdefault("tool_calls", tool_calls)
    result.setdefault("org_actions", [])
    result.setdefault("response", result.get("thought", "Done."))
    result.setdefault("thought", "")
    result["tool_results"] = tool_results

    tools_used = len(tool_calls)
    actions_taken = len(result.get("org_actions", []))
    print(f"  [{agent_name}] ✓ Complete — {tools_used} tools, {actions_taken} org actions")

    return result
