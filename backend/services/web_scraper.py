import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


async def web_search(query: str, max_results: int = 8) -> str:
    """Search the web using DuckDuckGo and return combined text results."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.warning("duckduckgo_search not installed — skipping web search (slim serverless bundle).")
        return "Web search is not available in this deployment."

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            logger.warning(f"No web search results for: {query[:80]}")
            return "No results found."

        combined = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            combined.append(f"[{title}] ({href})\n{body}")

        text = "\n\n".join(combined)
        logger.info(f"Web search '{query[:50]}...' returned {len(results)} results, {len(text)} chars")
        return text
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return f"Search failed: {str(e)}"


async def scrape_url(url: str, timeout: int = 15) -> str:
    """Scrape a webpage and return its text content."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Truncate to avoid token limits
        return text[:15000]
    except Exception as e:
        logger.error(f"Scrape error for {url}: {e}")
        return ""


async def search_cricket_live(team1: str, team2: str) -> str:
    """Search for live cricket scores and match details."""
    queries = [
        f"{team1} vs {team2} IPL 2026 live score today",
        f"{team1} vs {team2} IPL 2026 scorecard batting bowling",
    ]
    results = []
    for q in queries:
        text = await web_search(q, max_results=5)
        results.append(text)
    return "\n\n---\n\n".join(results)


async def search_match_context(team1: str, team2: str, venue: str) -> str:
    """Search for comprehensive match context: H2H, form, venue, injuries, conditions."""
    queries = [
        f"{team1} vs {team2} head to head IPL record last 5 years results",
        f"{team1} vs {team2} IPL 2026 prediction preview team news injuries playing XI",
        f"{venue} IPL pitch report conditions batting bowling average score",
        f"{team1} IPL 2026 recent form results last 5 matches",
        f"{team2} IPL 2026 recent form results last 5 matches",
    ]
    results = []
    for q in queries:
        text = await web_search(q, max_results=5)
        results.append(f"=== {q} ===\n{text}")
    return "\n\n".join(results)


async def search_player_data(team1: str, team2: str, venue: str) -> str:
    """Search for player stats and playing XI info."""
    queries = [
        f"{team1} vs {team2} IPL 2026 expected playing XI squad",
        f"{team1} players IPL 2026 stats runs wickets form injury update",
        f"{team2} players IPL 2026 stats runs wickets form injury update",
    ]
    results = []
    for q in queries:
        text = await web_search(q, max_results=5)
        results.append(f"=== {q} ===\n{text}")
    return "\n\n".join(results)


async def fetch_match_news(team1: str, team2: str) -> list:
    """Fetch latest news articles related to the match teams using newsdata.io API."""
    import os
    import httpx
    api_key = os.environ.get("NEWSDATA_API_KEY", "")
    if not api_key:
        logger.warning("NEWSDATA_API_KEY not set, skipping news fetch")
        return []

    articles = []
    short_names = {
        "Royal Challengers Bengaluru": "RCB",
        "Mumbai Indians": "MI",
        "Chennai Super Kings": "CSK",
        "Kolkata Knight Riders": "KKR",
        "Rajasthan Royals": "RR",
        "Sunrisers Hyderabad": "SRH",
        "Punjab Kings": "PBKS",
        "Gujarat Titans": "GT",
        "Lucknow Super Giants": "LSG",
        "Delhi Capitals": "DC",
    }
    t1_short = short_names.get(team1, team1)
    t2_short = short_names.get(team2, team2)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # First search: match-specific
            resp = await client.get(
                "https://newsdata.io/api/1/latest",
                params={
                    "apikey": api_key,
                    "q": f"{t1_short} vs {t2_short} IPL 2026 Cricket",
                    "language": "en",
                }
            )
            data = resp.json()
            for item in (data.get("results") or []):
                articles.append({
                    "title": item.get("title", ""),
                    "body": (item.get("description") or "")[:300],
                    "url": item.get("link", ""),
                    "source": item.get("source_name", "") or item.get("source_id", ""),
                    "date": item.get("pubDate", ""),
                    "image": item.get("image_url", ""),
                })

            # Second search: broader IPL news if not enough results
            if len(articles) < 3:
                resp2 = await client.get(
                    "https://newsdata.io/api/1/latest",
                    params={
                        "apikey": api_key,
                        "q": "IPL 2026 Cricket",
                        "language": "en",
                    }
                )
                data2 = resp2.json()
                for item in (data2.get("results") or []):
                    articles.append({
                        "title": item.get("title", ""),
                        "body": (item.get("description") or "")[:300],
                        "url": item.get("link", ""),
                        "source": item.get("source_name", "") or item.get("source_id", ""),
                        "date": item.get("pubDate", ""),
                        "image": item.get("image_url", ""),
                    })

    except Exception as e:
        logger.error(f"News fetch error: {e}")

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        if a.get("title") and a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:10]
