"""DuckDuckGo search + page fetch helpers for Andre.

Uses the duckduckgo-search library (no API key) and BeautifulSoup to
extract main page text. All public functions are async; sync calls are
wrapped via asyncio.to_thread so they don't block the event loop.

Robustness:
  - tries multiple DDG backends (api, html, lite) in order
  - retries with exponential backoff on RatelimitException
  - never raises — on persistent failure returns [] / "" so the agent
    can continue reasoning from model knowledge
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from bs4 import BeautifulSoup

from utils.quality import is_garbage_page, sanitize_text

try:
    from duckduckgo_search import DDGS
    try:
        from duckduckgo_search.exceptions import RatelimitException  # type: ignore
    except Exception:
        class RatelimitException(Exception):
            pass
except Exception:
    DDGS = None  # type: ignore

    class RatelimitException(Exception):
        pass


_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_BACKENDS = ("api", "html", "lite")


def _ddg_sync(query: str, max_results: int, backend: str) -> list[dict[str, Any]]:
    """Blocking DDG call — must run inside asyncio.to_thread."""
    if DDGS is None:
        return []
    out: list[dict[str, Any]] = []
    with DDGS() as ddgs:
        kwargs: dict[str, Any] = {
            "region": "wt-wt",
            "safesearch": "moderate",
            "max_results": max_results,
        }
        # Older versions accept positional only; newer accept backend kw.
        try:
            iterator = ddgs.text(query, backend=backend, **kwargs)
        except TypeError:
            iterator = ddgs.text(query, **kwargs)
        for r in iterator or []:
            out.append(
                {
                    "title": (r.get("title") or "").strip(),
                    "url": (r.get("href") or r.get("url") or "").strip(),
                    "snippet": (r.get("body") or r.get("snippet") or "").strip(),
                }
            )
    return out


async def ddg_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search DuckDuckGo and return [{title,url,snippet}]. Never raises."""
    max_results = max(1, min(int(max_results or 5), 10))
    backoff = 1.5
    for attempt in range(3):
        for backend in _BACKENDS:
            try:
                results = await asyncio.to_thread(
                    _ddg_sync, query, max_results, backend
                )
                if results:
                    return results
            except RatelimitException:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 8.0)
            except Exception:
                # try the next backend, then the next attempt
                continue
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 8.0)
    return []


def _clean_html(html: str, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(
        ["script", "style", "noscript", "iframe", "nav", "header",
         "footer", "aside", "form", "svg", "button"]
    ):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cleaned = "\n".join(lines)
    cleaned = sanitize_text(cleaned, max_len=max_chars)
    return cleaned


async def fetch_page(url: str, max_chars: int = 4000) -> str:
    """Fetch a URL and return cleaned main-content text. Never raises.
    Garbage pages (mostly non-Latin / collapsed repetition) return ""."""
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            follow_redirects=True,
            headers=_DEFAULT_HEADERS,
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return ""
            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype and "text" not in ctype:
                return ""
            cleaned = _clean_html(resp.text, max_chars)
            if is_garbage_page(cleaned):
                return ""
            return cleaned
    except Exception:
        return ""


async def search_and_fetch(
    query: str,
    max_results: int = 5,
    fetch_top: int = 2,
    max_chars: int = 3500,
) -> tuple[str, dict]:
    """Search DDG, fetch top N pages, return (formatted_text, stats).

    stats = {"result_count": int, "pages_fetched": int, "page_urls": list[str]}
    """
    results = await ddg_search(query, max_results=max_results)
    stats = {"result_count": len(results), "pages_fetched": 0, "page_urls": []}
    if not results:
        return (
            f"No search results returned for: {query}\n"
            "(DuckDuckGo may be rate-limiting. Proceed using your model "
            "knowledge and clearly mark any unsourced claims.)",
            stats,
        )

    chunks: list[str] = [f"Search results for: {query}", ""]
    for i, r in enumerate(results, 1):
        title = sanitize_text(r["title"], max_len=200)
        snippet = sanitize_text(r["snippet"], max_len=400)
        chunks.append(f"[{i}] {title}")
        chunks.append(r["url"])
        chunks.append(snippet)
        chunks.append("")

    fetch_top = max(0, min(int(fetch_top or 0), len(results)))
    if fetch_top > 0:
        page_tasks = [fetch_page(results[i]["url"], max_chars) for i in range(fetch_top)]
        pages = await asyncio.gather(*page_tasks, return_exceptions=False)
        for i, page in enumerate(pages):
            if not page:
                continue
            stats["pages_fetched"] += 1
            stats["page_urls"].append(results[i]["url"])
            chunks.append(f"--- Full content from {results[i]['url']} ---")
            chunks.append(page)
            chunks.append("")

    return "\n".join(chunks).strip(), stats
