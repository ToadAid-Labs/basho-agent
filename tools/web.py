import urllib.request
import urllib.error
from urllib.parse import quote

from core.tools import register_tool

# ---------------------------------------------------------------------------
# Web Search — DuckDuckGo HTML fallback (no API key needed)
# ---------------------------------------------------------------------------


@register_tool(
    name="web_search",
    description="Search the web via DuckDuckGo and return the top results as a list of titles and URLs.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
        },
        "required": ["query"],
    },
)
def web_search(query: str) -> str:
    """Search DuckDuckGo HTML and extract result titles + URLs."""
    try:
        encoded = quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = []
        for line in html.splitlines():
            if 'result__a"' in line:
                # Extract text between > and <
                start = line.find(">")
                end = line.rfind("<")
                if start != -1 and end != -1 and start < end:
                    text = line[start + 1 : end].strip()
                    if text and len(text) > 5:
                        results.append(text)
            if len(results) >= 10:
                break

        if not results:
            return "No results found."
        return "Search results:\n" + "\n".join(
            f"{i+1}. {r}" for i, r in enumerate(results)
        )
    except Exception as e:  # noqa: BLE001
        return f"[error] Search failed: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Web Fetch — retrieve a URL and extract visible text
# ---------------------------------------------------------------------------


def _extract_text(html: str) -> str:
    """Very simple HTML → plain text, keeping headings and paragraphs."""
    import re

    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r" +", " ", text)
    text = text.strip()
    return text


@register_tool(
    name="web_fetch",
    description="Fetch the content of a URL and return the visible text. Useful for reading articles, docs, or raw files.",
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL to fetch (http:// or https://).",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (default 3000).",
            },
        },
        "required": ["url"],
    },
)
def web_fetch(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL and return visible text."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()

        if "text/html" in content_type:
            html = raw.decode("utf-8", errors="replace")
            text = _extract_text(html)
        else:
            text = raw.decode("utf-8", errors="replace")

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"

        return text
    except urllib.error.HTTPError as e:
        return f"[error] HTTP {e.code}: {e.reason}"
    except Exception as e:  # noqa: BLE001
        return f"[error] Fetch failed: {type(e).__name__}: {e}"
