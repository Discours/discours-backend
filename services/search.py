import asyncio
import json
import logging
import os
import concurrent.futures

from txtai.embeddings import Embeddings

from services.redis import redis
from utils.encoders import CustomJSONEncoder

# Set redis logging level to suppress DEBUG messages
logger = logging.getLogger("search")
logger.setLevel(logging.WARNING)

REDIS_TTL = 86400  # 1 день в секундах

# Configuration for txtai search
SEARCH_ENABLED = bool(os.environ.get("SEARCH_ENABLED", "true").lower() in ["true", "1", "yes"])
# Thread executor for non-blocking initialization
thread_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


class SearchService:
    def __init__(self, index_name="search_index"):
        logger.info("Инициализируем поиск...")
        self.index_name = index_name
        self.embeddings = None
        self._initialization_future = None
        self.available = SEARCH_ENABLED
        
        if not self.available:
            logger.info("Поиск отключен (SEARCH_ENABLED = False)")
            return
            
        # Initialize embeddings in background thread
        self._initialization_future = thread_executor.submit(self._init_embeddings)
        
    def _init_embeddings(self):
        """Initialize txtai embeddings in a background thread"""
        try:
            # Use the same model as in TopicClassifier
            model_path = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
            
            # Configure embeddings with content storage and quantization for lower memory usage
            self.embeddings = Embeddings({
                "path": model_path,
                "content": True,
                "quantize": True
            })
            logger.info("txtai embeddings initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize txtai embeddings: {e}")
            self.available = False
            return False

    async def info(self):
        """Return information about search service"""
        if not self.available:
            return {"status": "disabled"}

        try:
            if not self.is_ready():
                return {"status": "initializing", "model": "paraphrase-multilingual-mpnet-base-v2"}
                
            return {
                "status": "active",
                "count": len(self.embeddings) if self.embeddings else 0,
                "model": "paraphrase-multilingual-mpnet-base-v2"
            }
        except Exception as e:
            logger.error(f"Failed to get search info: {e}")
            return {"status": "error", "message": str(e)}

    def is_ready(self):
        """Check if embeddings are fully initialized and ready"""
        return self.embeddings is not None and self.available

    def index(self, shout):
        """Index a single document"""
        if not self.available:
            return

        logger.info(f"Индексируем пост {shout.id}")
        
        # Start in background to not block
        asyncio.create_task(self.perform_index(shout))

    async def perform_index(self, shout):
        """Actually perform the indexing operation"""
        if not self.is_ready():
            # If embeddings not ready, wait for initialization
            if self._initialization_future and not self._initialization_future.done():
                try:
                    # Wait for initialization to complete with timeout
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self._initialization_future.result(timeout=30))
                except Exception as e:
                    logger.error(f"Embeddings initialization failed: {e}")
                    return
            
            if not self.is_ready():
                logger.error(f"Cannot index shout {shout.id}: embeddings not ready")
                return
        
        try:
            # Combine all text fields
            text = " ".join(filter(None, [
                shout.title or "", 
                shout.subtitle or "", 
                shout.lead or "", 
                shout.body or "",
                shout.media or ""
            ]))
            
            # Use upsert for individual documents
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.embeddings.upsert([(str(shout.id), text, None)])
            )
            logger.info(f"Пост {shout.id} успешно индексирован")
        except Exception as e:
            logger.error(f"Indexing error for shout {shout.id}: {e}")

    async def bulk_index(self, shouts):
        """Index multiple documents at once"""
        if not self.available or not shouts:
            return
            
        if not self.is_ready():
            # Wait for initialization if needed
            if self._initialization_future and not self._initialization_future.done():
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self._initialization_future.result(timeout=30))
                except Exception as e:
                    logger.error(f"Embeddings initialization failed: {e}")
                    return
            
            if not self.is_ready():
                logger.error("Cannot perform bulk indexing: embeddings not ready")
                return
                
        documents = []
        for shout in shouts:
            text = " ".join(filter(None, [
                shout.title or "", 
                shout.subtitle or "", 
                shout.lead or "", 
                shout.body or "",
                shout.media or ""
            ]))
            documents.append((str(shout.id), text, None))
            
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.embeddings.upsert(documents))
            logger.info(f"Bulk indexed {len(documents)} documents")
        except Exception as e:
            logger.error(f"Bulk indexing error: {e}")

    async def search(self, text, limit, offset):
        """Search documents"""
        if not self.available:
            return []
            
        # Check Redis cache first
        redis_key = f"search:{text}:{offset}+{limit}"
        cached = await redis.get(redis_key)
        if cached:
            return json.loads(cached)
            
        logger.info(f"Ищем: {text} {offset}+{limit}")
        
        if not self.is_ready():
            # Wait for initialization if needed
            if self._initialization_future and not self._initialization_future.done():
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self._initialization_future.result(timeout=30))
                except Exception as e:
                    logger.error(f"Embeddings initialization failed: {e}")
                    return []
            
            if not self.is_ready():
                logger.error("Cannot search: embeddings not ready")
                return []
        
        try:
            # Search with txtai (need to request more to handle offset)
            total = offset + limit
            results = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.embeddings.search(text, total))
            
            # Apply offset and convert to the expected format
            results = results[offset:offset+limit]
            formatted_results = [{"id": doc_id, "score": float(score)} for score, doc_id in results]
            
            # Cache results
            if formatted_results:
                await redis.execute(
                    "SETEX",
                    redis_key,
                    REDIS_TTL,
                    json.dumps(formatted_results, cls=CustomJSONEncoder),
                )
            return formatted_results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []


# Create the search service singleton
search_service = SearchService()


# Keep the API exactly the same to maintain compatibility
async def search_text(text: str, limit: int = 50, offset: int = 0):
    payload = []
    if search_service.available:
        payload = await search_service.search(text, limit, offset)
    return payload


# Function to initialize search with existing data
async def initialize_search_index(shouts_data):
    """Initialize search index with existing data during application startup"""
    if SEARCH_ENABLED:
        logger.info("Initializing search index with existing data...")
        await search_service.bulk_index(shouts_data)
        logger.info(f"Search index initialized with {len(shouts_data)} documents")
