from pprint import pprint
import inspect

from typing import Dict, List, Callable, ContextManager
import pandas as pd
from contextlib import contextmanager

import httpx

from agentic.common import RunContext, PauseForInputResult

TAVILY_API_URL = "https://api.tavily.com"

from functools import wraps
from typing import TypeVar, Generic, Union
from dataclasses import dataclass


class TavilySearchTool:
    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def required_secrets(self) -> dict[str, str]:
        return {"TAVILY_API_KEY": "Tavily API key"}

    def get_tools(self) -> list[Callable]:
        return [
            self.perform_web_search,
            self.query_for_news,
            self.tavily_download_pages,
        ]

    async def query_for_news(
        self, run_context: RunContext, query: str, days_back: int = 1
    ) -> pd.DataFrame | PauseForInputResult:
        """Returns the latest headlines on the given topic."""

        api_key = run_context.get_secret("TAVILY_API_KEY", self.api_key)

        params = {
            "api_key": api_key,
            "query": query,
            "topic": "news",
            "max_results": 10,
            "include_images": False,
            "include_answer": "advanced",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TAVILY_API_URL}/search",
                json=params,
                timeout=90,
            )

        print(f"{TAVILY_API_URL}/search {response}")
        response.raise_for_status()
        results = response.json()

        print(results)

        return pd.DataFrame(results["results"])

    async def perform_web_search(
        self, query: str, include_images: bool = False, run_context: RunContext = None
    ) -> pd.DataFrame | PauseForInputResult:
        """Returns a web search result pages and images using the Tavily search engine. Anything
         related to news should use the query_for_news function.
        Don't use the "site:" filter unless requested explicitly to do so.
        """

        api_key = run_context.get_secret("TAVILY_API_KEY", self.api_key)

        max_results: int = 8
        """Max search results to return, default is 5"""
        search_depth: str = "advanced"
        '''The depth of the search. It can be "basic" or "advanced"'''
        include_domains: List[str] = []
        """A list of domains to specifically include in the search results. Default is None, which includes all domains."""
        exclude_domains: List[str] = []
        """A list of domains to specifically exclude from the search results. Default is None, which doesn't exclude any domains."""
        include_answer: bool = True
        """Include a short answer to original query in the search results. Default is False."""
        include_raw_content: bool = False
        """Include cleaned and parsed HTML of each site search results. Default is False."""

        params = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "include_images": include_images,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TAVILY_API_URL}/search",
                json=params,
                timeout=90,
            )

        print(f"{TAVILY_API_URL}/search {response}")
        response.raise_for_status()
        results = response.json()

        df = pd.DataFrame(results["results"])
        if "images" in results:
            new_rows = pd.DataFrame(
                {"url": results["images"], "title": ["image"] * len(results["images"])}
            )

        # Concatenate the new rows to the existing DataFrame
        return pd.concat([df, new_rows], ignore_index=True)

    async def tavily_download_pages(
        self, run_context: RunContext, urls: list[str], include_images: bool = False
    ) -> pd.DataFrame:
        """Download the content from one or more web page URLS."""
        api_key = run_context.get_secret("TAVILY_API_KEY", self.api_key)

        params = {
            "api_key": api_key,
            "urls": urls,
            "extract_depth": "advanced",
            "include_images": include_images,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/extract",
                json=params,
                timeout=90,
            )

        return response.json()
