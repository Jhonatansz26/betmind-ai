from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    source: str = "duckduckgo"


@dataclass
class ScrapedContent:
    url: str
    title: str
    markdown_content: str
    content_length: int = 0


@dataclass
class AgentState:
    league_key: str = ""
    season: int = 2026
    search_queries: list[str] = field(default_factory=list)
    search_results: list[SearchResult] = field(default_factory=list)
    scraped_content: list[ScrapedContent] = field(default_factory=list)
    raw_extracted: list[dict[str, Any]] = field(default_factory=list)
    validated_fixtures: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    current_node: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def get_unique_urls(self) -> list[str]:
        return list({result.url for result in self.search_results})

    def summary(self) -> dict[str, Any]:
        return {
            "league_key": self.league_key,
            "season": self.season,
            "search_queries": len(self.search_queries),
            "search_results": len(self.search_results),
            "scraped_content": len(self.scraped_content),
            "raw_extracted": len(self.raw_extracted),
            "validated_fixtures": len(self.validated_fixtures),
            "errors": len(self.errors),
            "current_node": self.current_node,
        }
