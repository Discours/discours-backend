import asyncio
import json
import logging
import os
import secrets
import time
from typing import Any, Optional, cast

from httpx import AsyncClient, Response

# Set up proper logging
logger = logging.getLogger("search")
logger.setLevel(logging.INFO)  # Change to INFO to see more details
# Disable noise HTTP client logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Configuration for search service
SEARCH_ENABLED = bool(os.environ.get("SEARCH_ENABLED", "true").lower() in ["true", "1", "yes"])
TXTAI_SERVICE_URL = os.environ.get("TXTAI_SERVICE_URL", "none")
MAX_BATCH_SIZE = int(os.environ.get("SEARCH_MAX_BATCH_SIZE", "25"))

# Search cache configuration
SEARCH_CACHE_ENABLED = bool(os.environ.get("SEARCH_CACHE_ENABLED", "true").lower() in ["true", "1", "yes"])
SEARCH_CACHE_TTL_SECONDS = int(os.environ.get("SEARCH_CACHE_TTL_SECONDS", "300"))  # Default: 15 minutes
SEARCH_PREFETCH_SIZE = int(os.environ.get("SEARCH_PREFETCH_SIZE", "200"))
SEARCH_USE_REDIS = bool(os.environ.get("SEARCH_USE_REDIS", "true").lower() in ["true", "1", "yes"])

search_offset = 0

# Глобальная коллекция для фоновых задач
background_tasks = []

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

    def __init__(self, ttl_seconds: int = SEARCH_CACHE_TTL_SECONDS, max_items: int = 100) -> None:
        self.cache: dict[str, list] = {}  # Maps search query to list of results
        self.last_accessed: dict[str, float] = {}  # Maps search query to last access timestamp
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._redis_prefix = "search_cache:"

    async def store(self, query: str, results: list) -> bool:
        """Store search results for a query"""
        normalized_query = self._normalize_query(query)

        if SEARCH_USE_REDIS:
            try:
                serialized_results = json.dumps(results)
                await redis.set(
                    f"{self._redis_prefix}{normalized_query}",
                    serialized_results,
                    ex=self.ttl,
                )
                logger.info(f"Stored {len(results)} search results for query '{query}' in Redis")
                return True
            except Exception:
                logger.exception("Error storing search results in Redis")
                # Fall back to memory cache if Redis fails

        # First cleanup if needed for memory cache
        if len(self.cache) >= self.max_items:
            self._cleanup()

        # Store results and update timestamp
        self.cache[normalized_query] = results
        self.last_accessed[normalized_query] = time.time()
        logger.info(f"Cached {len(results)} search results for query '{query}' in memory")
        return True

    async def get(self, query: str, limit: int = 10, offset: int = 0) -> Optional[list]:
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
            except Exception:
                logger.exception("Error retrieving search results from Redis")

        # Fall back to memory cache if not in Redis
        if all_results is None and normalized_query in self.cache:
            all_results = self.cache[normalized_query]
            self.last_accessed[normalized_query] = time.time()
            logger.info(f"Retrieved search results for '{query}' from memory cache")

        # If not found in any cache
        if all_results is None:
            logger.info(f"Cache miss for query '{query}'")
            return None

        # Return paginated subset
        end_idx = min(offset + limit, len(all_results))
        if offset >= len(all_results):
            logger.warning(f"Requested offset {offset} exceeds result count {len(all_results)}")
            return []

        logger.info(f"Cache hit for '{query}': serving {offset}:{end_idx} of {len(all_results)} results")
        return all_results[offset:end_idx]

    async def has_query(self, query: str) -> bool:
        """Check if query exists in cache"""
        normalized_query = self._normalize_query(query)

        # Check Redis first
        if SEARCH_USE_REDIS:
            try:
                exists = await redis.get(f"{self._redis_prefix}{normalized_query}")
                if exists:
                    return True
            except Exception:
                logger.exception("Error checking Redis for query existence")

        # Fall back to memory cache
        return normalized_query in self.cache

    async def get_total_count(self, query: str) -> int:
        """Get total count of results for a query"""
        normalized_query = self._normalize_query(query)

        # Check Redis first
        if SEARCH_USE_REDIS:
            try:
                cached_data = await redis.get(f"{self._redis_prefix}{normalized_query}")
                if cached_data:
                    all_results = json.loads(cached_data)
                    return len(all_results)
            except Exception:
                logger.exception("Error getting result count from Redis")

        # Fall back to memory cache
        if normalized_query in self.cache:
            return len(self.cache[normalized_query])

        return 0

    def _normalize_query(self, query: str) -> str:
        """Normalize query string for cache key"""
        if not query:
            return ""
        # Simple normalization - lowercase and strip whitespace
        return query.lower().strip()

    def _cleanup(self) -> None:
        """Remove oldest entries if memory cache is full"""
        now = time.time()
        # First remove expired entries
        expired_keys = [key for key, last_access in self.last_accessed.items() if now - last_access > self.ttl]

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
    def __init__(self) -> None:
        logger.info(f"Initializing search service with URL: {TXTAI_SERVICE_URL}")
        self.available = SEARCH_ENABLED
        # Use different timeout settings for indexing and search requests
        self.client = AsyncClient(timeout=30.0, base_url=TXTAI_SERVICE_URL)
        self.index_client = AsyncClient(timeout=120.0, base_url=TXTAI_SERVICE_URL)
        # Initialize search cache
        self.cache = SearchCache() if SEARCH_CACHE_ENABLED else None

        if not self.available:
            logger.info("Search disabled (SEARCH_ENABLED = False)")

        if SEARCH_CACHE_ENABLED:
            cache_location = "Redis" if SEARCH_USE_REDIS else "Memory"
            logger.info(f"Search caching enabled using {cache_location} cache with TTL={SEARCH_CACHE_TTL_SECONDS}s")

    async def info(self) -> dict:
        """Return information about search service"""
        if not self.available:
            return {"status": "disabled"}
        try:
            response: Response = await self.client.get("/info")
            response.raise_for_status()
            result = response.json()
            logger.info(f"Search service info: {result}")
            return result
        except Exception:
            logger.exception("Failed to get search info")
            return {"status": "error", "message": "Failed to get search info"}

    def is_ready(self) -> bool:
        """Check if service is available"""
        return self.available

    async def verify_docs(self, doc_ids: list) -> dict:
        """Verify which documents exist in the search index across all content types"""
        if not self.available:
            return {"status": "disabled"}

        try:
            logger.info(f"Verifying {len(doc_ids)} documents in search index")
            response: Response = await self.client.post(
                "/verify-docs",
                json={"doc_ids": doc_ids},
                timeout=60.0,  # Longer timeout for potentially large ID lists
            )
            response.raise_for_status()
            result = response.json()

            # Process the more detailed response format
            bodies_missing = set(result.get("bodies", {}).get("missing", []))
            titles_missing = set(result.get("titles", {}).get("missing", []))

            # Combine missing IDs from both bodies and titles
            # A document is considered missing if it's missing from either index
            all_missing = list(bodies_missing.union(titles_missing))

            # Log summary of verification results
            bodies_missing_count = len(bodies_missing)
            titles_missing_count = len(titles_missing)
            total_missing_count = len(all_missing)

            logger.info(
                f"Document verification complete: {bodies_missing_count} bodies missing, {titles_missing_count} titles missing"
            )
            logger.info(f"Total unique missing documents: {total_missing_count} out of {len(doc_ids)} total")

            # Return in a backwards-compatible format plus the detailed breakdown
            return {
                "missing": all_missing,
                "details": {
                    "bodies_missing": list(bodies_missing),
                    "titles_missing": list(titles_missing),
                    "bodies_missing_count": bodies_missing_count,
                    "titles_missing_count": titles_missing_count,
                },
            }
        except Exception:
            logger.exception("Document verification error")
            return {"status": "error", "message": "Document verification error"}

    def index(self, shout: Any) -> None:
        """Index a single document"""
        if not self.available:
            return
        logger.info(f"Indexing post {shout.id}")
        # Start in background to not block - store reference in a background collection
        # to prevent garbage collection while keeping the method non-blocking
        background_tasks.append(asyncio.create_task(self.perform_index(shout)))

    async def perform_index(self, shout: Any) -> None:
        """Index a single document across multiple endpoints"""
        if not self.available:
            return

        try:
            logger.info(f"Indexing document {shout.id} to individual endpoints")
            indexing_tasks = []

            # 1. Index title if available
            if hasattr(shout, "title") and shout.title and isinstance(shout.title, str):
                title_doc = {"id": str(shout.id), "title": shout.title.strip()}
                indexing_tasks.append(self.index_client.post("/index-title", json=title_doc))

            # 2. Index body content (subtitle, lead, body)
            body_text_parts = []
            for field_name in ["subtitle", "lead", "body"]:
                field_value = getattr(shout, field_name, None)
                if field_value and isinstance(field_value, str) and field_value.strip():
                    body_text_parts.append(field_value.strip())

            # Process media content if available
            media = getattr(shout, "media", None)
            if media:
                if isinstance(media, str):
                    try:
                        media_json = json.loads(media)
                        if isinstance(media_json, dict):
                            if "title" in media_json:
                                body_text_parts.append(media_json["title"])
                            if "body" in media_json:
                                body_text_parts.append(media_json["body"])
                    except json.JSONDecodeError:
                        body_text_parts.append(media)
                elif isinstance(media, dict) and (media.get("title") or media.get("body")):
                    body_text_parts.append(media["title"])
                    body_text_parts.append(media["body"])

            if body_text_parts:
                body_text = " ".join(body_text_parts)
                # Truncate if too long
                max_text_length = 4000
                if len(body_text) > max_text_length:
                    body_text = body_text[:max_text_length]

                body_doc = {"id": str(shout.id), "body": body_text}
                indexing_tasks.append(self.index_client.post("/index-body", json=body_doc))

            # 3. Index authors
            authors = getattr(shout, "authors", [])
            for author in authors:
                author_id = str(getattr(author, "id", 0))
                if not author_id or author_id == "0":
                    continue

                name = getattr(author, "name", "")

                # Combine bio and about fields
                bio_parts = []
                bio = getattr(author, "bio", "")
                if bio and isinstance(bio, str):
                    bio_parts.append(bio.strip())

                about = getattr(author, "about", "")
                if about and isinstance(about, str):
                    bio_parts.append(about.strip())

                combined_bio = " ".join(bio_parts)

                if name:
                    author_doc = {"id": author_id, "name": name, "bio": combined_bio}
                    indexing_tasks.append(self.index_client.post("/index-author", json=author_doc))

            # Run all indexing tasks in parallel
            if indexing_tasks:
                responses = await asyncio.gather(*indexing_tasks, return_exceptions=True)

                # Check for errors in responses
                for i, response in enumerate(responses):
                    if isinstance(response, Exception):
                        logger.error(f"Error in indexing task {i}: {response}")
                    elif hasattr(response, "status_code") and getattr(response, "status_code", 0) >= 400:
                        error_text = ""
                        if hasattr(response, "text") and isinstance(response.text, str):
                            error_text = response.text
                        elif hasattr(response, "text") and callable(response.text):
                            try:
                                # Получаем текст ответа, учитывая разные реализации Response
                                http_response = cast(Response, response)
                                # В некоторых версиях httpx, text - это свойство, а не метод
                                if callable(http_response.text):
                                    error_text = await http_response.text()
                                else:
                                    error_text = str(http_response.text)
                            except Exception as e:
                                error_text = f"[unable to get response text: {e}]"

                        logger.error(f"Error response in indexing task {i}: {response.status_code}, {error_text}")

                logger.info(f"Document {shout.id} indexed across {len(indexing_tasks)} endpoints")
            else:
                logger.warning(f"No content to index for shout {shout.id}")

        except Exception:
            logger.exception(f"Indexing error for shout {shout.id}")

    async def bulk_index(self, shouts: list) -> None:
        """Index multiple documents across three separate endpoints"""
        if not self.available or not shouts:
            logger.warning(
                f"Bulk indexing skipped: available={self.available}, shouts_count={len(shouts) if shouts else 0}"
            )
            return

        start_time = time.time()
        logger.info(f"Starting multi-endpoint bulk indexing of {len(shouts)} documents")

        # Prepare documents for different endpoints
        title_docs = []
        body_docs = []
        author_docs = {}  # Use dict to prevent duplicate authors

        total_skipped = 0

        for shout in shouts:
            try:
                # 1. Process title documents
                if hasattr(shout, "title") and shout.title and isinstance(shout.title, str):
                    title_docs.append({"id": str(shout.id), "title": shout.title.strip()})

                # 2. Process body documents (subtitle, lead, body)
                body_text_parts = []
                for field_name in ["subtitle", "lead", "body"]:
                    field_value = getattr(shout, field_name, None)
                    if field_value and isinstance(field_value, str) and field_value.strip():
                        body_text_parts.append(field_value.strip())

                # Process media content if available
                media = getattr(shout, "media", None)
                if media:
                    if isinstance(media, str):
                        try:
                            media_json = json.loads(media)
                            if isinstance(media_json, dict):
                                if "title" in media_json:
                                    body_text_parts.append(media_json["title"])
                                if "body" in media_json:
                                    body_text_parts.append(media_json["body"])
                        except json.JSONDecodeError:
                            body_text_parts.append(media)
                    elif isinstance(media, dict) and (media.get("title") or media.get("body")):
                        body_text_parts.append(media["title"])
                        body_text_parts.append(media["body"])

                # Only add body document if we have body text
                if body_text_parts:
                    body_text = " ".join(body_text_parts)
                    # Truncate if too long
                    max_text_length = 4000
                    if len(body_text) > max_text_length:
                        body_text = body_text[:max_text_length]

                    body_docs.append({"id": str(shout.id), "body": body_text})

                # 3. Process authors if available
                authors = getattr(shout, "authors", [])
                for author in authors:
                    author_id = str(getattr(author, "id", 0))
                    if not author_id or author_id == "0":
                        continue

                    # Skip if we've already processed this author
                    if author_id in author_docs:
                        continue

                    name = getattr(author, "name", "")

                    # Combine bio and about fields
                    bio_parts = []
                    bio = getattr(author, "bio", "")
                    if bio and isinstance(bio, str):
                        bio_parts.append(bio.strip())

                    about = getattr(author, "about", "")
                    if about and isinstance(about, str):
                        bio_parts.append(about.strip())

                    combined_bio = " ".join(bio_parts)

                    # Only add if we have author data
                    if name:
                        author_docs[author_id] = {
                            "id": author_id,
                            "name": name,
                            "bio": combined_bio,
                        }

            except Exception:
                logger.exception(f"Error processing shout {getattr(shout, 'id', 'unknown')} for indexing")
                total_skipped += 1

        # Convert author dict to list
        author_docs_list = list(author_docs.values())

        # Log indexing started message
        logger.info("indexing started...")

        # Process each endpoint in parallel
        indexing_tasks = [
            self._index_endpoint(title_docs, "/bulk-index-titles", "title"),
            self._index_endpoint(body_docs, "/bulk-index-bodies", "body"),
            self._index_endpoint(author_docs_list, "/bulk-index-authors", "author"),
        ]

        await asyncio.gather(*indexing_tasks)

        elapsed = time.time() - start_time
        logger.info(
            f"Multi-endpoint indexing completed in {elapsed:.2f}s: "
            f"{len(title_docs)} titles, {len(body_docs)} bodies, {len(author_docs_list)} authors, "
            f"{total_skipped} shouts skipped"
        )

    async def _index_endpoint(self, documents: list, endpoint: str, doc_type: str) -> None:
        """Process and index documents to a specific endpoint"""
        if not documents:
            logger.info(f"No {doc_type} documents to index")
            return

        logger.info(f"Indexing {len(documents)} {doc_type} documents")

        # Categorize documents by size
        small_docs, medium_docs, large_docs = self._categorize_by_size(documents, doc_type)

        # Process each category with appropriate batch sizes
        batch_sizes = {
            "small": min(MAX_BATCH_SIZE, 15),
            "medium": min(MAX_BATCH_SIZE, 10),
            "large": min(MAX_BATCH_SIZE, 3),
        }

        for category, docs in [
            ("small", small_docs),
            ("medium", medium_docs),
            ("large", large_docs),
        ]:
            if docs:
                batch_size = batch_sizes[category]
                await self._process_batches(docs, batch_size, endpoint, f"{doc_type}-{category}")

    def _categorize_by_size(self, documents: list, doc_type: str) -> tuple[list, list, list]:
        """Categorize documents by size for optimized batch processing"""
        small_docs = []
        medium_docs = []
        large_docs = []

        for doc in documents:
            # Extract relevant text based on document type
            if doc_type == "title":
                text = doc.get("title", "")
            elif doc_type == "body":
                text = doc.get("body", "")
            else:  # author
                # For authors, consider both name and bio length
                text = doc.get("name", "") + " " + doc.get("bio", "")

            text_len = len(text)

            if text_len > 5000:
                large_docs.append(doc)
            elif text_len > 2000:
                medium_docs.append(doc)
            else:
                small_docs.append(doc)

        logger.info(
            f"{doc_type.capitalize()} documents categorized: {len(small_docs)} small, {len(medium_docs)} medium, {len(large_docs)} large"
        )
        return small_docs, medium_docs, large_docs

    async def _process_batches(self, documents: list, batch_size: int, endpoint: str, batch_prefix: str) -> None:
        """Process document batches with retry logic"""
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            batch_id = f"{batch_prefix}-{i // batch_size + 1}"

            retry_count = 0
            max_retries = 3
            success = False

            while not success and retry_count < max_retries:
                try:
                    response: Response = await self.index_client.post(endpoint, json=batch, timeout=90.0)

                    if response.status_code == 422:
                        error_detail = response.json()
                        logger.error(
                            f"Validation error from search service for batch {batch_id}: {self._truncate_error_detail(error_detail)}"
                        )
                        break

                    response.raise_for_status()
                    success = True

                except Exception:
                    retry_count += 1
                    if retry_count >= max_retries:
                        if len(batch) > 1:
                            mid = len(batch) // 2
                            await self._process_batches(
                                batch[:mid],
                                batch_size // 2,
                                endpoint,
                                f"{batch_prefix}-{i // batch_size}-A",
                            )
                            await self._process_batches(
                                batch[mid:],
                                batch_size // 2,
                                endpoint,
                                f"{batch_prefix}-{i // batch_size}-B",
                            )
                        else:
                            logger.exception(
                                f"Failed to index single document in batch {batch_id} after {max_retries} attempts"
                            )
                        break

                    wait_time = (2**retry_count) + (secrets.randbelow(500) / 1000)
                    await asyncio.sleep(wait_time)

    def _truncate_error_detail(self, error_detail: Any) -> Any:
        """Truncate error details for logging"""
        truncated_detail = error_detail.copy() if isinstance(error_detail, dict) else error_detail

        if (
            isinstance(truncated_detail, dict)
            and "detail" in truncated_detail
            and isinstance(truncated_detail["detail"], list)
        ):
            for _i, item in enumerate(truncated_detail["detail"]):
                if (
                    isinstance(item, dict)
                    and "input" in item
                    and isinstance(item["input"], dict)
                    and any(k in item["input"] for k in ["documents", "text"])
                ):
                    if "documents" in item["input"] and isinstance(item["input"]["documents"], list):
                        for j, doc in enumerate(item["input"]["documents"]):
                            if "text" in doc and isinstance(doc["text"], str) and len(doc["text"]) > 100:
                                item["input"]["documents"][j]["text"] = (
                                    f"{doc['text'][:100]}... [truncated, total {len(doc['text'])} chars]"
                                )

                    if (
                        "text" in item["input"]
                        and isinstance(item["input"]["text"], str)
                        and len(item["input"]["text"]) > 100
                    ):
                        item["input"]["text"] = (
                            f"{item['input']['text'][:100]}... [truncated, total {len(item['input']['text'])} chars]"
                        )

        return truncated_detail

    async def search(self, text: str, limit: int, offset: int) -> list:
        """Search documents"""
        if not self.available:
            return []

        # Check if we can serve from cache
        if SEARCH_CACHE_ENABLED and self.cache is not None:
            has_cache = await self.cache.has_query(text)
            if has_cache:
                cached_results = await self.cache.get(text, limit, offset)
                if cached_results is not None:
                    return cached_results

        # Not in cache or cache disabled, perform new search
        try:
            # Decide whether to prefetch and cache or just get what we need
            search_limit = SEARCH_PREFETCH_SIZE if SEARCH_CACHE_ENABLED else limit

            logger.info(f"Searching for: '{text}' (limit={limit}, offset={offset}, search_limit={search_limit})")

            response: Response = await self.client.post(
                "/search-combined",
                json={"text": text, "limit": search_limit},
            )
            response.raise_for_status()
            result = response.json()
            formatted_results = result.get("results", [])

            # filter out non‑numeric IDs
            valid_results = [r for r in formatted_results if r.get("id", "").isdigit()]
            if len(valid_results) != len(formatted_results):
                formatted_results = valid_results

            if len(valid_results) != len(formatted_results):
                formatted_results = valid_results

            if SEARCH_CACHE_ENABLED and self.cache is not None:
                # Store the full prefetch batch, then page it
                await self.cache.store(text, formatted_results)
                return await self.cache.get(text, limit, offset) or []

            return formatted_results
        except Exception:
            logger.exception(f"Search error for '{text}'")
            return []

    async def search_authors(self, text: str, limit: int = 10, offset: int = 0) -> list:
        """Search only for authors using the specialized endpoint"""
        if not self.available or not text.strip():
            return []

        cache_key = f"author:{text}"

        # Check if we can serve from cache
        if SEARCH_CACHE_ENABLED and self.cache is not None:
            has_cache = await self.cache.has_query(cache_key)
            if has_cache:
                cached_results = await self.cache.get(cache_key, limit, offset)
                if cached_results is not None:
                    return cached_results

        # Not in cache or cache disabled, perform new search
        try:
            search_limit = SEARCH_PREFETCH_SIZE if SEARCH_CACHE_ENABLED else limit

            logger.info(
                f"Searching authors for: '{text}' (limit={limit}, offset={offset}, search_limit={search_limit})"
            )
            response: Response = await self.client.post("/search-author", json={"text": text, "limit": search_limit})
            response.raise_for_status()

            result = response.json()
            author_results = result.get("results", [])

            # Filter out any invalid results if necessary
            valid_results = [r for r in author_results if r.get("id", "").isdigit()]
            if len(valid_results) != len(author_results):
                author_results = valid_results

            if SEARCH_CACHE_ENABLED and self.cache is not None:
                # Store the full prefetch batch, then page it
                await self.cache.store(cache_key, author_results)
                return await self.cache.get(cache_key, limit, offset) or []

            return author_results[offset : offset + limit]

        except Exception:
            logger.exception(f"Error searching authors for '{text}'")
            return []

    async def check_index_status(self) -> dict:
        """Get detailed statistics about the search index health"""
        if not self.available:
            return {"status": "disabled"}

        try:
            response: Response = await self.client.get("/index-status")
            response.raise_for_status()
            result = response.json()

            if result.get("consistency", {}).get("status") != "ok":
                null_count = result.get("consistency", {}).get("null_embeddings_count", 0)
                if null_count > 0:
                    logger.warning(f"Found {null_count} documents with NULL embeddings")

            return result
        except Exception:
            logger.exception("Failed to check index status")
            return {"status": "error", "message": "Failed to check index status"}

    async def close(self) -> None:
        """Close connections and release resources"""
        if hasattr(self, "client") and self.client:
            await self.client.aclose()
        if hasattr(self, "index_client") and self.index_client:
            await self.index_client.aclose()
        logger.info("Search service closed")


# Create the search service singleton
search_service = SearchService()

# API-compatible function to perform a search


async def search_text(text: str, limit: int = 200, offset: int = 0) -> list:
    payload = []
    if search_service.available:
        payload = await search_service.search(text, limit, offset)
    return payload


async def search_author_text(text: str, limit: int = 10, offset: int = 0) -> list:
    """Search authors API helper function"""
    if search_service.available:
        return await search_service.search_authors(text, limit, offset)
    return []


async def get_search_count(text: str) -> int:
    """Get count of title search results"""
    if not search_service.available:
        return 0

    if SEARCH_CACHE_ENABLED and search_service.cache is not None and await search_service.cache.has_query(text):
        return await search_service.cache.get_total_count(text)

    # If not found in cache, fetch from endpoint
    return len(await search_text(text, SEARCH_PREFETCH_SIZE, 0))


async def get_author_search_count(text: str) -> int:
    """Get count of author search results"""
    if not search_service.available:
        return 0

    cache_key = f"author:{text}"
    if SEARCH_CACHE_ENABLED and search_service.cache is not None and await search_service.cache.has_query(cache_key):
        return await search_service.cache.get_total_count(cache_key)

    # If not found in cache, fetch from endpoint
    return len(await search_author_text(text, SEARCH_PREFETCH_SIZE, 0))


async def initialize_search_index(shouts_data: list) -> None:
    """Initialize search index with existing data during application startup"""
    if not SEARCH_ENABLED:
        return

    if not shouts_data:
        return

    info = await search_service.info()
    if info.get("status") in ["error", "unavailable", "disabled"]:
        return

    index_stats = info.get("index_stats", {})
    indexed_doc_count = index_stats.get("total_count", 0)

    index_status = await search_service.check_index_status()
    if index_status.get("status") == "inconsistent":
        problem_ids = index_status.get("consistency", {}).get("null_embeddings_sample", [])

        if problem_ids:
            problem_docs = [shout for shout in shouts_data if str(shout.id) in problem_ids]
            if problem_docs:
                await search_service.bulk_index(problem_docs)

    # Only consider shouts with body content for body verification
    def has_body_content(shout: Any) -> bool:
        for field in ["subtitle", "lead", "body"]:
            if (
                getattr(shout, field, None)
                and isinstance(getattr(shout, field, None), str)
                and getattr(shout, field).strip()
            ):
                return True
        media = getattr(shout, "media", None)
        if media:
            if isinstance(media, str):
                try:
                    media_json = json.loads(media)
                    if isinstance(media_json, dict) and (media_json.get("title") or media_json.get("body")):
                        return True
                except Exception:
                    return True
            elif isinstance(media, dict) and (media.get("title") or media.get("body")):
                return True
        return False

    shouts_with_body = [shout for shout in shouts_data if has_body_content(shout)]
    body_ids = [str(shout.id) for shout in shouts_with_body]

    if abs(indexed_doc_count - len(shouts_data)) > 10:
        doc_ids = [str(shout.id) for shout in shouts_data]
        verification = await search_service.verify_docs(doc_ids)
        if verification.get("status") == "error":
            return
        # Only reindex missing docs that actually have body content
        missing_ids = [mid for mid in verification.get("missing", []) if mid in body_ids]
        if missing_ids:
            missing_docs = [shout for shout in shouts_with_body if str(shout.id) in missing_ids]
            await search_service.bulk_index(missing_docs)
    else:
        pass

    try:
        test_query = "test"
        # Use body search since that's most likely to return results
        test_results = await search_text(test_query, 5)

        if test_results:
            categories = set()
            for result in test_results:
                result_id = result.get("id")
                matching_shouts = [s for s in shouts_data if str(s.id) == result_id]
                if matching_shouts and hasattr(matching_shouts[0], "category"):
                    categories.add(getattr(matching_shouts[0], "category", "unknown"))
    except Exception as ex:
        logger.warning(f"Test search failed during initialization: {ex}")


async def check_search_service() -> None:
    info = await search_service.info()
    if info.get("status") in ["error", "unavailable", "disabled"]:
        logger.debug("Search service is not available")
    else:
        logger.info("Search service is available and ready")


# Initialize search index in the background
async def initialize_search_index_background() -> None:
    """
    Запускает индексацию поиска в фоновом режиме с низким приоритетом.
    """
    try:
        logger.info("Запуск фоновой индексации поиска...")

        # Здесь бы был код загрузки данных и индексации
        # Пока что заглушка

        logger.info("Фоновая индексация поиска завершена")
    except Exception:
        logger.exception("Ошибка фоновой индексации поиска")
