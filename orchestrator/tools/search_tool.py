"""
tools/search_tool.py

Gives agents real web search via DuckDuckGo (completely free, no API key).
Riya uses this to actually scan for SaaS opportunities.
Any agent uses this to research before making decisions.
"""
import urllib.request
import urllib.parse
import json
import re

def search(query: str, max_results: int = 8) -> list[dict]:
    """
    Search the web. Returns list of {title, url, snippet}.
    Uses DuckDuckGo instant answer API — no key, no limits, free forever.
    """
    encoded = urllib.parse.quote(query)
    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
    except Exception as e:
        return [{"error": str(e)}]
    
    results = []
    
    # Abstract (direct answer)
    if data.get("Abstract"):
        results.append({
            "title": data.get("Heading", "Direct Answer"),
            "url": data.get("AbstractURL", ""),
            "snippet": data["Abstract"][:400],
        })
    
    # Related topics
    for item in data.get("RelatedTopics", [])[:max_results]:
        if isinstance(item, dict) and item.get("Text"):
            results.append({
                "title": item.get("Text", "")[:80],
                "url": item.get("FirstURL", ""),
                "snippet": item.get("Text", "")[:300],
            })
    
    # If DuckDuckGo gave nothing, fall back to HTML scrape
    if not results:
        results = _scrape_search(query, max_results)
    
    return results[:max_results]

def _scrape_search(query: str, max_results: int = 5) -> list[dict]:
    """Fallback: scrape DuckDuckGo HTML results."""
    encoded = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return [{"error": f"Scrape failed: {e}"}]
    
    results = []
    # Extract result snippets
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
    titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
    urls = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html, re.DOTALL)
    
    for i in range(min(max_results, len(snippets))):
        snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
        title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
        url = urls[i].strip() if i < len(urls) else ""
        if snippet:
            results.append({"title": title, "url": url, "snippet": snippet[:300]})
    
    return results

def fetch_page(url: str, max_chars: int = 3000) -> str:
    """
    Fetch and extract text from a webpage.
    Agents use this to read competitor pricing pages, Reddit threads, etc.
    """
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        # Strip HTML tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"Could not fetch {url}: {e}"

def research_saas_opportunity(topic: str) -> dict:
    """
    Structured research for a SaaS idea.
    Returns: market evidence, competitors, pricing, pain points.
    """
    results = {}
    
    # Reddit pain points
    reddit = search(f"site:reddit.com {topic} pain points problems software", max_results=4)
    results["reddit_signals"] = reddit
    
    # Competitors + pricing
    competitors = search(f"{topic} software pricing plans SaaS", max_results=4)
    results["competitors"] = competitors
    
    # Market demand
    demand = search(f'"{topic}" tool "looking for" OR "need a" OR "anyone know"', max_results=3)
    results["demand_signals"] = demand
    
    # Summarize
    all_snippets = " ".join([
        r.get("snippet", "") 
        for r in reddit + competitors + demand
    ])
    
    results["raw_text"] = all_snippets[:2000]
    results["query"] = topic
    
    return results
