"""Browser pool manager with rate limiting for concurrent browser instances."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from browser_use import Browser

logger = logging.getLogger(__name__)


class BrowserPool:
    """Manage multiple browser instances with rate limiting."""
    
    def __init__(
        self,
        max_instances: int = 3,
        rate_limit_delay: int = 30,
        max_per_day: int = 50,
        headless: bool = True,
        ollama_model: str = "qwen2.5:7b"
    ):
        self.max_instances = max_instances
        self.rate_limit_delay = rate_limit_delay
        self.max_per_day = max_per_day
        self.headless = headless
        self.ollama_model = ollama_model
        
        self.semaphore = asyncio.Semaphore(max_instances)
        self.rate_limit_lock = asyncio.Lock()
        self.last_search_time: Optional[datetime] = None
        self.daily_count = 0
        self.daily_reset = datetime.now()
        
        self.browsers: List[Browser] = []
        
    async def initialize(self):
        """Initialize browser instances."""
        logger.info(f"Initializing {self.max_instances} browser instances...")
        for i in range(self.max_instances):
            browser = Browser(headless=self.headless)
            self.browsers.append(browser)
            logger.info(f"Browser instance {i+1} initialized")
    
    async def cleanup(self):
        """Close all browser instances."""
        logger.info("Cleaning up browser instances...")
        for browser in self.browsers:
            try:
                # BrowserSession doesn't have close(), just stop using it
                pass
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
        self.browsers.clear()
        logger.info("Browser cleanup complete")
    
    async def _check_daily_limit(self) -> bool:
        """Check if daily search limit reached."""
        now = datetime.now()
        
        # Reset counter if it's a new day
        if now.date() > self.daily_reset.date():
            self.daily_count = 0
            self.daily_reset = now
            logger.info("Daily search counter reset")
        
        if self.daily_count >= self.max_per_day:
            logger.warning(f"Daily search limit ({self.max_per_day}) reached")
            return False
        
        return True
    
    async def _enforce_rate_limit(self):
        """Wait if needed to respect rate limit."""
        async with self.rate_limit_lock:
            if self.last_search_time:
                elapsed = (datetime.now() - self.last_search_time).total_seconds()
                if elapsed < self.rate_limit_delay:
                    wait_time = self.rate_limit_delay - elapsed
                    logger.info(f"Rate limiting: waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
            
            self.last_search_time = datetime.now()
            self.daily_count += 1
    
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform Google search with rate limiting."""
        if not await self._check_daily_limit():
            raise Exception("Daily search limit reached")
        
        async with self.semaphore:
            await self._enforce_rate_limit()
            
            # Round-robin browser selection
            browser_idx = self.daily_count % len(self.browsers)
            browser = self.browsers[browser_idx]
            
            try:
                # Navigate to Google and search
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                await browser.goto(search_url)
                await browser.wait_for_load_state('networkidle')
                
                # Extract search results
                results = await browser.query_selector_all('div.g')
                articles = []
                
                for result in results[:5]:  # Top 5 results
                    try:
                        title_elem = await result.query_selector('h3')
                        title = await title_elem.inner_text() if title_elem else 'No title'
                        
                        link_elem = await result.query_selector('a')
                        url = await link_elem.get_attribute('href') if link_elem else ''
                        
                        desc_elem = await result.query_selector('div.VwiC3b')
                        description = await desc_elem.inner_text() if desc_elem else ''
                        
                        articles.append({
                            'title': title,
                            'url': url,
                            'description': description,
                            'source_query': query,
                            'retrieved_at': datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error parsing result: {e}")
                        continue
                
                logger.info(f"Search completed: found {len(articles)} articles for '{query}'")
                return articles
                
            except Exception as e:
                logger.error(f"Search failed for '{query}': {e}")
                raise
    
    def _parse_search_results(self, result: Any, query: str) -> List[Dict[str, Any]]:
        """Parse browser-use output into structured articles."""
        articles = []
        
        try:
            # Extract text from result
            if hasattr(result, 'content'):
                text = result.content
            elif isinstance(result, str):
                text = result
            else:
                text = str(result)
            
            # Simple parsing - split by lines and look for URLs
            lines = text.split('\n')
            current_article = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_article and 'title' in current_article:
                        articles.append(current_article)
                        current_article = {}
                    continue
                
                # Look for URLs
                if line.startswith('http://') or line.startswith('https://'):
                    current_article['url'] = line
                elif 'title' not in current_article and len(line) > 10:
                    current_article['title'] = line
                elif 'description' not in current_article:
                    current_article['description'] = line
                
                current_article['source_query'] = query
                current_article['retrieved_at'] = datetime.now().isoformat()
            
            # Don't forget last article
            if current_article and 'title' in current_article:
                articles.append(current_article)
            
        except Exception as e:
            logger.error(f"Error parsing search results: {e}")
        
        return articles
