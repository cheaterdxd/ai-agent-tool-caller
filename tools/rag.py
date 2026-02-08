"""RAG tool using LEANN for knowledge storage and retrieval."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LEANNTool:
    """RAG tool using LEANN vector database."""
    
    def __init__(self, index_path: str = "storage/lean_index"):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.index = None
        self._initialize_lean()
    
    def _initialize_lean(self):
        """Initialize LEANN index."""
        try:
            # Import LEANN from submodule
            import sys
            sys.path.insert(0, "external/LEANN")
            from leann import LeannBuilder
            
            self.index = LeannBuilder(str(self.index_path))
            logger.info(f"LEANN index initialized at {self.index_path}")
        except ImportError as e:
            logger.error(f"Failed to import LEANN: {e}")
            self.index = None
        except Exception as e:
            logger.error(f"Error initializing LEANN: {e}")
            self.index = None
    
    async def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a document to the RAG system."""
        if not self.index:
            logger.error("LEANN not initialized")
            return False
        
        try:
            # Check for duplicates (simple hash check)
            doc_hash = hash(content) % 10000000
            
            if metadata is None:
                metadata = {}
            
            metadata['hash'] = doc_hash
            metadata['added_at'] = __import__('datetime').datetime.now().isoformat()
            
            # Add to LEANN
            self.index.add(text=content, metadata=metadata)
            
            logger.info(f"Document added to RAG (hash: {doc_hash})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding document to RAG: {e}")
            return False
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search the RAG system."""
        if not self.index:
            logger.error("LEANN not initialized")
            return []
        
        try:
            results = self.index.search(query=query, top_k=top_k)
            logger.info(f"RAG search found {len(results)} results for '{query}'")
            return results
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return []
    
    async def add_search_results(self, articles: List[Dict[str, Any]]) -> int:
        """Add search results to RAG."""
        added = 0
        for article in articles:
            content = f"{article.get('title', '')}\n{article.get('description', '')}"
            if content.strip():
                success = await self.add_document(
                    content=content,
                    metadata={
                        'url': article.get('url', ''),
                        'title': article.get('title', ''),
                        'source_query': article.get('source_query', ''),
                        'retrieved_at': article.get('retrieved_at', '')
                    }
                )
                if success:
                    added += 1
        
        logger.info(f"Added {added}/{len(articles)} articles to RAG")
        return added
