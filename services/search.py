import asyncio
import json
import logging
import os
import httpx

from services.redis import redis
from utils.encoders import CustomJSONEncoder

# Set redis logging level to suppress DEBUG messages
logger = logging.getLogger("search")
logger.setLevel(logging.WARNING)

REDIS_TTL = 86400  # 1 day in seconds

# Configuration for search service
SEARCH_ENABLED = bool(os.environ.get("SEARCH_ENABLED", "true").lower() in ["true", "1", "yes"])
TXTAI_SERVICE_URL = os.environ.get("TXTAI_SERVICE_URL", "http://txtai-service:8000")


class SearchService:
    def __init__(self):
        logger.info("Initializing search service...")
        self.available = SEARCH_ENABLED
        self.client = httpx.AsyncClient(timeout=30.0, base_url=TXTAI_SERVICE_URL)
        
        if not self.available:
            logger.info("Search disabled (SEARCH_ENABLED = False)")
            
    async def info(self):
        """Return information about search service"""
        if not self.available:
            return {"status": "disabled"}

        try:
            response = await self.client.get("/info")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get search info: {e}")
            return {"status": "error", "message": str(e)}

    def is_ready(self):
        """Check if service is available"""
        return self.available

    def index(self, shout):
        """Index a single document"""
        if not self.available:
            return

        logger.info(f"Indexing post {shout.id}")
        
        # Start in background to not block
        asyncio.create_task(self.perform_index(shout))

    async def perform_index(self, shout):
        """Actually perform the indexing operation"""
        if not self.available:
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
            
            # Send to txtai service
            response = await self.client.post(
                "/index",
                json={"id": str(shout.id), "text": text}
            )
            response.raise_for_status()
            logger.info(f"Post {shout.id} successfully indexed")
        except Exception as e:
            logger.error(f"Indexing error for shout {shout.id}: {e}")

    async def bulk_index(self, shouts):
        """Index multiple documents at once"""
        if not self.available or not shouts:
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
            documents.append({"id": str(shout.id), "text": text})
            
        try:
            response = await self.client.post(
                "/bulk-index",
                json={"documents": documents}
            )
            response.raise_for_status()
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
            
        logger.info(f"Searching: {text} {offset}+{limit}")
        
        try:
            response = await self.client.post(
                "/search",
                json={"text": text, "limit": limit, "offset": offset}
            )
            response.raise_for_status()
            result = response.json()
            formatted_results = result.get("results", [])
            
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