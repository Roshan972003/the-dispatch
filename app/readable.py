"""Clean article text for the dashboard's source pane, quick-add and Ask Gemini. Pure-Python (httpx + BeautifulSoup), no browser."""
import re
import httpx
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; TheDispatchReader/1.0)", "Accept": "text/html,application/xhtml+xml"}
JUNK = ("script", "style", "noscript", "nav", "footer", "aside", "form", "header", "svg", "iframe")

def _meta(soup, *names):
    for n in names:
        t = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if t and t.get("content"):
            return re.sub(r"\s+", " ", t["content"]).strip()
    return ""

def extract(url, timeout=12, max_chars=3000):
    """-> {title, description, text, final_url} or None when the page cannot be read (login wall, non-HTML, network error)."""
    if "news.google.com" in url:
        return None                 # a redirect shell: the real publisher is not visible without a browser
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True, headers=UA)
    except httpx.HTTPError:
        return None
    if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    title = _meta(soup, "og:title", "twitter:title") or (soup.title.get_text(strip=True) if soup.title else "")
    desc = _meta(soup, "og:description", "description", "twitter:description")
    for t in soup(JUNK):
        t.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paras = [re.sub(r"\s+", " ", p.get_text(" ", strip=True)) for p in root.find_all("p")]
    paras = [p for p in paras if len(p) > 70 and not re.search(r"(subscribe|sign in|cookie|all rights reserved|advertisement)", p, re.I)]
    text = "\n\n".join(paras)[:max_chars]
    if len(text) < 200 and not desc:
        return None
    return {"title": title, "description": desc, "text": text, "final_url": str(r.url)}
