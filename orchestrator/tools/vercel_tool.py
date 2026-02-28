"""
tools/vercel_tool.py

Gives Dev agent real deployment capabilities:
- Deploy a GitHub repo to Vercel
- Set environment variables
- Check deployment status
- Get production URL

Free Vercel plan: unlimited deployments, 100GB bandwidth/month.
"""
import os
import json
import urllib.request
import urllib.error

VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")
BASE = "https://api.vercel.com"

def _headers():
    return {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json",
    }

def _request(method, path, data=None):
    if not VERCEL_TOKEN:
        return None, "VERCEL_TOKEN not set in GitHub Secrets"
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        return None, f"HTTP {e.code}: {err[:300]}"
    except Exception as e:
        return None, str(e)

def create_project(name: str, github_repo: str, framework: str = "nextjs") -> dict:
    """
    Link a GitHub repo to a new Vercel project.
    github_repo = "owner/repo-name"
    """
    owner, repo = github_repo.split("/", 1)
    data, err = _request("POST", "/v10/projects", {
        "name": name,
        "framework": framework,
        "gitRepository": {
            "type": "github",
            "repo": github_repo,
        },
        "installCommand": "npm install",
        "buildCommand": "npm run build",
        "outputDirectory": ".next",
    })
    if err:
        return {"success": False, "error": err}
    return {
        "success": True,
        "project_id": data.get("id"),
        "name": data.get("name"),
        "url": f"https://{name}.vercel.app",
    }

def set_env_vars(project_id: str, env_vars: dict, target: list = None) -> dict:
    """
    Set environment variables for a Vercel project.
    env_vars = {"SUPABASE_URL": "https://...", "STRIPE_KEY": "sk_..."}
    """
    if target is None:
        target = ["production", "preview", "development"]
    
    envs = []
    for key, value in env_vars.items():
        envs.append({
            "key": key,
            "value": value,
            "type": "encrypted",
            "target": target,
        })
    
    data, err = _request("POST", f"/v10/projects/{project_id}/env", envs)
    if err:
        return {"success": False, "error": err}
    return {"success": True, "vars_set": list(env_vars.keys())}

def trigger_deploy(project_id: str) -> dict:
    """Manually trigger a new deployment."""
    data, err = _request("POST", f"/v13/deployments", {
        "name": project_id,
        "project": project_id,
        "target": "production",
    })
    if err:
        return {"success": False, "error": err}
    return {
        "success": True,
        "deployment_id": data.get("id"),
        "url": data.get("url"),
        "state": data.get("readyState"),
    }

def get_deployments(project_name: str, limit: int = 5) -> dict:
    """Get recent deployments for a project."""
    data, err = _request("GET", f"/v6/deployments?app={project_name}&limit={limit}")
    if err:
        return {"success": False, "error": err}
    
    deployments = []
    for d in data.get("deployments", []):
        deployments.append({
            "id": d.get("uid"),
            "state": d.get("state"),
            "url": f"https://{d.get('url')}",
            "created": d.get("created"),
            "error": d.get("errorMessage"),
        })
    
    return {"success": True, "deployments": deployments}

def get_project_url(project_name: str) -> str:
    """Get the production URL of a project."""
    data, err = _request("GET", f"/v9/projects/{project_name}")
    if err:
        return f"https://{project_name}.vercel.app"
    
    targets = data.get("targets", {})
    prod = targets.get("production", {})
    alias = prod.get("alias", [])
    if alias:
        return f"https://{alias[0]}"
    return f"https://{project_name}.vercel.app"

def check_deployment_status(deployment_id: str) -> dict:
    """Check if a specific deployment succeeded or failed."""
    data, err = _request("GET", f"/v13/deployments/{deployment_id}")
    if err:
        return {"success": False, "error": err}
    
    state = data.get("readyState", "UNKNOWN")
    return {
        "success": True,
        "state": state,
        "ready": state == "READY",
        "failed": state in ["ERROR", "CANCELED"],
        "url": f"https://{data.get('url', '')}",
        "error": data.get("errorMessage"),
        "build_logs_url": f"https://vercel.com/deployments/{deployment_id}",
    }
