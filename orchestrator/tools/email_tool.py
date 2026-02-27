"""
email_tool.py — Email via Resend (100 free emails/day, no credit card)
Sign up at resend.com and add RESEND_API_KEY to GitHub Secrets.
"""
import os
import json
import urllib.request
import urllib.error

def send_email(to: str | list, subject: str, body: str, html: str = None) -> bool:
    """
    Send an email via Resend.
    Returns True if sent, False if failed (does not crash).
    """
    api_key = os.environ.get("RESEND_API_KEY")
    
    if not api_key:
        # Print to logs instead of crashing
        print(f"\n[EMAIL NOT SENT — Add RESEND_API_KEY to GitHub Secrets to enable]\n"
              f"  To: {to}\n  Subject: {subject}\n  Body: {body[:200]}...\n")
        return False
    
    from_email = os.environ.get("FROM_EMAIL", f"org@{os.environ.get('RESEND_DOMAIN', 'yourdomain.com')}")
    
    payload = {
        "from": from_email,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "text": body,
    }
    if html:
        payload["html"] = html
    
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read())
            print(f"  📧 Email sent → {to}: {subject[:50]}")
            return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        print(f"  ⚠ Email failed (HTTP {e.code}): {error_body[:200]}")
        return False
    except Exception as e:
        print(f"  ⚠ Email failed: {e}")
        return False

def send_weekly_briefing(sb, founder_email: str):
    """
    Compile and send the weekly Sunday briefing email.
    Called by the Analytics agent or directly by orchestrator on Sundays.
    """
    try:
        # Gather org data
        pending_decisions = sb.table("decisions").select("*").eq(
            "needs_approval", True
        ).eq("approved_by_human", False).execute()
        
        products = sb.table("products").select("*").execute()
        
        recent_completions = sb.table("tasks").select(
            "description, output, completed_at"
        ).eq("status", "complete").order(
            "completed_at", desc=True
        ).limit(10).execute()
        
        failed_tasks = sb.table("tasks").select(
            "description, last_error"
        ).eq("status", "failed").order(
            "created_at", desc=True
        ).limit(5).execute()
        
        # Build email
        product_lines = "\n".join([
            f"  • {p['name']} [{p['status']}] — MRR: ₹{p.get('mrr', 0)}, Users: {p.get('user_count', 0)}"
            for p in (products.data or [])
        ]) or "  No products yet."
        
        decisions_lines = "\n".join([
            f"  • {d['description']}" for d in (pending_decisions.data or [])
        ]) or "  No decisions pending."
        
        completed_lines = "\n".join([
            f"  ✓ {t['description'][:70]}" for t in (recent_completions.data or [])
        ]) or "  Nothing completed this week."
        
        failed_lines = "\n".join([
            f"  ✗ {t['description'][:60]}: {(t.get('last_error') or '')[:80]}"
            for t in (failed_tasks.data or [])
        ]) or "  No failures this week 🎉"
        
        body = f"""Your Autonomous Org — Weekly Briefing
{'='*50}

📦 PRODUCTS
{product_lines}

✅ COMPLETED THIS WEEK
{completed_lines}

🔴 DECISIONS NEEDING YOUR APPROVAL
{decisions_lines}

⚠️ TASKS THAT FAILED (already retried 3x)
{failed_lines}

{'='*50}
Reply to any item above with your decision/instruction
and I'll handle it immediately.

— Your Autonomous Org
"""
        
        send_email(
            to=founder_email,
            subject="📊 Weekly Org Briefing",
            body=body
        )
    
    except Exception as e:
        print(f"  ⚠ Could not send weekly briefing: {e}")
