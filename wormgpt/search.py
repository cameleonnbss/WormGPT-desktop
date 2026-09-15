"""Web search for the agent tool — no API key required.

Two backends, both returning clean JSON over stdlib urllib:
  * DuckDuckGo Instant Answer API (encyclopedic summaries + related topics)
  * Wikipedia search API (titles + snippets, reliable fallback)

The formatted result is bounded so it fits comfortably in the model context.
"""

import json
import re
import urllib.parse
import urllib.request

USER_AGENT = "WormGPT-Desktop/1.0"
MAX_RESULTS = 6
MAX_RESULT_LEN = 500
MAX_TOTAL = 5000


def _get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def duckduckgo_instant(query):
    """DuckDuckGo Instant Answer API — abstract + related topics."""
    url = ("https://api.duckduckgo.com/?" +
           urllib.parse.urlencode({"q": query, "format": "json",
                                   "no_html": 1, "skip_disambig": 1}))
    data = _get_json(url)
    results = []
    abstract = (data.get("AbstractText") or "").strip()
    if abstract:
        link = data.get("AbstractURL") or ""
        results.append(f"- {abstract}\n  source: {link}")
    def _walk(topics):
        for t in topics:
            if isinstance(t, dict):
                text = (t.get("Text") or "").strip()
                if text:
                    results.append(f"- {text}\n  source: {t.get('FirstURL') or ''}")
    _walk(data.get("RelatedTopics") or [])
    return results


def wikipedia_search(query, lang="en"):
    """Wikipedia search API — titles + snippets (localized)."""
    url = (f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "srlimit": MAX_RESULTS}))
    data = _get_json(url)
    results = []
    for hit in (data.get("query", {}).get("search") or []):
        snippet = (hit.get("snippet") or "").replace("&quot;", "\"").replace("&#160;", " ")
        results.append(f"- {hit.get('title')}: {snippet}")
    return results


BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")

#: un bloc sponsorisé/annonce — à écarter avant même de lire le titre
_AD_MARK = re.compile(r"result--ad|result--sponsored|ad_provider|ad_domain|"
                      r"y\.js|sponsored", re.I)
_BLOCK = re.compile(r'<div[^>]*class="[^"]*\bresult\b[^"]*"', re.I)


def _fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", "replace")


def _clean(fragment):
    """Strip tags/entities and collapse whitespace."""
    import html as _html
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def _real_url(href):
    """Unwrap DuckDuckGo's /l/?uddg= redirect into the real URL."""
    if "uddg=" in href:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        href = (q.get("uddg") or [href])[0]
    return href


def _blocks(page):
    """Split an HTML results page into per-result blocks.

    Pairing titles and snippets by *block* (instead of two parallel lists)
    is what keeps each snippet attached to its own result — the old code
    mis-aligned them because the ads also carry a snippet.
    """
    parts = _BLOCK.split(page)
    return parts[1:] if len(parts) > 1 else [page]


def duckduckgo_html(query, max_results=MAX_RESULTS):
    """DuckDuckGo HTML endpoint — real web results, no API key."""
    page = _fetch("https://html.duckduckgo.com/html/?" +
                  urllib.parse.urlencode({"q": query}))
    results = []
    for block in _blocks(page):
        head = block[:4000]
        if _AD_MARK.search(head):
            continue                      # annonce → on saute
        m = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                      head, re.S)
        if not m:
            continue
        href = _real_url(urllib.parse.unquote(m.group(1)))
        title = _clean(m.group(2))
        if not title or not href.startswith("http"):
            continue
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', head, re.S)
        entry = f"- {title}\n  {href}"
        if sn:
            snippet = _clean(sn.group(1))[:300]
            if snippet:
                entry += "\n  " + snippet
        results.append(entry)
        if len(results) >= max_results:
            break
    return results


def duckduckgo_lite(query, max_results=MAX_RESULTS):
    """DuckDuckGo Lite — table layout, very stable, good second backend."""
    page = _fetch("https://lite.duckduckgo.com/lite/?" +
                  urllib.parse.urlencode({"q": query}))
    links = re.findall(
        r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        page, re.S)
    snippets = re.findall(
        r'class="result-snippet"[^>]*>(.*?)</td>', page, re.S)
    results = []
    for i, (href, title) in enumerate(links):
        href = _real_url(urllib.parse.unquote(href))
        title = _clean(title)
        if not title or not href.startswith("http"):
            continue
        entry = f"- {title}\n  {href}"
        if i < len(snippets):
            snippet = _clean(snippets[i])[:300]
            if snippet:
                entry += "\n  " + snippet
        results.append(entry)
        if len(results) >= max_results:
            break
    return results


def web_search(query, max_results=MAX_RESULTS, max_total=MAX_TOTAL,
               lang="en"):
    """Search the web and return a bounded, plain-text digest.

    Backends are tried in order and the first one that yields real results
    wins: DuckDuckGo HTML → DuckDuckGo Lite → Instant Answer → Wikipedia.
    """
    lines = []
    backends = (duckduckgo_html, duckduckgo_lite, duckduckgo_instant,
                lambda q: wikipedia_search(q, lang=lang or "en"))
    for backend in backends:
        try:
            got = backend(query)
        except Exception as exc:
            lines.append(f"(search backend unavailable: {exc})")
            continue
        if got:
            lines = got
            break
    if not [l for l in lines if l.startswith("- ")]:
        return f"[web_search] No results for: {query}"
    out = f"Web search results for \"{query}\":\n"
    count = 0
    for line in lines:
        if count >= max_results:
            break
        if not line.startswith("- "):
            continue
        out += line[:MAX_RESULT_LEN] + "\n"
        count += 1
    if len(out) > max_total:
        out = out[:max_total] + "\n… (truncated)"
    return out


WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for up-to-date information (encyclopedic summaries, "
            "news, technical topics). Use it when you need facts you do not "
            "know reliably, recent events, or external references."),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Short, focused search query.",
                },
            },
            "required": ["query"],
        },
    },
}