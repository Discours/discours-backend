import asyncio
import json
import logging
import os
import httpx
import time

from services.redis import redis
from utils.encoders import CustomJSONEncoder

# Set up proper logging
logger = logging.getLogger("search")
logger.setLevel(logging.INFO)  # Change to INFO to see more details

REDIS_TTL = 86400  # 1 day in seconds

# Configuration for search service
SEARCH_ENABLED = bool(os.environ.get("SEARCH_ENABLED", "true").lower() in ["true", "1", "yes"])
TXTAI_SERVICE_URL = os.environ.get("TXTAI_SERVICE_URL", "http://search-txtai.web.1:8000")
MAX_BATCH_SIZE = int(os.environ.get("SEARCH_MAX_BATCH_SIZE", "100"))


class SearchService:
    def __init__(self):
        logger.info(f"Initializing search service with URL: {TXTAI_SERVICE_URL}")
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
            result = response.json()
            logger.info(f"Search service info: {result}")
            return result
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
            
            if not text.strip():
                logger.warning(f"No text content to index for shout {shout.id}")
                return
                
            # Log the document being indexed
            logger.info(f"Indexing document: ID={shout.id}, Text length={len(text)}")
            
            # Send to txtai service
            response = await self.client.post(
                "/index",
                json={"id": str(shout.id), "text": text}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Post {shout.id} successfully indexed: {result}")
        except Exception as e:
            logger.error(f"Indexing error for shout {shout.id}: {e}")

    async def bulk_index(self, shouts):
        """Index multiple documents at once"""
        if not self.available or not shouts:
            logger.warning(f"Bulk indexing skipped: available={self.available}, shouts_count={len(shouts) if shouts else 0}")
            return
        
        start_time = time.time()
        logger.info(f"Starting bulk indexing of {len(shouts)} documents")
                
        # Process documents in batches
        batch_size = MAX_BATCH_SIZE
        total_indexed = 0
        total_skipped = 0
        
        for i in range(0, len(shouts), batch_size):
            batch = shouts[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} of {(len(shouts)-1)//batch_size + 1}, size {len(batch)}")
            
            documents = []
            for shout in batch:
                try:
                    # Clean and combine all text fields
                    text_fields = []
                    for field_name in ['title', 'subtitle', 'lead', 'body']:
                        field_value = getattr(shout, field_name, None)
                        if field_value and isinstance(field_value, str) and field_value.strip():
                            text_fields.append(field_value.strip())
                    
                    # Process media field if it exists
                    media = getattr(shout, 'media', None)
                    if media:
                        if isinstance(media, str):
                            # Try to parse if it's JSON
                            try:
                                media_json = json.loads(media)
                                if isinstance(media_json, dict) and 'title' in media_json:
                                    text_fields.append(media_json['title'])
                                if isinstance(media_json, dict) and 'body' in media_json:
                                    text_fields.append(media_json['body'])
                            except json.JSONDecodeError:
                                text_fields.append(media)
                        elif isinstance(media, dict):
                            if 'title' in media:
                                text_fields.append(media['title'])
                            if 'body' in media:
                                text_fields.append(media['body'])
                    
                    # Combine fields into one text
                    text = " ".join(text_fields)
                    
                    if not text.strip():
                        logger.debug(f"Skipping shout {shout.id}: no text content")
                        total_skipped += 1
                        continue
                        
                    # Add to batch
                    documents.append({
                        "id": str(shout.id),
                        "text": text
                    })
                    total_indexed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing shout {getattr(shout, 'id', 'unknown')} for indexing: {e}")
                    total_skipped += 1
            
            if not documents:
                logger.warning(f"No valid documents in batch {i//batch_size + 1}")
                continue
                
            try:
                # Log a sample of the batch for debugging
                if documents:
                    sample = documents[0]
                    logger.info(f"Sample document: id={sample['id']}, text_length={len(sample['text'])}")
                
                # Send batch to txtai service
                logger.info(f"Sending batch of {len(documents)} documents to search service")
                response = await self.client.post(
                    "/bulk-index",
                    json={"documents": documents}
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"Batch {i//batch_size + 1} indexed successfully: {result}")
            except Exception as e:
                logger.error(f"Bulk indexing error for batch {i//batch_size + 1}: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"Bulk indexing completed in {elapsed:.2f}s: {total_indexed} indexed, {total_skipped} skipped")

    async def search(self, text, limit, offset):
        """Search documents"""
        if not self.available:
            logger.warning("Search not available")
            return []
        
        # Validate input
        if not isinstance(text, str) or not text.strip():
            logger.warning(f"Invalid search text: {text}")
            return []
            
        logger.info(f"Searching for: '{text}' (limit={limit}, offset={offset})")
            
        # Check Redis cache first
        redis_key = f"search:{text}:{offset}+{limit}"
        cached = await redis.get(redis_key)
        if cached:
            cached_results = json.loads(cached)
            logger.info(f"Retrieved {len(cached_results)} results from cache for '{text}'")
            return cached_results
        
        try:
            # Log request
            logger.info(f"Sending search request: text='{text}', limit={limit}, offset={offset}")
            
            # Send search request to txtai service
            response = await self.client.post(
                "/search",
                json={"text": text, "limit": limit, "offset": offset}
            )
            response.raise_for_status()
            
            # Log raw response for debugging
            logger.info(f"Raw search response: {response.text}")
            
            # Parse response
            result = response.json()
            logger.info(f"Parsed search response: {result}")
            
            # Extract results
            formatted_results = result.get("results", [])
            logger.info(f"Search for '{text}' returned {len(formatted_results)} results")
            
            # Log sample results for debugging
            if formatted_results:
                logger.info(f"Sample result: {formatted_results[0]}")
            else:
                logger.warning(f"No results found for '{text}'")
            
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
            logger.error(f"Search error for '{text}': {e}", exc_info=True)
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
        if not shouts_data:
            logger.warning("No shouts data provided for search indexing")
            return
            
        logger.info(f"Initializing search index with {len(shouts_data)} documents")
        
        # Check if search service is available first
        info = await search_service.info()
        if info.get("status") in ["error", "unavailable", "disabled"]:
            logger.error(f"Cannot initialize search index: {info}")
            return
        
        # Start the bulk indexing process
        await search_service.bulk_index(shouts_data)
        
        # Verify indexing worked by testing with a search
        try:
            test_query = "test"
            logger.info(f"Verifying search index with query: '{test_query}'")
            test_results = await search_text(test_query, 5)
            
            if test_results:
                logger.info(f"Search verification successful: found {len(test_results)} results")
            else:
                logger.warning("Search verification returned no results. Index may be empty or not working.")
        except Exception as e:
            logger.error(f"Error verifying search index: {e}")
    else:
        logger.info("Search indexing skipped (SEARCH_ENABLED=False)")