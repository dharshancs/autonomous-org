"""
tools/github_tool.py

Gives agents the ability to:
- Create/update files in any GitHub repo
- Create new repos for new products
- Read file contents
- Create pull requests
- Run GitHub Actions workflows
- List repo contents

This is what lets Arjun actually WRITE CODE and push it.
"""
import os
import json
import base64
import urllib.request
import urllib.error

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "")  # Set this in GitHub Secrets
BASE = "https://api.github.com"

def _headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def _request(method, path, data=None):
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

def create_repo(name: str, description: str = "", private: bool = False) -> dict:
    """Create a new GitHub repo for a new product."""
    data, err = _request("POST", "/user/repos", {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": True,
    })
    if err:
        return {"success": False, "error": err}
    return {
        "success": True,
        "repo_url": data.get("html_url"),
        "clone_url": data.get("clone_url"),
        "name": data.get("full_name"),
    }

def write_file(repo: str, path: str, content: str, message: str, branch: str = "main") -> dict:
    """
    Create or update a file in a repo.
    repo = "owner/repo-name"
    path = "src/app/page.tsx"
    content = full file content (string)
    """
    # Check if file exists (need SHA for updates)
    existing, _ = _request("GET", f"/repos/{repo}/contents/{path}?ref={branch}")
    sha = existing.get("sha") if existing else None

    encoded = base64.b64encode(content.encode()).decode()
    payload = {
        "message": message,
        "content": encoded,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    data, err = _request("PUT", f"/repos/{repo}/contents/{path}", payload)
    if err:
        return {"success": False, "error": err, "path": path}
    return {
        "success": True,
        "path": path,
        "url": data.get("content", {}).get("html_url", ""),
    }

def write_multiple_files(repo: str, files: list, commit_message: str, branch: str = "main") -> dict:
    """
    Write multiple files in one operation.
    files = [{"path": "...", "content": "..."}, ...]
    Uses Git Trees API for atomic multi-file commit.
    """
    # Get latest commit SHA
    ref_data, err = _request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
    if err:
        return {"success": False, "error": f"Could not get branch ref: {err}"}

    base_sha = ref_data["object"]["sha"]

    # Get base tree
    commit_data, err = _request("GET", f"/repos/{repo}/git/commits/{base_sha}")
    if err:
        return {"success": False, "error": err}
    base_tree_sha = commit_data["tree"]["sha"]

    # Create blobs for each file
    tree_items = []
    for f in files:
        blob, err = _request("POST", f"/repos/{repo}/git/blobs", {
            "content": f["content"],
            "encoding": "utf-8",
        })
        if err:
            return {"success": False, "error": f"Blob creation failed for {f['path']}: {err}"}
        tree_items.append({
            "path": f["path"],
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })

    # Create tree
    tree, err = _request("POST", f"/repos/{repo}/git/trees", {
        "base_tree": base_tree_sha,
        "tree": tree_items,
    })
    if err:
        return {"success": False, "error": f"Tree creation failed: {err}"}

    # Create commit
    new_commit, err = _request("POST", f"/repos/{repo}/git/commits", {
        "message": commit_message,
        "tree": tree["sha"],
        "parents": [base_sha],
    })
    if err:
        return {"success": False, "error": f"Commit failed: {err}"}

    # Update branch ref
    _, err = _request("PATCH", f"/repos/{repo}/git/refs/heads/{branch}", {
        "sha": new_commit["sha"],
        "force": False,
    })
    if err:
        return {"success": False, "error": f"Ref update failed: {err}"}

    return {
        "success": True,
        "commit_sha": new_commit["sha"],
        "files_written": len(files),
        "repo_url": f"https://github.com/{repo}",
    }

def read_file(repo: str, path: str, branch: str = "main") -> dict:
    """Read a file from a repo."""
    data, err = _request("GET", f"/repos/{repo}/contents/{path}?ref={branch}")
    if err:
        return {"success": False, "error": err}
    content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
    return {"success": True, "content": content, "sha": data.get("sha")}

def list_files(repo: str, path: str = "", branch: str = "main") -> dict:
    """List files in a directory."""
    data, err = _request("GET", f"/repos/{repo}/contents/{path}?ref={branch}")
    if err:
        return {"success": False, "error": err}
    files = [{"name": f["name"], "type": f["type"], "path": f["path"]} for f in (data if isinstance(data, list) else [])]
    return {"success": True, "files": files}

def trigger_workflow(repo: str, workflow_file: str, inputs: dict = None) -> dict:
    """Trigger a GitHub Actions workflow."""
    _, err = _request("POST", f"/repos/{repo}/actions/workflows/{workflow_file}/dispatches", {
        "ref": "main",
        "inputs": inputs or {},
    })
    if err:
        return {"success": False, "error": err}
    return {"success": True, "message": f"Workflow {workflow_file} triggered"}

def get_latest_run(repo: str, workflow_file: str = None) -> dict:
    """Get the latest workflow run status."""
    path = f"/repos/{repo}/actions/runs?per_page=1"
    data, err = _request("GET", path)
    if err:
        return {"success": False, "error": err}
    runs = data.get("workflow_runs", [])
    if not runs:
        return {"success": True, "status": "no_runs"}
    run = runs[0]
    return {
        "success": True,
        "status": run.get("conclusion") or run.get("status"),
        "name": run.get("name"),
        "url": run.get("html_url"),
    }

# ── SCAFFOLD HELPERS ──────────────────────────────────────────────────────────

def scaffold_nextjs_saas(repo: str, product_name: str, description: str) -> dict:
    """
    Write a complete Next.js SaaS scaffold to a repo.
    Includes: landing page, auth layout, dashboard, Stripe setup, Supabase config.
    """
    files = [
        {
            "path": "package.json",
            "content": json.dumps({
                "name": product_name.lower().replace(" ", "-"),
                "version": "0.1.0",
                "private": True,
                "scripts": {"dev": "next dev", "build": "next build", "start": "next start"},
                "dependencies": {
                    "next": "14.2.0", "react": "^18", "react-dom": "^18",
                    "@supabase/supabase-js": "^2", "@supabase/ssr": "^0.4",
                    "stripe": "^16", "tailwindcss": "^3",
                    "@types/node": "^20", "@types/react": "^18",
                    "typescript": "^5",
                },
            }, indent=2),
        },
        {
            "path": "app/page.tsx",
            "content": f"""import Link from 'next/link'

export default function Home() {{
  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-8">
      <h1 className="text-5xl font-bold mb-4">{product_name}</h1>
      <p className="text-xl text-gray-400 mb-8 text-center max-w-lg">{description}</p>
      <div className="flex gap-4">
        <Link href="/auth/signup" className="bg-indigo-600 hover:bg-indigo-700 px-6 py-3 rounded-lg font-semibold">
          Get Started Free
        </Link>
        <Link href="/auth/login" className="border border-gray-600 hover:border-gray-400 px-6 py-3 rounded-lg">
          Sign In
        </Link>
      </div>
    </main>
  )
}}
""",
        },
        {
            "path": "app/layout.tsx",
            "content": """import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = { title: 'App', description: 'SaaS App' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white">{children}</body>
    </html>
  )
}
""",
        },
        {
            "path": "app/globals.css",
            "content": "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n",
        },
        {
            "path": "app/dashboard/page.tsx",
            "content": """'use client'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

export default function Dashboard() {
  const [user, setUser] = useState<any>(null)

  useEffect(() => {
    const sb = createClient()
    sb.auth.getUser().then(({ data }) => setUser(data.user))
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>
      <p className="text-gray-400">Welcome, {user?.email}</p>
    </div>
  )
}
""",
        },
        {
            "path": "lib/supabase/client.ts",
            "content": """import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
""",
        },
        {
            "path": "lib/supabase/server.ts",
            "content": """import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export function createClient() {
  const cookieStore = cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll() { return cookieStore.getAll() }, setAll(c) { try { c.forEach(({ name, value, options }) => cookieStore.set(name, value, options)) } catch {} } } }
  )
}
""",
        },
        {
            "path": ".env.example",
            "content": "NEXT_PUBLIC_SUPABASE_URL=\nNEXT_PUBLIC_SUPABASE_ANON_KEY=\nSTRIPE_SECRET_KEY=\nSTRIPE_WEBHOOK_SECRET=\n",
        },
        {
            "path": "tailwind.config.ts",
            "content": """import type { Config } from 'tailwindcss'
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
}
export default config
""",
        },
        {
            "path": ".github/workflows/deploy.yml",
            "content": """name: Deploy to Vercel
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm install
      - run: npm run build
""",
        },
        {
            "path": "README.md",
            "content": f"# {product_name}\n\n{description}\n\n## Stack\n- Next.js 14\n- Supabase (auth + db)\n- Stripe (payments)\n- Vercel (hosting)\n- Tailwind CSS\n",
        },
    ]

    return write_multiple_files(repo, files, f"🚀 Initial scaffold: {product_name}")
