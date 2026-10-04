"""
MAYA Browser Agent
Handles web exploration, default browser launching, web searching, and page inspection.
Requires confirmation for sensitive operations.
"""
import urllib.request
import urllib.parse
import json
import webbrowser
import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

class BrowserAgent:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 MAYA/2.0"

    def open_url(self, url: str) -> Dict[str, Any]:
        """Opens URL in user's default Windows browser."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        try:
            success = webbrowser.open(url)
            return {"success": success, "url": url, "message": f"Opened {url} in default browser."}
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}

    def search_web(self, query: str) -> Dict[str, Any]:
        """Performs a web search via DuckDuckGo HTML API and parses instant snippets."""
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})

        results = []
        try:
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                soup = BeautifulSoup(html, "html.parser")
                for link in soup.find_all("a", class_="result__snippet")[:5]:
                    snippet = link.get_text().strip()
                    results.append({"snippet": snippet})
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            # Fallback to browser search
            fallback_url = f"https://www.google.com/search?q={encoded}"
            webbrowser.open(fallback_url)
            return {
                "success": True,
                "query": query,
                "fallback_opened": True,
                "message": f"Opened web search in browser: {fallback_url}"
            }

    def fetch_page_text(self, url: str, max_chars: int = 4000) -> Dict[str, Any]:
        """Fetches and cleans visible text from a public web page."""
        if not url.startswith("http"):
            url = "https://" + url

        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                soup = BeautifulSoup(html, "html.parser")
                # Remove scripts and styles
                for s in soup(["script", "style", "nav", "footer"]):
                    s.extract()
                text = " ".join(soup.get_text().split())[:max_chars]
                return {
                    "success": True,
                    "url": url,
                    "title": soup.title.string.strip() if soup.title else "",
                    "content": text
                }
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}
