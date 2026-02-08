"""Search tool wrapper for browser automation."""

import logging
from typing import List, Dict, Any
from .browser_pool import BrowserPool

logger = logging.getLogger(__name__)


class SearchTool:
    """Tool for performing web searches."""
    
    def __init__(self, browser_pool: BrowserPool):
        self.browser_pool = browser_pool
    
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform a Google search and return results."""
        logger.info(f"Executing search: {query}")
        
        try:
            results = await self.browser_pool.search(query)
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
