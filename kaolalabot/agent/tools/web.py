"""Agent tools - Web Search tool."""

import asyncio
from typing import Any

from kaolalabot.agent.tools.base import Tool


class WebSearchTool(Tool):
    """Tool for searching the web."""

    def __init__(self, api_key: str = None, max_results: int = 5):
        self.api_key = api_key
        self.max_results = max_results

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for information. Returns search results with titles, URLs, and snippets."

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query string",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    async def execute(self, query: str, max_results: int = None) -> str:
        """Execute web search."""
        max_results = max_results or self.max_results
        
        try:
            import aiohttp
            
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
                "limit": max_results,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        return f"Error: Search API returned status {response.status}"
                    
                    data = await response.json()
                    
                    results = data.get("RelatedTopics", [])
                    if not results:
                        return f"No results found for: {query}"
                    
                    output = []
                    for i, item in enumerate(results[:max_results], 1):
                        if "Text" in item:
                            text = item.get("Text", "")
                            first_url = item.get("FirstURL", "")
                            output.append(f"{i}. {text}\n   URL: {first_url}")
                    
                    if not output:
                        return f"No results found for: {query}"
                    
                    return f"Search results for '{query}':\n\n" + "\n\n".join(output)
                    
        except ImportError:
            return "Error: aiohttp library not installed. Install with: pip install aiohttp"
        except asyncio.TimeoutError:
            return "Error: Search request timed out"
        except Exception as e:
            return f"Error during search: {str(e)}"


class WebFetchTool(Tool):
    """Tool for fetching web page content."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch content from a specific URL. Returns the page title and main text content."

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to fetch",
                        },
                    },
                    "required": ["url"],
                },
            },
        }

    async def execute(self, url: str) -> str:
        """Fetch web page content."""
        try:
            import aiohttp
            from bs4 import BeautifulSoup
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                    if response.status != 200:
                        return f"Error: HTTP {response.status}"
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    title = soup.find('title')
                    title_text = title.get_text(strip=True) if title else "No title"
                    
                    for script in soup(['script', 'style']):
                        script.decompose()
                    
                    text = soup.get_text(separator='\n', strip=True)
                    lines = [line for line in text.split('\n') if line.strip()]
                    content = '\n'.join(lines[:100])
                    
                    return f"Title: {title_text}\n\nContent:\n{content}"
                    
        except ImportError as e:
            return f"Error: Required library not installed: {e}"
        except asyncio.TimeoutError:
            return f"Error: Request timed out after {self.timeout}s"
        except Exception as e:
            return f"Error fetching URL: {str(e)}"
