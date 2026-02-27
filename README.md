# 🏢 Autonomous AI Organization
## Complete setup guide — no tech knowledge needed

---

## What you're building

A 24/7 autonomous AI org with 8 agents (ARIA, Riya, Arjun, Sam, Priya, Dev, Raj, Meera) that:
- Runs on GitHub's servers for FREE, forever
- Uses GitHub Models (GPT-4o mini, Llama 3.3) as its brain — also FREE
- Stores all memory in Supabase (free)
- Sends you emails via Resend (100/day free)
- Self-heals on errors (retries 3x automatically)
- Expands itself (agents can add new agents)
- Never needs your intervention except Sunday approvals

**Your total cost: ₹0**

---

## Setup — 5 steps, ~45 minutes

### STEP 1 — Create Supabase database (15 min)

1. Go to **supabase.com** → click "Start your project" → sign in with GitHub
2. Click "New Project"
   - Name it: `autonomous-org`
   - Generate a strong password (save it somewhere)
   - Region: choose closest to you (Mumbai/Singapore)
   - Click "Create new project" → wait ~2 minutes
3. Once ready, go to **SQL Editor** (left sidebar, looks like `</>`)
4. Click "New query"
5. Open `schema.sql` from this folder → copy ALL the text → paste into the SQL editor → click **Run**
   - You should see "Success. No rows returned"
6. Click "New query" again
7. Open `seed.sql` → copy ALL → paste → click **Run**
   - You should see "Success"
8. Go to **Settings → API** (bottom of left sidebar)
   - Copy **Project URL** (looks like: https://xyzabc.supabase.co) — save this
   - Copy **anon/public** key (long string starting with eyJ...) — save this
   - Copy **service_role** key (another long string) — THIS is your SUPABASE_KEY for secrets

Done! Your org's brain exists.

---

### STEP 2 — Create GitHub repository (5 min)

1. Go to **github.com** → sign in (create account if needed, it's free)
2. Click the **+** button (top right) → "New repository"
   - Repository name: `autonomous-org`
   - Make it **Public** (required for unlimited free GitHub Actions minutes)
   - Click "Create repository"
3. You'll see a page with setup instructions. Click **"uploading an existing file"**
4. Drag and drop ALL files from the `autonomous-org/` folder onto that page
   - Make sure the folder structure is maintained (.github/workflows/ etc)
5. Click "Commit changes"

---

### STEP 3 — Add secrets (5 min)

Your org needs to know your Supabase credentials. These are stored as GitHub Secrets (encrypted, never visible).

1. In your GitHub repo, click **Settings** (top menu)
2. Left sidebar → **Secrets and variables → Actions**
3. Click **"New repository secret"** for each of these:

| Secret Name | Value |
|-------------|-------|
| SUPABASE_URL | Your Supabase Project URL from Step 1 |
| SUPABASE_KEY | Your Supabase service_role key from Step 1 |
| FOUNDER_EMAIL | Your email address (for org to email you) |
| RESEND_API_KEY | Get from resend.com (free, see Step 4) |
| FROM_EMAIL | hello@yourdomain.com (or your Resend email) |

> ⚡ GITHUB_TOKEN is provided automatically — you do NOT need to add it. This is what gives you free access to GitHub Models (GPT-4o mini, Llama 3.3, Phi-4).

---

### STEP 4 — Set up email (5 min, optional but recommended)

Without email, the org still runs but can't message you. With email, it sends you updates and the Sunday briefing.

1. Go to **resend.com** → sign up (free)
2. Go to **API Keys** → "Create API Key"
3. Copy the key → add as `RESEND_API_KEY` in GitHub Secrets (Step 3)
4. For FROM_EMAIL: Resend gives you a test domain automatically, or add your own domain

---

### STEP 5 — Verify it's running (2 min)

1. In your GitHub repo, click **Actions** (top menu)
2. You should see "Org Orchestrator" workflow
3. Click it → click "Run workflow" → click the green "Run workflow" button
4. Click on the running job to watch it live
5. You should see the orchestrator output: "ORG ORCHESTRATOR... ✓ Run complete"

**Your org is live.** It will now run automatically every 5 minutes, forever.

---

## How to use it

### Option A — Chat UI (easiest)

Open `frontend/App.jsx` — this is a React app. To run it:

**Easiest: paste it at claude.ai** — copy the contents of App.jsx → go to claude.ai → paste it → Claude will run it as a live React app.

**For permanent hosting:**
```bash
# Install Node.js from nodejs.org first, then:
npm create vite@latest my-org-ui -- --template react
cd my-org-ui
# Replace src/App.jsx with the App.jsx from this folder
npm install @supabase/supabase-js
# Create .env file with:
# VITE_SUPABASE_URL=your_supabase_url
# VITE_SUPABASE_ANON_KEY=your_anon_key
npm run dev
```

### Option B — Talk to org via GitHub Actions (works right now)

1. GitHub repo → **Actions** → "Org Orchestrator"
2. Click "Run workflow"
3. In the "Optional message" field, type anything:
   - "Hey Riya, find me 3 SaaS ideas"
   - "Hey ARIA, let's build a SaaS product"
4. Click "Run workflow"
5. Watch the output in real-time

### Option C — Direct terminal (if you want to run locally)

```bash
# Install Python 3.11 from python.org first, then:
pip install -r requirements.txt

# Create a .env file with your secrets:
echo "SUPABASE_URL=your_url" > .env
echo "SUPABASE_KEY=your_key" >> .env
echo "FOUNDER_EMAIL=your@email.com" >> .env
echo "GITHUB_TOKEN=your_github_token" >> .env
# Get GitHub token from: github.com/settings/tokens → New token → just check "public_repo"

cd orchestrator
python main.py  # Run orchestrator
python chat_ingress.py "Hey Riya, what SaaS ideas do you have?"  # Chat
```

---

## Adding a new agent

You never edit code. Just add a row to Supabase:

1. Go to **Supabase → Table Editor → agents**
2. Click "Insert row"
3. Fill in:
   - `name`: e.g., "Vikram"
   - `role`: e.g., "Legal & Compliance Advisor"
   - `emoji`: e.g., "⚖️"
   - `color`: e.g., "#0891b2"
   - `system_prompt`: Write their full personality and instructions
   - `active`: true
4. Click Save

Vikram now exists and can receive tasks from any other agent. That's it.

The org can also add agents itself — if any agent encounters a task it needs help with and no suitable agent exists, it will create one automatically.

---

## Free tier limits

| Service | Limit | Hits limit when... |
|---------|-------|-------------------|
| GitHub Actions | 2,000 min/month (public repo = unlimited) | Never (public repo) |
| GitHub Models | ~150 req/min, 8k/day for gpt-4o-mini | Only if running 1000s of tasks/day |
| Supabase | 500MB, 50k rows | After months of heavy use |
| Vercel | 100GB bandwidth | After launching products with real traffic |
| Resend | 100 emails/day | Only if org emails you constantly |

**Summary: You will not hit any limits in the first 3-6 months of running this.**

---

## What self-healing looks like

When a task fails:
1. First failure → Task gets error context added, retried with "try a different approach"
2. Second failure → Retried again with more context
3. Third failure → You get an email: "🔴 Task needs your attention"
4. You reply with instructions → The org retries

For compile errors, API errors, wrong formats — the agents self-correct on retries. For true blockers (like a service being down), you get an email.

---

## Weekly Sunday briefing

Every Sunday at 7am IST, you get an email with:
- All products and their status/MRR
- What was completed this week
- Decisions needing your approval
- Tasks that failed 3x and need your input

Your entire job is to read this and reply to any decision emails with APPROVE or REJECT.

---

## Need help?

Paste this error or question to claude.ai and ask for help. Claude built this system and can debug any issue instantly.
