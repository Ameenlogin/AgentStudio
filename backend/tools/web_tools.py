"""Web tools: keyless DuckDuckGo search + readable page fetch."""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (KimiStudioPro Agent)"}


def web_search(query: str) -> str:
    if not query or not query.strip():
        return "Error: empty search query."
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=HEADERS,
            timeout=20,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for res in soup.select(".result")[:8]:
            a = res.select_one(".result__a")
            snippet = res.select_one(".result__snippet")
            if not a:
                continue
            title = a.get_text(" ", strip=True)
            link = a.get("href", "")
            desc = snippet.get_text(" ", strip=True) if snippet else ""
            results.append(f"- {title}\n  {link}\n  {desc}")
        if not results:
            return f"No results for '{query}'."
        return f"Search results for '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Error searching the web: {e}"


def fetch_url(url: str) -> str:
    if not url or not url.startswith(("http://", "https://")):
        return "Error: provide a full http(s) URL."
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        clean = "\n".join(lines)
        if len(clean) > 12000:
            clean = clean[:12000] + "\n\n[...truncated]"
        title = soup.title.get_text(strip=True) if soup.title else url
        return f"# {title}\n{url}\n\n{clean}"
    except Exception as e:
        return f"Error fetching {url}: {e}"


# ── Advanced web + scraping tools ─────────────────────────────────────────────
import os as _os
import json as _json
from tools.sandbox import resolve as _resolve, rel as _rel


def scrape(url: str, selector: str = "", attr: str = "") -> str:
    """Fetch a page and extract elements by CSS selector (text or an attribute)."""
    if not url or not url.startswith(("http://", "https://")):
        return "Error: provide a full http(s) URL."
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        if not selector:
            return fetch_url(url)
        nodes = soup.select(selector)
        if not nodes:
            return f"No elements matched selector '{selector}'."
        out = []
        for n in nodes[:60]:
            if attr:
                val = n.get(attr, "")
                if val:
                    out.append(val)
            else:
                out.append(n.get_text(" ", strip=True))
        return f"{len(out)} match(es) for '{selector}':\n" + "\n".join(f"- {x}" for x in out if x)
    except Exception as e:
        return f"Error scraping {url}: {e}"


def extract_links(url: str) -> str:
    """Return all hyperlinks on a page as 'text -> href'."""
    if not url or not url.startswith(("http://", "https://")):
        return "Error: provide a full http(s) URL."
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        from urllib.parse import urljoin
        links, seen = [], set()
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            if href in seen:
                continue
            seen.add(href)
            text = a.get_text(" ", strip=True)[:80] or "(no text)"
            links.append(f"{text} -> {href}")
            if len(links) >= 120:
                break
        return f"{len(links)} link(s) on {url}:\n" + "\n".join(links)
    except Exception as e:
        return f"Error extracting links from {url}: {e}"


def http_request(url: str, method: str = "GET", headers: dict | None = None,
                 body: str = "", json_body: dict | None = None) -> str:
    """General HTTP request (GET/POST/PUT/DELETE...). Returns status + body preview."""
    if not url or not url.startswith(("http://", "https://")):
        return "Error: provide a full http(s) URL."
    try:
        h = dict(HEADERS)
        if headers:
            h.update(headers)
        r = requests.request(
            method.upper(), url, headers=h,
            data=body or None, json=json_body or None, timeout=30,
        )
        ct = r.headers.get("content-type", "")
        preview = r.text[:8000]
        return (f"{method.upper()} {url}\nHTTP {r.status_code}  ({ct})\n\n{preview}"
                + ("\n[...truncated]" if len(r.text) > 8000 else ""))
    except Exception as e:
        return f"Error in HTTP request: {e}"


def download_file(url: str, dest: str = "") -> str:
    """Download a file from a URL into the workspace."""
    if not url or not url.startswith(("http://", "https://")):
        return "Error: provide a full http(s) URL."
    try:
        name = dest or url.split("?")[0].rstrip("/").split("/")[-1] or "download.bin"
        out = _resolve(name)
        _os.makedirs(_os.path.dirname(out) or ".", exist_ok=True)
        with requests.get(url, headers=HEADERS, timeout=60, stream=True) as r:
            r.raise_for_status()
            total = 0
            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)
        return f"Downloaded {total} bytes to {_rel(out)}"
    except Exception as e:
        return f"Error downloading {url}: {e}"
