import asyncio
import json
import logging
import os
import httpx
import time
import random

# Set up proper logging
logger = logging.getLogger("search")
logger.setLevel(logging.INFO)  # Change to INFO to see more details

# Configuration for search service
SEARCH_ENABLED = bool(os.environ.get("SEARCH_ENABLED", "true").lower() in ["true", "1", "yes"])
TXTAI_SERVICE_URL = os.environ.get("TXTAI_SERVICE_URL", "none")
MAX_BATCH_SIZE = int(os.environ.get("SEARCH_MAX_BATCH_SIZE", "25"))


class SearchService:
    def __init__(self):
        logger.info(f"Initializing search service with URL: {TXTAI_SERVICE_URL}")
        self.available = SEARCH_ENABLED
        # Use different timeout settings for indexing and search requests
        self.client = httpx.AsyncClient(timeout=30.0, base_url=TXTAI_SERVICE_URL)
        self.index_client = httpx.AsyncClient(timeout=120.0, base_url=TXTAI_SERVICE_URL)

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
            
        try:
            logger.info(f"Sending search request: text='{text}', limit={limit}, offset={offset}")
            response = await self.client.post(
                "/search",
                json={"text": text, "limit": limit, "offset": offset}
            )
            response.raise_for_status()
            
            logger.info(f"Raw search response: {response.text}")
            result = response.json()
            logger.info(f"Parsed search response: {result}")
            
            formatted_results = result.get("results", [])
            logger.info(f"Search for '{text}' returned {len(formatted_results)} results")
            
            if formatted_results:
                logger.info(f"Sample result: {formatted_results[0]}")
            else:
                logger.warning(f"No results found for '{text}'")
            
            return formatted_results
        except Exception as e:
            logger.error(f"Search error for '{text}': {e}", exc_info=True)
            return []


# Create the search service singleton
search_service = SearchService()


# API-compatible function to perform a search
async def search_text(text: str, limit: int = 50, offset: int = 0):
    payload = []
    if search_service.available:
        payload = await search_service.search(text, limit, offset)
    return payload


async def initialize_search_index(shouts_data):
    """Initialize search index with existing data during application startup"""
    if SEARCH_ENABLED:
        if not shouts_data:
            logger.warning("No shouts data provided for search indexing")
            return
            
        logger.info(f"Initializing search index with {len(shouts_data)} documents")
        
        info = await search_service.info()
        if info.get("status") in ["error", "unavailable", "disabled"]:
            logger.error(f"Cannot initialize search index: {info}")
            return
        
        await search_service.bulk_index(shouts_data)
        
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
