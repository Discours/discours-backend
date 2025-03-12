import asyncio
import json
import logging
import os
import httpx
from typing import List, Dict, Any, Optional

from services.redis import redis
from utils.encoders import CustomJSONEncoder

# Set redis logging level to suppress DEBUG messages
logger = logging.getLogger("search")
logger.setLevel(logging.WARNING)

REDIS_TTL = 86400  # 1 day in seconds

# Configuration for search service
SEARCH_ENABLED = bool(os.environ.get("SEARCH_ENABLED", "true").lower() in ["true", "1", "yes"])
TXTAI_SERVICE_URL = os.environ.get("TXTAI_SERVICE_URL")
# Add retry configuration
MAX_RETRIES = int(os.environ.get("TXTAI_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("TXTAI_RETRY_DELAY", "1.0"))
# Add request timeout configuration
REQUEST_TIMEOUT = float(os.environ.get("TXTAI_REQUEST_TIMEOUT", "30.0"))
# Add health check configuration
HEALTH_CHECK_INTERVAL = int(os.environ.get("SEARCH_HEALTH_CHECK_INTERVAL", "300"))  # 5 minutes


class SearchService:
    def __init__(self):
        logger.info(f"Initializing search service with URL: {TXTAI_SERVICE_URL}")
        self.available = SEARCH_ENABLED
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT, base_url=TXTAI_SERVICE_URL)
        self.last_health_check = 0
        self.health_status = False
        
        if not self.available:
            logger.info("Search disabled (SEARCH_ENABLED = False)")
        
        # Schedule health check if enabled
        if self.available:
            asyncio.create_task(self._schedule_health_checks())
            
    async def _schedule_health_checks(self):
        """Schedule periodic health checks"""
        while True:
            try:
                await self._check_health()
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error in health check scheduler: {e}")
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                
    async def _check_health(self):
        """Check if search service is healthy"""
        try:
            info = await self.info()
            self.health_status = info.get("status") != "error"
            if self.health_status:
                logger.info("Search service is healthy")
            else:
                logger.warning("Search service is unhealthy")
            return self.health_status
        except Exception as e:
            self.health_status = False
            logger.warning(f"Search health check failed: {e}")
            return False
            
    async def _retry_operation(self, operation_func, *args, **kwargs):
        """Execute an operation with retries"""
        if not self.available:
            return None
            
        for attempt in range(MAX_RETRIES):
            try:
                return await operation_func(*args, **kwargs)
            except httpx.ReadTimeout:
                if attempt == MAX_RETRIES - 1:
                    raise
                logger.warning(f"Request timed out, retrying ({attempt+1}/{MAX_RETRIES})")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except httpx.ConnectError as e:
                if attempt == MAX_RETRIES - 1:
                    self.available = False
                    logger.error(f"Connection error after {MAX_RETRIES} attempts: {e}")
                    raise
                logger.warning(f"Connection error, retrying ({attempt+1}/{MAX_RETRIES}): {e}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                logger.warning(f"Error, retrying ({attempt+1}/{MAX_RETRIES}): {e}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        
        return None  # Should not reach here

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
        return self.available and self.health_status

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
            
            # Send to txtai service with retry
            await self._retry_operation(
                self._perform_index_request,
                str(shout.id),
                text
            )
            logger.info(f"Post {shout.id} successfully indexed")
        except Exception as e:
            logger.error(f"Indexing error for shout {shout.id}: {e}")
            
    async def _perform_index_request(self, id, text):
        """Execute the actual index request"""
        response = await self.client.post(
            "/index",
            json={"id": id, "text": text}
        )
        response.raise_for_status()
        return response.json()

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
            # Using chunking to avoid large requests
            chunk_size = 100  # Adjust based on your needs
            for i in range(0, len(documents), chunk_size):
                chunk = documents[i:i+chunk_size]
                logger.info(f"Bulk indexing chunk {i//chunk_size + 1}/{(len(documents)-1)//chunk_size + 1} ({len(chunk)} documents)")
                
                await self._retry_operation(
                    self._perform_bulk_index_request,
                    chunk
                )
            
            logger.info(f"Bulk indexed {len(documents)} documents in total")
        except Exception as e:
            logger.error(f"Bulk indexing error: {e}")
            
    async def _perform_bulk_index_request(self, documents):
        """Execute the actual bulk index request"""
        response = await self.client.post(
            "/bulk-index",
            json={"documents": documents}
        )
        response.raise_for_status()
        return response.json()

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
            result = await self._retry_operation(
                self._perform_search_request,
                text, 
                limit, 
                offset
            )
            
            if not result:
                return []
                
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
            
    async def _perform_search_request(self, text, limit, offset):
        """Execute the actual search request"""
        response = await self.client.post(
            "/search",
            json={"text": text, "limit": limit, "offset": offset}
        )
        response.raise_for_status()
        return response.json()


# Create the search service singleton
search_service = SearchService()


# Keep the API exactly the same to maintain compatibility
async def search_text(text: str, limit: int = 50, offset: int = 0):
    payload = []
    if search_service.available:
        payload = await search_service.search(text, limit, offset)
    return payload


# Function to initialize search index with existing data
async def initialize_search_index(shouts_data):
    """Initialize search index with existing data during application startup"""
    if SEARCH_ENABLED:
        logger.info("Initializing search index with existing data...")
        await search_service.bulk_index(shouts_data)
        logger.info(f"Search index initialized with {len(shouts_data)} documents")