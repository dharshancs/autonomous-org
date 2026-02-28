"""
tools/code_tool.py

Gives agents the ability to:
- Execute Python code and capture output/errors
- Run shell commands safely
- Validate code before committing
- Auto-fix common errors
- Run tests

This is the self-healing core. When code fails, this tool
runs it, reads the error, and the agent tries again.
"""
import subprocess
import sys
import os
import tempfile
import json
import re

def run_python(code: str, timeout: int = 30) -> dict:
    """
    Execute Python code in an isolated subprocess.
    Returns stdout, stderr, return code.
    Safe — runs in temp file, not eval().
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        tmp_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stderr": f"Timeout after {timeout}s", "stdout": "", "returncode": -1}
    except Exception as e:
        return {"success": False, "stderr": str(e), "stdout": "", "returncode": -1}
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

def run_shell(command: str, cwd: str = None, timeout: int = 60) -> dict:
    """
    Run a shell command. Used for npm install, npm run build, etc.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.getcwd(),
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:3000],
            "returncode": result.returncode,
            "command": command,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stderr": f"Timeout after {timeout}s", "stdout": "", "returncode": -1, "command": command}
    except Exception as e:
        return {"success": False, "stderr": str(e), "stdout": "", "returncode": -1, "command": command}

def validate_python(code: str) -> dict:
    """Check Python syntax without running it."""
    try:
        import ast
        ast.parse(code)
        return {"valid": True, "errors": []}
    except SyntaxError as e:
        return {
            "valid": False,
            "errors": [f"Line {e.lineno}: {e.msg}"],
            "line": e.lineno,
        }

def validate_json(text: str) -> dict:
    """Validate JSON."""
    try:
        parsed = json.loads(text)
        return {"valid": True, "parsed": parsed}
    except json.JSONDecodeError as e:
        return {"valid": False, "error": str(e), "position": e.pos}

def analyze_error(error_text: str) -> dict:
    """
    Parse an error message and suggest a fix strategy.
    Used by self-healing: read error → understand it → retry differently.
    """
    error_lower = error_text.lower()
    
    # Import errors
    if "modulenotfounderror" in error_lower or "no module named" in error_lower:
        module = re.search(r"No module named '([^']+)'", error_text)
        module_name = module.group(1) if module else "unknown"
        return {
            "type": "missing_dependency",
            "module": module_name,
            "fix": f"pip install {module_name}",
            "suggestion": f"Add 'pip install {module_name}' before running this code",
        }
    
    # Syntax errors
    if "syntaxerror" in error_lower:
        line = re.search(r"line (\d+)", error_text, re.IGNORECASE)
        return {
            "type": "syntax_error",
            "line": line.group(1) if line else "unknown",
            "suggestion": "Check the code at the indicated line for syntax issues",
        }
    
    # API/auth errors
    if "401" in error_text or "unauthorized" in error_lower:
        return {
            "type": "auth_error",
            "suggestion": "Check that all API keys and tokens are correct and have required permissions",
        }
    
    # Rate limits
    if "429" in error_text or "rate limit" in error_lower:
        return {
            "type": "rate_limit",
            "suggestion": "Wait and retry. Consider adding exponential backoff.",
        }
    
    # Network errors
    if "connection" in error_lower or "timeout" in error_lower:
        return {
            "type": "network_error",
            "suggestion": "Network issue. Retry with timeout handling.",
        }
    
    # Type errors
    if "typeerror" in error_lower or "attributeerror" in error_lower:
        return {
            "type": "code_logic_error",
            "suggestion": "Logic error. Check data types and object attributes.",
        }
    
    return {
        "type": "unknown_error",
        "suggestion": "Review the full error and try a different approach",
    }

def test_api_endpoint(url: str, method: str = "GET", headers: dict = None, body: dict = None) -> dict:
    """
    Test if an API endpoint is working.
    Used to verify deployments are live and responding.
    """
    import urllib.request
    import urllib.error
    
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    data = json.dumps(body).encode() if body else None
    
    try:
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as r:
            response_body = r.read().decode("utf-8", errors="ignore")
            return {
                "success": True,
                "status": r.status,
                "response": response_body[:500],
                "headers": dict(r.headers),
            }
    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "status": e.code,
            "error": e.read().decode("utf-8", errors="ignore")[:300],
        }
    except Exception as e:
        return {"success": False, "error": str(e), "status": 0}
