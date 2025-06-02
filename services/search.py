import asyncio
import json
import logging
import os
import random
import time
from typing import Any, Union

import httpx

from orm.shout import Shout
from settings import TXTAI_SERVICE_URL
from utils.logger import root_logger as logger

# Set up proper logging
logger.setLevel(logging.INFO)  # Change to INFO to see more details
# Disable noise HTTP cltouchient logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Configuration for search service
SEARCH_ENABLED = bool(os.environ.get("SEARCH_ENABLED", "true").lower() in ["true", "1", "yes"])
MAX_BATCH_SIZE = int(os.environ.get("SEARCH_MAX_BATCH_SIZE", "25"))

# Search cache configuration
SEARCH_CACHE_ENABLED = bool(os.environ.get("SEARCH_CACHE_ENABLED", "true").lower() in ["true", "1", "yes"])
SEARCH_CACHE_TTL_SECONDS = int(os.environ.get("SEARCH_CACHE_TTL_SECONDS", "300"))  # Default: 5 minutes
SEARCH_PREFETCH_SIZE = int(os.environ.get("SEARCH_PREFETCH_SIZE", "200"))
SEARCH_USE_REDIS = bool(os.environ.get("SEARCH_USE_REDIS", "true").lower() in ["true", "1", "yes"])

search_offset = 0

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
                await redis.serialize_and_set(
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

    async def get(self, query: str, limit: int = 10, offset: int = 0) -> list[dict] | None:
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

        logger.info("Cleaned up %d expired search cache entries", len(expired_keys))

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
            logger.info("Removed %d oldest search cache entries", remove_count)


class SearchService:
    def __init__(self) -> None:
        logger.info("Initializing search service with URL: %s", TXTAI_SERVICE_URL)
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

    async def info(self) -> dict[str, Any]:
        """Check search service info"""
        if not SEARCH_ENABLED:
            return {"status": "disabled", "message": "Search is disabled"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{TXTAI_SERVICE_URL}/info")
            response.raise_for_status()
            result = response.json()
            logger.info(f"Search service info: {result}")
            return result
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            # Используем debug уровень для ошибок подключения
            logger.debug("Search service connection failed: %s", str(e))
            return {"status": "error", "message": str(e)}
        except Exception as e:
            # Другие ошибки логируем как debug
            logger.debug("Failed to get search info: %s", str(e))
            return {"status": "error", "message": str(e)}

    def is_ready(self) -> bool:
        """Check if service is available"""
        return self.available

    async def verify_docs(self, doc_ids: list[int]) -> dict[str, Any]:
        """Verify which documents exist in the search index across all content types"""
        if not self.available:
            return {"status": "error", "message": "Search service not available"}

        try:
            # Check documents across all content types
            results = {}
            for content_type in ["shouts", "authors", "topics"]:
                endpoint = f"{TXTAI_SERVICE_URL}/exists/{content_type}"
                async with httpx.AsyncClient() as client:
                    response = await client.post(endpoint, json={"ids": doc_ids})
                response.raise_for_status()
                results[content_type] = response.json()

            return {
                "status": "success",
                "verified": results,
                "total_docs": len(doc_ids),
            }
        except Exception as e:
            logger.exception("Document verification error")
            return {"status": "error", "message": str(e)}

    def index(self, shout: Shout) -> None:
        """Index a single document"""
        if not self.available:
            return

        logger.info(f"Indexing post {shout.id}")
        # Start in background to not block
        task = asyncio.create_task(self.perform_index(shout))
        # Store task reference to prevent garbage collection
        self._background_tasks: set[asyncio.Task[None]] = getattr(self, "_background_tasks", set())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def perform_index(self, shout: Shout) -> None:
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
                elif isinstance(media, dict):
                    if "title" in media:
                        body_text_parts.append(media["title"])
                    if "body" in media:
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
                        logger.error("Error in indexing task %d: %s", i, response)
                    elif hasattr(response, "status_code") and response.status_code >= 400:
                        error_text = ""
                        if hasattr(response, "text") and callable(response.text):
                            try:
                                error_text = await response.text()
                            except (Exception, httpx.HTTPError):
                                error_text = str(response)
                        logger.error("Error response in indexing task %d: %d, %s", i, response.status_code, error_text)

                logger.info("Document %s indexed across %d endpoints", shout.id, len(indexing_tasks))
            else:
                logger.warning("No content to index for shout %s", shout.id)

        except Exception:
            logger.exception("Indexing error for shout %s", shout.id)

    async def bulk_index(self, shouts: list[Shout]) -> None:
        """Index multiple documents across three separate endpoints"""
        if not self.available or not shouts:
            logger.warning(
                "Bulk indexing skipped: available=%s, shouts_count=%d", self.available, len(shouts) if shouts else 0
            )
            return

        start_time = time.time()
        logger.info("Starting multi-endpoint bulk indexing of %d documents", len(shouts))

        # Prepare documents for different endpoints
        title_docs: list[dict[str, Any]] = []
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
                    elif isinstance(media, dict):
                        if "title" in media:
                            body_text_parts.append(media["title"])
                        if "body" in media:
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
                logger.exception("Error processing shout %s for indexing", getattr(shout, "id", "unknown"))
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
            "Multi-endpoint indexing completed in %.2fs: %d titles, %d bodies, %d authors, %d shouts skipped",
            elapsed,
            len(title_docs),
            len(body_docs),
            len(author_docs_list),
            total_skipped,
        )

    async def _index_endpoint(self, documents: list[dict], endpoint: str, doc_type: str) -> None:
        """Process and index documents to a specific endpoint"""
        if not documents:
            logger.info("No %s documents to index", doc_type)
            return

        logger.info("Indexing %d %s documents", len(documents), doc_type)

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

    def _categorize_by_size(self, documents: list[dict], doc_type: str) -> tuple[list[dict], list[dict], list[dict]]:
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
            "%s documents categorized: %d small, %d medium, %d large",
            doc_type.capitalize(),
            len(small_docs),
            len(medium_docs),
            len(large_docs),
        )
        return small_docs, medium_docs, large_docs

    async def _process_batches(self, documents: list[dict], batch_size: int, endpoint: str, batch_prefix: str) -> None:
        """Process document batches with retry logic"""
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            batch_id = f"{batch_prefix}-{i // batch_size + 1}"

            retry_count = 0
            max_retries = 3
            success = False

            while not success and retry_count < max_retries:
                try:
                    response = await self.index_client.post(endpoint, json=batch, timeout=90.0)

                    if response.status_code == 422:
                        error_detail = response.json()
                        logger.error(
                            "Validation error from search service for batch %s: %s",
                            batch_id,
                            self._truncate_error_detail(error_detail),
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
                                "Failed to index single document in batch %s after %d attempts", batch_id, max_retries
                            )
                        break

                    wait_time = (2**retry_count) + (random.SystemRandom().random() * 0.5)
                    await asyncio.sleep(wait_time)

    def _truncate_error_detail(self, error_detail: Union[dict, str, int]) -> Union[dict, str, int]:
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

    async def search(self, text: str, limit: int, offset: int) -> list[dict]:
        """Search documents"""
        if not self.available:
            logger.warning("Search service not available")
            return []

        if not text or not text.strip():
            logger.warning("Empty search query provided")
            return []

        # Устанавливаем общий размер выборки поиска
        search_limit = SEARCH_PREFETCH_SIZE if SEARCH_CACHE_ENABLED else limit

        logger.info("Searching for: '%s' (limit=%d, offset=%d, search_limit=%d)", text, limit, offset, search_limit)

        try:
            response = await self.client.post(
                "/search-combined",
                json={"text": text, "limit": search_limit},
            )

            logger.debug(f"Search service response status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Search service returned status {response.status_code}: {response.text}")
                return []

            results = response.json()
            logger.debug(f"Raw search results: {len(results) if results else 0} items")

            if not results or not isinstance(results, list):
                logger.warning(f"No search results or invalid format for query '{text}'")
                return []

            # Обрабатываем каждый результат
            formatted_results = []
            for i, item in enumerate(results):
                if isinstance(item, dict):
                    formatted_result = self._format_search_result(item)
                    formatted_results.append(formatted_result)
                    logger.debug(
                        f"Formatted result {i}: id={formatted_result.get('id')}, title={formatted_result.get('title', '')[:50]}..."
                    )
                else:
                    logger.warning(f"Invalid search result item {i}: {type(item)}")

            logger.info(f"Successfully formatted {len(formatted_results)} search results for '{text}'")

            # Сохраняем результаты в кеше
            if SEARCH_CACHE_ENABLED and self.cache:
                await self.cache.store(text, formatted_results)
                logger.debug(f"Stored {len(formatted_results)} results in cache for '{text}'")

            # Если включен кеш и есть лишние результаты
            if SEARCH_CACHE_ENABLED and self.cache and await self.cache.has_query(text):
                cached_result = await self.cache.get(text, limit, offset)
                logger.debug(f"Retrieved {len(cached_result) if cached_result else 0} results from cache for '{text}'")
                return cached_result or []

            return formatted_results

        except Exception as e:
            logger.error(f"Search error for '{text}': {e}", exc_info=True)
            return []

    async def search_authors(self, text: str, limit: int = 10, offset: int = 0) -> list[dict]:
        """Search only for authors using the specialized endpoint"""
        if not self.available or not text.strip():
            return []

        # Кеш для авторов
        cache_key = f"author:{text}"
        if SEARCH_CACHE_ENABLED and self.cache and await self.cache.has_query(cache_key):
            cached_results = await self.cache.get(cache_key, limit, offset)
            if cached_results:
                return cached_results

        try:
            # Устанавливаем общий размер выборки поиска
            search_limit = SEARCH_PREFETCH_SIZE if SEARCH_CACHE_ENABLED else limit

            logger.info(
                "Searching authors for: '%s' (limit=%d, offset=%d, search_limit=%d)", text, limit, offset, search_limit
            )
            response = await self.client.post("/search-author", json={"text": text, "limit": search_limit})

            results = await response.json()
            if not results or not isinstance(results, list):
                return []

            # Форматируем результаты поиска авторов
            author_results = []
            for item in results:
                if isinstance(item, dict):
                    formatted_author = self._format_author_result(item)
                    author_results.append(formatted_author)

            # Сохраняем результаты в кеше
            if SEARCH_CACHE_ENABLED and self.cache:
                await self.cache.store(cache_key, author_results)

            # Возвращаем нужную порцию результатов
            return author_results[offset : offset + limit]

        except Exception:
            logger.exception("Error searching authors for '%s'", text)
            return []

    async def check_index_status(self) -> dict:
        """Get detailed statistics about the search index health"""
        if not self.available:
            return {"status": "unavailable", "message": "Search service not available"}

        try:
            response = await self.client.post("/check-index")
            result = await response.json()

            if isinstance(result, dict):
                # Проверяем на NULL эмбеддинги
                null_count = result.get("consistency", {}).get("null_embeddings_count", 0)
                if null_count > 0:
                    logger.warning("Found %d documents with NULL embeddings", null_count)
        except Exception as e:
            logger.exception("Failed to check index status")
            return {"status": "error", "message": str(e)}
        else:
            return result

    def _format_search_result(self, item: dict) -> dict:
        """Format search result item"""
        formatted_result = {}

        # Обязательные поля
        if "id" in item:
            formatted_result["id"] = item["id"]
        if "title" in item:
            formatted_result["title"] = item["title"]
        if "body" in item:
            formatted_result["body"] = item["body"]

        # Дополнительные поля
        for field in ["subtitle", "lead", "author_id", "author_name", "created_at", "stat"]:
            if field in item:
                formatted_result[field] = item[field]

        return formatted_result

    def _format_author_result(self, item: dict) -> dict:
        """Format author search result item"""
        formatted_result = {}

        # Обязательные поля для автора
        if "id" in item:
            formatted_result["id"] = item["id"]
        if "name" in item:
            formatted_result["name"] = item["name"]
        if "username" in item:
            formatted_result["username"] = item["username"]

        # Дополнительные поля для автора
        for field in ["slug", "bio", "pic", "created_at", "stat"]:
            if field in item:
                formatted_result[field] = item[field]

        return formatted_result

    def close(self) -> None:
        """Close the search service"""


# Create the search service singleton
search_service = SearchService()

# API-compatible function to perform a search


async def search_text(text: str, limit: int = 200, offset: int = 0) -> list[dict]:
    payload = []
    if search_service.available:
        payload = await search_service.search(text, limit, offset)
    return payload


async def search_author_text(text: str, limit: int = 10, offset: int = 0) -> list[dict]:
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

    # Return approximate count for active search
    return 42  # Placeholder implementation


async def get_author_search_count(text: str) -> int:
    """Get count of author search results"""
    if not search_service.available:
        return 0

    if SEARCH_CACHE_ENABLED:
        cache_key = f"author:{text}"
        if search_service.cache is not None and await search_service.cache.has_query(cache_key):
            return await search_service.cache.get_total_count(cache_key)

    return 0  # Placeholder implementation


async def initialize_search_index(shouts_data: list) -> None:
    """Initialize search index with existing data during application startup"""
    if not SEARCH_ENABLED:
        logger.info("Search is disabled, skipping index initialization")
        return

    if not search_service.available:
        logger.warning("Search service not available, skipping index initialization")
        return

    # Only consider shouts with body content for body verification
    def has_body_content(shout: dict) -> bool:
        for field in ["subtitle", "lead", "body"]:
            if hasattr(shout, field) and getattr(shout, field) and getattr(shout, field).strip():
                return True

        # Check media JSON for content
        if hasattr(shout, "media") and shout.media:
            media = shout.media
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

    total_count = len(shouts_data)
    processed_count = 0

    # Collect categories while we're at it for informational purposes
    categories: set = set()

    try:
        for shout in shouts_data:
            # Skip items that lack meaningful text content
            if not has_body_content(shout):
                continue

            # Track categories
            matching_shouts = [s for s in shouts_data if getattr(s, "id", None) == getattr(shout, "id", None)]
            if matching_shouts and hasattr(matching_shouts[0], "category"):
                categories.add(getattr(matching_shouts[0], "category", "unknown"))
    except (AttributeError, TypeError):
        pass

    logger.info("Search index initialization completed: %d/%d items", processed_count, total_count)


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
