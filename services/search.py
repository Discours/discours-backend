import asyncio
import json
import logging
import os
import httpx
import time
from collections import defaultdict
from datetime import datetime, timedelta

# Set up proper logging
logger = logging.getLogger("search")
logger.setLevel(logging.INFO)  # Change to INFO to see more details

# Configuration for search service
SEARCH_ENABLED = bool(os.environ.get("SEARCH_ENABLED", "true").lower() in ["true", "1", "yes"])
TXTAI_SERVICE_URL = os.environ.get("TXTAI_SERVICE_URL", "none")
MAX_BATCH_SIZE = int(os.environ.get("SEARCH_MAX_BATCH_SIZE", "25"))

# Search cache configuration
SEARCH_CACHE_ENABLED = bool(os.environ.get("SEARCH_CACHE_ENABLED", "true").lower() in ["true", "1", "yes"])
SEARCH_CACHE_TTL_SECONDS = int(os.environ.get("SEARCH_CACHE_TTL_SECONDS", "900"))  # Default: 15 minutes
SEARCH_MIN_SCORE = float(os.environ.get("SEARCH_MIN_SCORE", "0.1"))
SEARCH_PREFETCH_SIZE = int(os.environ.get("SEARCH_PREFETCH_SIZE", "200"))
SEARCH_USE_REDIS = bool(os.environ.get("SEARCH_USE_REDIS", "true").lower() in ["true", "1", "yes"])

# Import Redis client if Redis caching is enabled
if SEARCH_USE_REDIS:
    try:
        from services.redis import redis
        logger.info("Redis client imported for search caching")
    except ImportError:
        logger.warning("Redis client import failed, falling back to memory cache")
        SEARCH_USE_REDIS = False

class SearchCache:
    """Cache for search results to enable efficient pagination"""
    
    def __init__(self, ttl_seconds=SEARCH_CACHE_TTL_SECONDS, max_items=100):
        self.cache = {}  # Maps search query to list of results
        self.last_accessed = {}  # Maps search query to last access timestamp
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._redis_prefix = "search_cache:"
    
    async def store(self, query, results):
        """Store search results for a query"""
        normalized_query = self._normalize_query(query)
        
        if SEARCH_USE_REDIS:
            try:
                serialized_results = json.dumps(results)
                await redis.set(
                    f"{self._redis_prefix}{normalized_query}", 
                    serialized_results,
                    ex=self.ttl
                )
                logger.info(f"Stored {len(results)} search results for query '{query}' in Redis")
                return True
            except Exception as e:
                logger.error(f"Error storing search results in Redis: {e}")
                # Fall back to memory cache if Redis fails
        
        # First cleanup if needed for memory cache
        if len(self.cache) >= self.max_items:
            self._cleanup()
            
        # Store results and update timestamp
        self.cache[normalized_query] = results
        self.last_accessed[normalized_query] = time.time()
        logger.info(f"Cached {len(results)} search results for query '{query}' in memory")
        return True
    
    async def get(self, query, limit=10, offset=0):
        """Get paginated results for a query"""
        normalized_query = self._normalize_query(query)
        all_results = None

        # Try to get from Redis first
        if SEARCH_USE_REDIS:
            try:
                cached_data = await redis.get(f"{self._redis_prefix}{normalized_query}")
                if cached_data:
                    all_results = json.loads(cached_data)
                    logger.info(f"Retrieved search results for '{query}' from Redis")
                    # Redis TTL is auto-extended when setting the key with expiry
            except Exception as e:
                logger.error(f"Error retrieving search results from Redis: {e}")
        
        # Fall back to memory cache if not in Redis
        if all_results is None and normalized_query in self.cache:
            all_results = self.cache[normalized_query]
            self.last_accessed[normalized_query] = time.time()
            logger.info(f"Retrieved search results for '{query}' from memory cache")
        
        # If not found in any cache
        if all_results is None:
            logger.debug(f"Cache miss for query '{query}'")
            return None
        
        # Return paginated subset
        end_idx = min(offset + limit, len(all_results))
        if offset >= len(all_results):
            logger.warning(f"Requested offset {offset} exceeds result count {len(all_results)}")
            return []
            
        logger.info(f"Cache hit for '{query}': serving {offset}:{end_idx} of {len(all_results)} results")
        return all_results[offset:end_idx]
    
    async def has_query(self, query):
        """Check if query exists in cache"""
        normalized_query = self._normalize_query(query)
        
        # Check Redis first
        if SEARCH_USE_REDIS:
            try:
                exists = await redis.get(f"{self._redis_prefix}{normalized_query}")
                if exists:
                    return True
            except Exception as e:
                logger.error(f"Error checking Redis for query existence: {e}")
        
        # Fall back to memory cache
        return normalized_query in self.cache
    
    async def get_total_count(self, query):
        """Get total count of results for a query"""
        normalized_query = self._normalize_query(query)
        
        # Check Redis first
        if SEARCH_USE_REDIS:
            try:
                cached_data = await redis.get(f"{self._redis_prefix}{normalized_query}")
                if cached_data:
                    all_results = json.loads(cached_data)
                    return len(all_results)
            except Exception as e:
                logger.error(f"Error getting result count from Redis: {e}")
        
        # Fall back to memory cache
        if normalized_query in self.cache:
            return len(self.cache[normalized_query])
            
        return 0
    
    def _normalize_query(self, query):
        """Normalize query string for cache key"""
        if not query:
            return ""
        # Simple normalization - lowercase and strip whitespace
        return query.lower().strip()
    
    def _cleanup(self):
        """Remove oldest entries if memory cache is full"""
        now = time.time()
        # First remove expired entries
        expired_keys = [
            key for key, last_access in self.last_accessed.items() 
            if now - last_access > self.ttl
        ]
        
        for key in expired_keys:
            if key in self.cache:
                del self.cache[key]
            if key in self.last_accessed:
                del self.last_accessed[key]
        
        logger.info(f"Cleaned up {len(expired_keys)} expired search cache entries")
        
        # If still above max size, remove oldest entries
        if len(self.cache) >= self.max_items:
            # Sort by last access time
            sorted_items = sorted(self.last_accessed.items(), key=lambda x: x[1])
            # Remove oldest 20%
            remove_count = max(1, int(len(sorted_items) * 0.2))
            for key, _ in sorted_items[:remove_count]:
                if key in self.cache:
                    del self.cache[key]
                if key in self.last_accessed:
                    del self.last_accessed[key]
            logger.info(f"Removed {remove_count} oldest search cache entries")

class SearchService:
    def __init__(self):
        logger.info(f"Initializing search service with URL: {TXTAI_SERVICE_URL}")
        self.available = SEARCH_ENABLED
        # Use different timeout settings for indexing and search requests
        self.client = httpx.AsyncClient(timeout=30.0, base_url=TXTAI_SERVICE_URL)
        self.index_client = httpx.AsyncClient(timeout=120.0, base_url=TXTAI_SERVICE_URL)
        # Initialize search cache
        self.cache = SearchCache() if SEARCH_CACHE_ENABLED else None
        
        if not self.available:
            logger.info("Search disabled (SEARCH_ENABLED = False)")
        
        if SEARCH_CACHE_ENABLED:
            cache_location = "Redis" if SEARCH_USE_REDIS else "Memory"
            logger.info(f"Search caching enabled using {cache_location} cache with TTL={SEARCH_CACHE_TTL_SECONDS}s")
            logger.info(f"Minimum score filter: {SEARCH_MIN_SCORE}, prefetch size: {SEARCH_PREFETCH_SIZE}")
            
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
    
    async def verify_docs(self, doc_ids):
        """Verify which documents exist in the search index"""
        if not self.available:
            return {"status": "disabled"}
            
        try:
            logger.info(f"Verifying {len(doc_ids)} documents in search index")
            response = await self.client.post(
                "/verify-docs",
                json={"doc_ids": doc_ids},
                timeout=60.0  # Longer timeout for potentially large ID lists
            )
            response.raise_for_status()
            result = response.json()
            
            # Log summary of verification results
            missing_count = len(result.get("missing", []))
            logger.info(f"Document verification complete: {missing_count} missing out of {len(doc_ids)} total")
            
            return result
        except Exception as e:
            logger.error(f"Document verification error: {e}")
            return {"status": "error", "message": str(e)}
    
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
        """Index multiple documents at once with adaptive batch sizing"""
        if not self.available or not shouts:
            logger.warning(f"Bulk indexing skipped: available={self.available}, shouts_count={len(shouts) if shouts else 0}")
            return
        
        start_time = time.time()
        logger.info(f"Starting bulk indexing of {len(shouts)} documents")

        MAX_TEXT_LENGTH = 4000  # Maximum text length to send in a single request
        max_batch_size = MAX_BATCH_SIZE
        total_indexed = 0
        total_skipped = 0
        total_truncated = 0
        total_retries = 0
        
        # Group documents by size to process smaller documents in larger batches
        small_docs = []
        medium_docs = []
        large_docs = []
        
        # First pass: prepare all documents and categorize by size
        for shout in shouts:
            try:
                text_fields = []
                for field_name in ['title', 'subtitle', 'lead', 'body']:
                    field_value = getattr(shout, field_name, None)
                    if field_value and isinstance(field_value, str) and field_value.strip():
                        text_fields.append(field_value.strip())
                
                # Media field processing remains the same
                media = getattr(shout, 'media', None)
                if media:
                    # Your existing media processing logic
                    if isinstance(media, str):
                        try:
                            media_json = json.loads(media)
                            if isinstance(media_json, dict):
                                if 'title' in media_json:
                                    text_fields.append(media_json['title'])
                                if 'body' in media_json:
                                    text_fields.append(media_json['body'])
                        except json.JSONDecodeError:
                            text_fields.append(media)
                    elif isinstance(media, dict):
                        if 'title' in media:
                            text_fields.append(media['title'])
                        if 'body' in media:
                            text_fields.append(media['body'])
                
                text = " ".join(text_fields)
                
                if not text.strip():
                    logger.debug(f"Skipping shout {shout.id}: no text content")
                    total_skipped += 1
                    continue

                # Truncate text if it exceeds the maximum length
                original_length = len(text)
                if original_length > MAX_TEXT_LENGTH:
                    text = text[:MAX_TEXT_LENGTH]
                    logger.info(f"Truncated document {shout.id} from {original_length} to {MAX_TEXT_LENGTH} chars")
                    total_truncated += 1
                
                document = {
                    "id": str(shout.id),
                    "text": text
                }
                
                # Categorize by size
                text_len = len(text)
                if text_len > 5000:
                    large_docs.append(document)
                elif text_len > 2000:
                    medium_docs.append(document)
                else:
                    small_docs.append(document)
                
                total_indexed += 1
                
            except Exception as e:
                logger.error(f"Error processing shout {getattr(shout, 'id', 'unknown')} for indexing: {e}")
                total_skipped += 1
        
        # Process each category with appropriate batch sizes
        logger.info(f"Documents categorized: {len(small_docs)} small, {len(medium_docs)} medium, {len(large_docs)} large")
        
        # Process small documents (larger batches)
        if small_docs:
            batch_size = min(max_batch_size, 15)
            await self._process_document_batches(small_docs, batch_size, "small")
            
        # Process medium documents (medium batches)
        if medium_docs:
            batch_size = min(max_batch_size, 10)
            await self._process_document_batches(medium_docs, batch_size, "medium")
            
        # Process large documents (small batches)
        if large_docs:
            batch_size = min(max_batch_size, 3)
            await self._process_document_batches(large_docs, batch_size, "large")
        
        elapsed = time.time() - start_time
        logger.info(f"Bulk indexing completed in {elapsed:.2f}s: {total_indexed} indexed, {total_skipped} skipped, {total_truncated} truncated, {total_retries} retries")

    async def _process_document_batches(self, documents, batch_size, size_category):
            """Process document batches with retry logic"""
            # Check for possible database corruption before starting
            db_error_count = 0
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i+batch_size]
                batch_id = f"{size_category}-{i//batch_size + 1}"
                logger.info(f"Processing {size_category} batch {batch_id} of {len(batch)} documents")
                
                retry_count = 0
                max_retries = 3
                success = False
                
                # Process with retries
                while not success and retry_count < max_retries:
                    try:
                        if batch:
                            sample = batch[0]
                            logger.info(f"Sample document in batch {batch_id}: id={sample['id']}, text_length={len(sample['text'])}")
                        
                        logger.info(f"Sending batch {batch_id} of {len(batch)} documents to search service (attempt {retry_count+1})")
                        response = await self.index_client.post(
                            "/bulk-index",
                            json=batch,
                            timeout=120.0  # Explicit longer timeout for large batches
                        )
                        
                        # Handle 422 validation errors - these won't be fixed by retrying
                        if response.status_code == 422:
                            error_detail = response.json()
                            truncated_error = self._truncate_error_detail(error_detail)
                            logger.error(f"Validation error from search service for batch {batch_id}: {truncated_error}")
                            break
                        
                        # Handle 500 server errors - these might be fixed by retrying with smaller batches
                        elif response.status_code == 500:
                            db_error_count += 1
                            
                            # If we've seen multiple 500s, log a critical error
                            if db_error_count >= 3:
                                logger.critical(f"Multiple server errors detected (500). The search service may need manual intervention. Stopping batch {batch_id} processing.")
                                break
                                
                            # Try again with exponential backoff
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                wait_time = (2 ** retry_count) + (random.random() * 0.5)  # Exponential backoff with jitter
                                logger.warning(f"Server error for batch {batch_id}, retrying in {wait_time:.1f}s (attempt {retry_count+1}/{max_retries})")
                                await asyncio.sleep(wait_time)
                                continue
                            
                            # Final retry, split the batch
                            elif len(batch) > 1:
                                logger.warning(f"Splitting batch {batch_id} after repeated failures")
                                mid = len(batch) // 2
                                await self._process_single_batch(batch[:mid], f"{batch_id}-A")
                                await self._process_single_batch(batch[mid:], f"{batch_id}-B")
                                break
                            else:
                                # Can't split a single document
                                logger.error(f"Failed to index document {batch[0]['id']} after {max_retries} attempts")
                                break
                        
                        # Normal success case
                        response.raise_for_status()
                        result = response.json()
                        logger.info(f"Batch {batch_id} indexed successfully: {result}")
                        success = True
                        db_error_count = 0  # Reset error counter on success
                        
                    except Exception as e:
                        # Check if it looks like a database corruption error
                        error_str = str(e).lower()
                        if "duplicate key" in error_str or "unique constraint" in error_str or "nonetype" in error_str:
                            db_error_count += 1
                            if db_error_count >= 2:
                                logger.critical(f"Potential database corruption detected: {error_str}. The search service may need manual intervention. Stopping batch {batch_id} processing.")
                                break
                        
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            wait_time = (2 ** retry_count) + (random.random() * 0.5)
                            logger.warning(f"Error for batch {batch_id}, retrying in {wait_time:.1f}s: {str(e)[:200]}")
                            await asyncio.sleep(wait_time)
                        else:
                            # Last resort - try to split the batch
                            if len(batch) > 1:
                                logger.warning(f"Splitting batch {batch_id} after exception: {str(e)[:200]}")
                                mid = len(batch) // 2
                                await self._process_single_batch(batch[:mid], f"{batch_id}-A")
                                await self._process_single_batch(batch[mid:], f"{batch_id}-B")
                            else:
                                logger.error(f"Failed to index document {batch[0]['id']} after {max_retries} attempts: {e}")
                            break

    async def _process_single_batch(self, documents, batch_id):
        """Process a single batch with maximum reliability"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if not documents:
                    return
                    
                logger.info(f"Processing sub-batch {batch_id} with {len(documents)} documents")
                response = await self.index_client.post(
                    "/bulk-index",
                    json=documents,
                    timeout=90.0
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"Sub-batch {batch_id} indexed successfully: {result}")
                return  # Success, exit the retry loop
                
            except Exception as e:
                error_str = str(e).lower()
                retry_count += 1
                
                # Check if it's a transient error that txtai might recover from internally
                if "dictionary changed size" in error_str or "transaction error" in error_str:
                    wait_time = (2 ** retry_count) + (random.random() * 0.5)
                    logger.warning(f"Transient txtai error in sub-batch {batch_id}, waiting {wait_time:.1f}s for recovery: {str(e)[:200]}")
                    await asyncio.sleep(wait_time)  # Wait for txtai to recover
                    continue  # Try again
                
                # For other errors or final retry failure
                logger.error(f"Error indexing sub-batch {batch_id} (attempt {retry_count}/{max_retries}): {str(e)[:200]}")
                
                # Only try one-by-one on the final retry
                if retry_count >= max_retries and len(documents) > 1:
                    logger.info(f"Processing documents in sub-batch {batch_id} individually")
                    for i, doc in enumerate(documents):
                        try:
                            resp = await self.index_client.post("/index", json=doc, timeout=30.0)
                            resp.raise_for_status()
                            logger.info(f"Indexed document {doc['id']} individually")
                        except Exception as e2:
                            logger.error(f"Failed to index document {doc['id']} individually: {str(e2)[:100]}")
                    return  # Exit after individual processing attempt

    def _truncate_error_detail(self, error_detail):
        """Truncate error details for logging"""
        truncated_detail = error_detail.copy() if isinstance(error_detail, dict) else error_detail
        
        if isinstance(truncated_detail, dict) and 'detail' in truncated_detail and isinstance(truncated_detail['detail'], list):
            for i, item in enumerate(truncated_detail['detail']):
                if isinstance(item, dict) and 'input' in item:
                    if isinstance(item['input'], dict) and any(k in item['input'] for k in ['documents', 'text']):
                        # Check for documents list
                        if 'documents' in item['input'] and isinstance(item['input']['documents'], list):
                            for j, doc in enumerate(item['input']['documents']):
                                if 'text' in doc and isinstance(doc['text'], str) and len(doc['text']) > 100:
                                    item['input']['documents'][j]['text'] = f"{doc['text'][:100]}... [truncated, total {len(doc['text'])} chars]"
                        
                        # Check for direct text field
                        if 'text' in item['input'] and isinstance(item['input']['text'], str) and len(item['input']['text']) > 100:
                            item['input']['text'] = f"{item['input']['text'][:100]}... [truncated, total {len(item['input']['text'])} chars]"
        
        return truncated_detail

    async def search(self, text, limit, offset):
        """Search documents"""
        if not self.available:
            logger.warning("Search not available")
            return []
        
        if not isinstance(text, str) or not text.strip():
            logger.warning(f"Invalid search text: {text}")
            return []
            
        logger.info(f"Searching for: '{text}' (limit={limit}, offset={offset})")
        
        # Check if we can serve from cache
        if SEARCH_CACHE_ENABLED:
            has_cache = await self.cache.has_query(text)
            if has_cache:
                cached_results = await self.cache.get(text, limit, offset)
                if cached_results is not None:
                    logger.info(f"Serving search results for '{text}' from cache (offset={offset}, limit={limit})")
                    return cached_results
        
        # Not in cache or cache disabled, perform new search
        try:
            search_limit = limit
            search_offset = offset
            
            # If cache is enabled, prefetch more results to store in cache
            if SEARCH_CACHE_ENABLED and offset == 0:
                search_limit = SEARCH_PREFETCH_SIZE  # Fetch more results to cache
                search_offset = 0  # Always start from beginning for cache
                
            logger.info(f"Sending search request: text='{text}', limit={search_limit}, offset={search_offset}")
            response = await self.client.post(
                "/search",
                json={"text": text, "limit": search_limit, "offset": search_offset}
            )
            response.raise_for_status()
            
            logger.info(f"Raw search response: {response.text}")
            result = response.json()
            logger.info(f"Parsed search response: {result}")
            
            formatted_results = result.get("results", [])
            
            # Filter out non-numeric IDs to prevent database errors
            valid_results = []
            for item in formatted_results:
                doc_id = item.get("id")
                if doc_id and doc_id.isdigit():
                    valid_results.append(item)
                else:
                    logger.warning(f"Filtered out non-numeric document ID: {doc_id}")
            
            if len(valid_results) != len(formatted_results):
                logger.info(f"Filtered {len(formatted_results) - len(valid_results)} results with non-numeric IDs")
                formatted_results = valid_results
                
            # Filter out low-score results
            if SEARCH_MIN_SCORE > 0:
                initial_count = len(formatted_results)
                formatted_results = [r for r in formatted_results if r.get("score", 0) >= SEARCH_MIN_SCORE]
                if len(formatted_results) != initial_count:
                    logger.info(f"Filtered {initial_count - len(formatted_results)} results with score < {SEARCH_MIN_SCORE}")
            
            logger.info(f"Search for '{text}' returned {len(formatted_results)} valid results")
            
            if formatted_results:
                logger.info(f"Sample result: {formatted_results[0]}")
            else:
                logger.warning(f"No results found for '{text}'")
            
            # Store full results in cache if caching is enabled
            if SEARCH_CACHE_ENABLED and offset == 0:
                # Store normal sorted results
                await self.cache.store(text, formatted_results)
                
                # Return only the requested page
                if limit < len(formatted_results):
                    page_results = formatted_results[:limit]
                    logger.info(f"Returning first page of {len(page_results)} results " +
                                f"(out of {len(formatted_results)} total)")
                    return page_results
                    
            return formatted_results
        except Exception as e:
            logger.error(f"Search error for '{text}': {e}", exc_info=True)
            return []
    
    async def check_index_status(self):
        """Get detailed statistics about the search index health"""
        if not self.available:
            return {"status": "disabled"}
            
        try:
            response = await self.client.get("/index-status")
            response.raise_for_status()
            result = response.json()
            logger.info(f"Index status check: {result['status']}, {result['documents_count']} documents")
            
            # Log warnings for any inconsistencies
            if result.get("consistency", {}).get("status") != "ok":
                null_count = result.get("consistency", {}).get("null_embeddings_count", 0)
                if null_count > 0:
                    logger.warning(f"Found {null_count} documents with NULL embeddings")
                    
            return result
        except Exception as e:
            logger.error(f"Failed to check index status: {e}")
            return {"status": "error", "message": str(e)}

# Create the search service singleton
search_service = SearchService()

# API-compatible function to perform a search
async def search_text(text: str, limit: int = 50, offset: int = 0):
    payload = []
    if search_service.available:
        payload = await search_service.search(text, limit, offset)
    return payload

async def get_search_count(text: str):
    """Get total count of results for a query without fetching all results"""
    if search_service.available and SEARCH_CACHE_ENABLED:
        if await search_service.cache.has_query(text):
            return await search_service.cache.get_total_count(text)
    # If not cached, we'll need to perform the full search once
    results = await search_text(text, SEARCH_PREFETCH_SIZE, 0)
    return len(results)

async def initialize_search_index(shouts_data):
    """Initialize search index with existing data during application startup"""
    if not SEARCH_ENABLED:
        logger.info("Search indexing skipped (SEARCH_ENABLED=False)")
        return
        
    if not shouts_data:
        logger.warning("No shouts data provided for search indexing")
        return
        
    logger.info(f"Checking search index status for {len(shouts_data)} documents")
    
    # Get the current index info
    info = await search_service.info()
    if info.get("status") in ["error", "unavailable", "disabled"]:
        logger.error(f"Cannot initialize search index: {info}")
        return
    
    # Check if index has approximately right number of documents
    index_stats = info.get("index_stats", {})
    indexed_doc_count = index_stats.get("document_count", 0)

    # Add a more detailed status check
    index_status = await search_service.check_index_status()
    if index_status.get("status") == "healthy":
        logger.info("Index status check passed")
    elif index_status.get("status") == "inconsistent":
        logger.warning("Index status check found inconsistencies")
        
        # Get documents with null embeddings
        problem_ids = index_status.get("consistency", {}).get("null_embeddings_sample", [])
                
        if problem_ids:
            logger.info(f"Repairing {len(problem_ids)} documents with NULL embeddings")
            problem_docs = [shout for shout in shouts_data if str(shout.id) in problem_ids]
            if problem_docs:
                await search_service.bulk_index(problem_docs)
    
    # Log database document summary
    db_ids = [str(shout.id) for shout in shouts_data]
    logger.info(f"Database contains {len(shouts_data)} documents. Sample IDs: {', '.join(db_ids[:5])}...")
    
    # Calculate summary by ID range to understand the coverage
    try:
        # Parse numeric IDs where possible to analyze coverage
        numeric_ids = [int(sid) for sid in db_ids if sid.isdigit()]
        if numeric_ids:
            min_id = min(numeric_ids)
            max_id = max(numeric_ids)
            id_range = max_id - min_id + 1
            coverage_pct = (len(numeric_ids) / id_range) * 100 if id_range > 0 else 0
            logger.info(f"ID range analysis: min_id={min_id}, max_id={max_id}, range={id_range}, " 
                        f"coverage={coverage_pct:.1f}% ({len(numeric_ids)}/{id_range})")
    except Exception as e:
        logger.warning(f"Could not analyze ID ranges: {e}")
    
    # If counts are significantly different, do verification
    if abs(indexed_doc_count - len(shouts_data)) > 10:
        logger.info(f"Document count mismatch: {indexed_doc_count} in index vs {len(shouts_data)} in database. Verifying...")
        
        # Get all document IDs from your database
        doc_ids = [str(shout.id) for shout in shouts_data]
        
        # Verify which ones are missing from the index
        verification = await search_service.verify_docs(doc_ids)
        
        if verification.get("status") == "error":
            logger.error(f"Document verification failed: {verification.get('message')}")
            return
            
        # Index only missing documents
        missing_ids = verification.get("missing", [])
        if missing_ids:
            logger.info(f"Found {len(missing_ids)} documents missing from index. Indexing them...")
            logger.info(f"Sample missing IDs: {', '.join(missing_ids[:10])}...")
            missing_docs = [shout for shout in shouts_data if str(shout.id) in missing_ids]
            await search_service.bulk_index(missing_docs)
        else:
            logger.info("All documents are already indexed.")
    else:
        logger.info(f"Search index appears to be in sync ({indexed_doc_count} documents indexed).")
        
        # Optional sample verification (can be slow with large document sets)
        # Uncomment if you want to periodically check a random sample even when counts match
        """
        sample_size = 10
        if len(db_ids) > sample_size:
            sample_ids = random.sample(db_ids, sample_size)
            logger.info(f"Performing random sample verification on {sample_size} documents...")
            verification = await search_service.verify_docs(sample_ids)
            if verification.get("missing"):
                missing_count = len(verification.get("missing", []))
                logger.warning(f"Random verification found {missing_count}/{sample_size} missing docs " 
                              f"despite count match. Consider full verification.")
            else:
                logger.info("Random document sample verification passed.")
        """
    
    # Verify with test query
    try:
        test_query = "test"
        logger.info(f"Verifying search index with query: '{test_query}'")
        test_results = await search_text(test_query, 5)
        
        if test_results:
            logger.info(f"Search verification successful: found {len(test_results)} results")
            # Log categories covered by search results
            categories = set()
            for result in test_results:
                result_id = result.get("id")
                matching_shouts = [s for s in shouts_data if str(s.id) == result_id]
                if matching_shouts and hasattr(matching_shouts[0], 'category'):
                    categories.add(getattr(matching_shouts[0], 'category', 'unknown'))
            if categories:
                logger.info(f"Search results cover categories: {', '.join(categories)}")
        else:
            logger.warning("Search verification returned no results. Index may be empty or not working.")
    except Exception as e:
        logger.error(f"Error verifying search index: {e}")
