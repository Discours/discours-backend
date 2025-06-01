import asyncio
import concurrent.futures
from concurrent.futures import Future
from typing import Any, Optional

try:
    from utils.logger import root_logger as logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class PreTopicService:
    def __init__(self) -> None:
        self.topic_embeddings: Optional[Any] = None
        self.search_embeddings: Optional[Any] = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._initialization_future: Optional[Future[None]] = None

    def _ensure_initialization(self) -> None:
        """Ensure embeddings are initialized"""
        if self._initialization_future is None:
            self._initialization_future = self._executor.submit(self._prepare_embeddings)

    def _prepare_embeddings(self) -> None:
        """Prepare embeddings for topic and search functionality"""
        try:
            from txtai.embeddings import Embeddings  # type: ignore[import-untyped]

            # Initialize topic embeddings
            self.topic_embeddings = Embeddings(
                {
                    "method": "transformers",
                    "path": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                }
            )

            # Initialize search embeddings
            self.search_embeddings = Embeddings(
                {
                    "method": "transformers",
                    "path": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                }
            )
            logger.info("PreTopic embeddings initialized successfully")
        except ImportError:
            logger.warning("txtai.embeddings not available, PreTopicService disabled")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")

    async def suggest_topics(self, text: str) -> list[dict[str, Any]]:
        """Suggest topics based on text content"""
        if self.topic_embeddings is None:
            return []

        try:
            self._ensure_initialization()
            if self._initialization_future:
                await asyncio.wrap_future(self._initialization_future)

            if self.topic_embeddings is not None:
                results = self.topic_embeddings.search(text, 1)
                if results:
                    return [{"topic": result["text"], "score": result["score"]} for result in results]
        except Exception as e:
            logger.error(f"Error suggesting topics: {e}")
        return []

    async def search_content(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search content using embeddings"""
        if self.search_embeddings is None:
            return []

        try:
            self._ensure_initialization()
            if self._initialization_future:
                await asyncio.wrap_future(self._initialization_future)

            if self.search_embeddings is not None:
                results = self.search_embeddings.search(query, limit)
                if results:
                    return [{"content": result["text"], "score": result["score"]} for result in results]
        except Exception as e:
            logger.error(f"Error searching content: {e}")
        return []


# Global instance
pretopic_service = PreTopicService()
