from __future__ import annotations

import asyncio
import logging
from typing import Any

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from apps.api.services.providers.ai_agent.schemas.agent_state import AgentState, ScrapedContent

logger = logging.getLogger(__name__)

TRUSTED_SOURCES = {
    "sofascore.com",
    "flashscore.com",
    "flashscore.es",
    "espn.com",
    "espn.com.co",
    "dimayor.com.co",
    "caracol.com.co",
    "futbolred.com",
    "eltiempo.com",
    "winwinbeta.com",
}

BLOCKED_SOURCES = {
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "reddit.com",
}

MAX_CONCURRENT_SCRAPES = 3
MAX_CONTENT_LENGTH = 50000
SCRAPE_TIMEOUT = 30


async def _scrape_single_url(
    url: str,
    semaphore: asyncio.Semaphore,
) -> ScrapedContent | None:
    async with semaphore:
        try:
            logger.debug(f"Scraping: {url}")
            
            config = CrawlerRunConfig(
                cache_mode=CacheMode.ENABLED,
                wait_until="domcontentloaded",
                delay_before_return_html=1.0,
            )
            
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url, config=config)
                
                if not result.success:
                    logger.warning(f"Failed to scrape {url}: {result.error_message}")
                    return None
                
                markdown_content = result.markdown_v2.raw_markdown or ""
                
                if len(markdown_content) < 100:
                    logger.warning(f"Content too short for {url}: {len(markdown_content)} chars")
                    return None
                
                if len(markdown_content) > MAX_CONTENT_LENGTH:
                    markdown_content = markdown_content[:MAX_CONTENT_LENGTH]
                    logger.info(f"Truncated content for {url} to {MAX_CONTENT_LENGTH} chars")
                
                title = result.metadata.get("title", url) if result.metadata else url
                
                scraped = ScrapedContent(
                    url=url,
                    title=title,
                    markdown_content=markdown_content,
                    content_length=len(markdown_content),
                )
                
                logger.info(f"Scraped {url}: {len(markdown_content)} chars")
                return scraped
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout scraping {url}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None


def _filter_urls(urls: list[str]) -> list[str]:
    filtered = []
    
    for url in urls:
        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
        
        if any(blocked in domain for blocked in BLOCKED_SOURCES):
            logger.debug(f"Blocked URL: {url}")
            continue
        
        is_trusted = any(trusted in domain for trusted in TRUSTED_SOURCES)
        
        if is_trusted:
            filtered.append(url)
            logger.debug(f"Trusted URL: {url}")
        else:
            logger.debug(f"Non-trusted URL skipped: {url}")
    
    logger.info(f"Filtered {len(urls)} URLs to {len(filtered)} trusted sources")
    return filtered


async def scrape_node(state: AgentState) -> AgentState:
    state.current_node = "scrape_node"
    
    logger.info(f"Starting scrape_node with {len(state.search_results)} search results")
    
    if not state.search_results:
        state.add_error("No search results to scrape")
        logger.warning("No search results to scrape")
        return state
    
    urls_to_scrape = state.get_unique_urls()
    trusted_urls = _filter_urls(urls_to_scrape)
    
    if not trusted_urls:
        state.add_error("No trusted URLs to scrape after filtering")
        logger.warning("No trusted URLs to scrape")
        return state
    
    logger.info(f"Scraping {len(trusted_urls)} trusted URLs with concurrency={MAX_CONCURRENT_SCRAPES}")
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)
    
    scrape_tasks = [
        _scrape_single_url(url, semaphore)
        for url in trusted_urls
    ]
    
    results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
    
    scraped_contents: list[ScrapedContent] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Scrape task failed: {result}")
            state.add_error(f"Scrape task failed: {str(result)}")
        elif result is not None:
            scraped_contents.append(result)
    
    state.scraped_content = scraped_contents
    
    logger.info(
        f"scrape_node completed: {len(scraped_contents)} pages scraped "
        f"from {len(trusted_urls)} URLs"
    )
    
    if not scraped_contents:
        state.add_error("No content scraped from trusted sources")
        logger.warning("No content scraped")
    
    return state
