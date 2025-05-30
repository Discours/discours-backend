"""
Caching system for the Discours platform
----------------------------------------

This module provides a comprehensive caching solution with these key components:

1. KEY NAMING CONVENTIONS:
   - Entity-based keys: "entity:property:value" (e.g., "author:id:123")
   - Collection keys: "entity:collection:params" (e.g., "authors:stats:limit=10:offset=0")
   - Special case keys: Maintained for backwards compatibility (e.g., "topic_shouts_123")

2. CORE FUNCTIONS:
   - cached_query(): High-level function for retrieving cached data or executing queries

3. ENTITY-SPECIFIC FUNCTIONS:
   - cache_author(), cache_topic(): Cache entity data
   - get_cached_author(), get_cached_topic(): Retrieve entity data from cache
   - invalidate_cache_by_prefix(): Invalidate all keys with a specific prefix

4. CACHE INVALIDATION STRATEGY:
   - Direct invalidation via invalidate_* functions for immediate changes
   - Delayed invalidation via revalidation_manager for background processing
   - Event-based triggers for automatic cache updates (see triggers.py)

To maintain consistency with the existing codebase, this module preserves
the original key naming patterns while providing a more structured approach
for new cache operations.
"""

import asyncio
import json
from typing import Any, List, Optional

import orjson
from sqlalchemy import and_, join, select

from auth.orm import Author, AuthorFollower
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic, TopicFollower
from services.db import local_session
from services.redis import redis
from utils.encoders import CustomJSONEncoder
from utils.logger import root_logger as logger

DEFAULT_FOLLOWS = {
    "topics": [],
    "authors": [],
    "shouts": [],
    "communities": [{"id": 1, "name": "Дискурс", "slug": "discours", "pic": ""}],
}

CACHE_TTL = 300  # 5 minutes

# Key templates for common entity types
# These are used throughout the codebase and should be maintained for compatibility
CACHE_KEYS = {
    "TOPIC_ID": "topic:id:{}",
    "TOPIC_SLUG": "topic:slug:{}",
    "TOPIC_AUTHORS": "topic:authors:{}",
    "TOPIC_FOLLOWERS": "topic:followers:{}",
    "TOPIC_SHOUTS": "topic_shouts_{}",
    "AUTHOR_ID": "author:id:{}",
    "SHOUTS": "shouts:{}",
}


# Cache topic data
async def cache_topic(topic: dict):
    payload = json.dumps(topic, cls=CustomJSONEncoder)
    await asyncio.gather(
        redis.execute("SET", f"topic:id:{topic['id']}", payload),
        redis.execute("SET", f"topic:slug:{topic['slug']}", payload),
    )


# Cache author data
async def cache_author(author: dict):
    payload = json.dumps(author, cls=CustomJSONEncoder)
    await asyncio.gather(
        redis.execute("SET", f"author:slug:{author['slug'].strip()}", str(author["id"])),
        redis.execute("SET", f"author:id:{author['id']}", payload),
    )


# Cache follows data
async def cache_follows(follower_id: int, entity_type: str, entity_id: int, is_insert=True):
    key = f"author:follows-{entity_type}s:{follower_id}"
    follows_str = await redis.execute("GET", key)
    follows = orjson.loads(follows_str) if follows_str else DEFAULT_FOLLOWS[entity_type]
    if is_insert:
        if entity_id not in follows:
            follows.append(entity_id)
    else:
        follows = [eid for eid in follows if eid != entity_id]
    await redis.execute("SET", key, json.dumps(follows, cls=CustomJSONEncoder))
    await update_follower_stat(follower_id, entity_type, len(follows))


# Update follower statistics
async def update_follower_stat(follower_id, entity_type, count):
    follower_key = f"author:id:{follower_id}"
    follower_str = await redis.execute("GET", follower_key)
    follower = orjson.loads(follower_str) if follower_str else None
    if follower:
        follower["stat"] = {f"{entity_type}s": count}
        await cache_author(follower)


# Get author from cache
async def get_cached_author(author_id: int, get_with_stat):
    author_key = f"author:id:{author_id}"
    result = await redis.execute("GET", author_key)
    if result:
        return orjson.loads(result)
    # Load from database if not found in cache
    q = select(Author).where(Author.id == author_id)
    authors = get_with_stat(q)
    if authors:
        author = authors[0]
        await cache_author(author.dict())
        return author.dict()
    return None


# Function to get cached topic
async def get_cached_topic(topic_id: int):
    """
    Fetch topic data from cache or database by id.

    Args:
        topic_id (int): The identifier for the topic.

    Returns:
        dict: Topic data or None if not found.
    """
    topic_key = f"topic:id:{topic_id}"
    cached_topic = await redis.execute("GET", topic_key)
    if cached_topic:
        return orjson.loads(cached_topic)

    # If not in cache, fetch from the database
    with local_session() as session:
        topic = session.execute(select(Topic).where(Topic.id == topic_id)).scalar_one_or_none()
        if topic:
            topic_dict = topic.dict()
            await redis.execute("SET", topic_key, json.dumps(topic_dict, cls=CustomJSONEncoder))
            return topic_dict

    return None


# Get topic by slug from cache
async def get_cached_topic_by_slug(slug: str, get_with_stat):
    topic_key = f"topic:slug:{slug}"
    result = await redis.execute("GET", topic_key)
    if result:
        return orjson.loads(result)
    # Load from database if not found in cache
    topic_query = select(Topic).where(Topic.slug == slug)
    topics = get_with_stat(topic_query)
    if topics:
        topic_dict = topics[0].dict()
        await cache_topic(topic_dict)
        return topic_dict
    return None


# Get list of authors by ID from cache
async def get_cached_authors_by_ids(author_ids: List[int]) -> List[dict]:
    # Fetch all author data concurrently
    keys = [f"author:id:{author_id}" for author_id in author_ids]
    results = await asyncio.gather(*(redis.execute("GET", key) for key in keys))
    authors = [orjson.loads(result) if result else None for result in results]
    # Load missing authors from database and cache
    missing_indices = [index for index, author in enumerate(authors) if author is None]
    if missing_indices:
        missing_ids = [author_ids[index] for index in missing_indices]
        with local_session() as session:
            query = select(Author).where(Author.id.in_(missing_ids))
            missing_authors = session.execute(query).scalars().unique().all()
            await asyncio.gather(*(cache_author(author.dict()) for author in missing_authors))
            for index, author in zip(missing_indices, missing_authors):
                authors[index] = author.dict()
    return authors


async def get_cached_topic_followers(topic_id: int):
    """
    Получает подписчиков темы по ID, используя кеш Redis.

    Args:
        topic_id: ID темы

    Returns:
        List[dict]: Список подписчиков с их данными
    """
    try:
        cache_key = CACHE_KEYS["TOPIC_FOLLOWERS"].format(topic_id)
        cached = await redis.execute("GET", cache_key)

        if cached:
            followers_ids = orjson.loads(cached)
            logger.debug(f"Found {len(followers_ids)} cached followers for topic #{topic_id}")
            return await get_cached_authors_by_ids(followers_ids)

        with local_session() as session:
            followers_ids = [
                f[0]
                for f in session.query(Author.id)
                .join(TopicFollower, TopicFollower.follower == Author.id)
                .filter(TopicFollower.topic == topic_id)
                .all()
            ]

            await redis.execute("SETEX", cache_key, CACHE_TTL, orjson.dumps(followers_ids))
            followers = await get_cached_authors_by_ids(followers_ids)
            logger.debug(f"Cached {len(followers)} followers for topic #{topic_id}")
            return followers

    except Exception as e:
        logger.error(f"Error getting followers for topic #{topic_id}: {str(e)}")
        return []


# Get cached author followers
async def get_cached_author_followers(author_id: int):
    # Check cache for data
    cached = await redis.execute("GET", f"author:followers:{author_id}")
    if cached:
        followers_ids = orjson.loads(cached)
        followers = await get_cached_authors_by_ids(followers_ids)
        logger.debug(f"Cached followers for author #{author_id}: {len(followers)}")
        return followers

    # Query database if cache is empty
    with local_session() as session:
        followers_ids = [
            f[0]
            for f in session.query(Author.id)
            .join(AuthorFollower, AuthorFollower.follower == Author.id)
            .filter(AuthorFollower.author == author_id, Author.id != author_id)
            .all()
        ]
        await redis.execute("SET", f"author:followers:{author_id}", orjson.dumps(followers_ids))
        followers = await get_cached_authors_by_ids(followers_ids)
        return followers


# Get cached follower authors
async def get_cached_follower_authors(author_id: int):
    # Attempt to retrieve authors from cache
    cached = await redis.execute("GET", f"author:follows-authors:{author_id}")
    if cached:
        authors_ids = orjson.loads(cached)
    else:
        # Query authors from database
        with local_session() as session:
            authors_ids = [
                a[0]
                for a in session.execute(
                    select(Author.id)
                    .select_from(join(Author, AuthorFollower, Author.id == AuthorFollower.author))
                    .where(AuthorFollower.follower == author_id)
                ).all()
            ]
            await redis.execute("SET", f"author:follows-authors:{author_id}", orjson.dumps(authors_ids))

    authors = await get_cached_authors_by_ids(authors_ids)
    return authors


# Get cached follower topics
async def get_cached_follower_topics(author_id: int):
    # Attempt to retrieve topics from cache
    cached = await redis.execute("GET", f"author:follows-topics:{author_id}")
    if cached:
        topics_ids = orjson.loads(cached)
    else:
        # Load topics from database and cache them
        with local_session() as session:
            topics_ids = [
                t[0]
                for t in session.query(Topic.id)
                .join(TopicFollower, TopicFollower.topic == Topic.id)
                .where(TopicFollower.follower == author_id)
                .all()
            ]
            await redis.execute("SET", f"author:follows-topics:{author_id}", orjson.dumps(topics_ids))

    topics = []
    for topic_id in topics_ids:
        topic_str = await redis.execute("GET", f"topic:id:{topic_id}")
        if topic_str:
            topic = orjson.loads(topic_str)
            if topic and topic not in topics:
                topics.append(topic)

    logger.debug(f"Cached topics for author#{author_id}: {len(topics)}")
    return topics


# Get author by author_id from cache
async def get_cached_author_by_id(author_id: int, get_with_stat):
    """
    Retrieve author information by author_id, checking the cache first, then the database.

    Args:
        author_id (int): The author identifier for which to retrieve the author.

    Returns:
        dict: Dictionary with author data or None if not found.
    """
    # Attempt to find author data by author_id in Redis cache
    cached_author_data = await redis.execute("GET", f"author:id:{author_id}")
    if cached_author_data:
        # If data is found, return parsed JSON
        return orjson.loads(cached_author_data)

    # If data is not found in cache, query the database
    author_query = select(Author).where(Author.id == author_id)
    authors = get_with_stat(author_query)
    if authors:
        # Cache the retrieved author data
        author = authors[0]
        author_dict = author.dict()
        await asyncio.gather(
            redis.execute("SET", f"author:id:{author.id}", orjson.dumps(author_dict)),
        )
        return author_dict

    # Return None if author is not found
    return None


# Get cached topic authors
async def get_cached_topic_authors(topic_id: int):
    """
    Retrieve a list of authors for a given topic, using cache or database.

    Args:
        topic_id (int): The identifier of the topic for which to retrieve authors.

    Returns:
        List[dict]: A list of dictionaries containing author data.
    """
    # Attempt to get a list of author IDs from cache
    rkey = f"topic:authors:{topic_id}"
    cached_authors_ids = await redis.execute("GET", rkey)
    if cached_authors_ids:
        authors_ids = orjson.loads(cached_authors_ids)
    else:
        # If cache is empty, get data from the database
        with local_session() as session:
            query = (
                select(ShoutAuthor.author)
                .select_from(join(ShoutTopic, Shout, ShoutTopic.shout == Shout.id))
                .join(ShoutAuthor, ShoutAuthor.shout == Shout.id)
                .where(
                    and_(
                        ShoutTopic.topic == topic_id,
                        Shout.published_at.is_not(None),
                        Shout.deleted_at.is_(None),
                    )
                )
            )
            authors_ids = [author_id for (author_id,) in session.execute(query).all()]
            # Cache the retrieved author IDs
            await redis.execute("SET", rkey, orjson.dumps(authors_ids))

    # Retrieve full author details from cached IDs
    if authors_ids:
        authors = await get_cached_authors_by_ids(authors_ids)
        logger.debug(f"Topic#{topic_id} authors fetched and cached: {len(authors)} authors found.")
        return authors

    return []


async def invalidate_shouts_cache(cache_keys: List[str]):
    """
    Инвалидирует кэш выборок публикаций по переданным ключам.
    """
    for cache_key in cache_keys:
        try:
            # Удаляем основной кэш
            await redis.execute("DEL", cache_key)
            logger.debug(f"Invalidated cache key: {cache_key}")

            # Добавляем ключ в список инвалидированных с TTL
            await redis.execute("SETEX", f"{cache_key}:invalidated", CACHE_TTL, "1")

            # Если это кэш темы, инвалидируем также связанные ключи
            if cache_key.startswith("topic_"):
                topic_id = cache_key.split("_")[1]
                related_keys = [
                    f"topic:id:{topic_id}",
                    f"topic:authors:{topic_id}",
                    f"topic:followers:{topic_id}",
                    f"topic:stats:{topic_id}",
                ]
                for related_key in related_keys:
                    await redis.execute("DEL", related_key)
                    logger.debug(f"Invalidated related key: {related_key}")

        except Exception as e:
            logger.error(f"Error invalidating cache key {cache_key}: {e}")


async def cache_topic_shouts(topic_id: int, shouts: List[dict]):
    """Кэширует список публикаций для темы"""
    key = f"topic_shouts_{topic_id}"
    payload = json.dumps(shouts, cls=CustomJSONEncoder)
    await redis.execute("SETEX", key, CACHE_TTL, payload)


async def get_cached_topic_shouts(topic_id: int) -> List[dict]:
    """Получает кэшированный список публикаций для темы"""
    key = f"topic_shouts_{topic_id}"
    cached = await redis.execute("GET", key)
    if cached:
        return orjson.loads(cached)
    return None


async def cache_related_entities(shout: Shout):
    """
    Кэширует все связанные с публикацией сущности (авторов и темы)
    """
    tasks = []
    for author in shout.authors:
        tasks.append(cache_by_id(Author, author.id, cache_author))
    for topic in shout.topics:
        tasks.append(cache_by_id(Topic, topic.id, cache_topic))
    await asyncio.gather(*tasks)


async def invalidate_shout_related_cache(shout: Shout, author_id: int):
    """
    Инвалидирует весь кэш, связанный с публикацией и её связями

    Args:
        shout: Объект публикации
        author_id: ID автора
    """
    cache_keys = {
        "feed",  # основная лента
        f"author_{author_id}",  # публикации автора
        "random_top",  # случайные топовые
        "unrated",  # неоцененные
        "recent",  # последние
        "coauthored",  # совместные
    }

    # Добавляем ключи авторов
    cache_keys.update(f"author_{a.id}" for a in shout.authors)
    cache_keys.update(f"authored_{a.id}" for a in shout.authors)

    # Добавляем ключи тем
    cache_keys.update(f"topic_{t.id}" for t in shout.topics)
    cache_keys.update(f"topic_shouts_{t.id}" for t in shout.topics)

    await invalidate_shouts_cache(list(cache_keys))


# Function removed - direct Redis calls used throughout the module instead


async def get_cached_entity(entity_type: str, entity_id: int, get_method, cache_method):
    """
    Универсальная функция получения кэшированной сущности

    Args:
        entity_type: 'author' или 'topic'
        entity_id: ID сущности
        get_method: метод получения из БД
        cache_method: метод кэширования
    """
    key = f"{entity_type}:id:{entity_id}"
    cached = await redis.execute("GET", key)
    if cached:
        return orjson.loads(cached)

    entity = await get_method(entity_id)
    if entity:
        await cache_method(entity)
        return entity
    return None


async def cache_by_id(entity, entity_id: int, cache_method):
    """
    Кэширует сущность по ID, используя указанный метод кэширования

    Args:
        entity: класс сущности (Author/Topic)
        entity_id: ID сущности
        cache_method: функция кэширования
    """
    from resolvers.stat import get_with_stat

    caching_query = select(entity).filter(entity.id == entity_id)
    result = get_with_stat(caching_query)
    if not result or not result[0]:
        logger.warning(f"{entity.__name__} with id {entity_id} not found")
        return
    x = result[0]
    d = x.dict()
    await cache_method(d)
    return d


# Универсальная функция для сохранения данных в кеш
async def cache_data(key: str, data: Any, ttl: Optional[int] = None) -> None:
    """
    Сохраняет данные в кеш по указанному ключу.

    Args:
        key: Ключ кеша
        data: Данные для сохранения
        ttl: Время жизни кеша в секундах (None - бессрочно)
    """
    try:
        payload = json.dumps(data, cls=CustomJSONEncoder)
        if ttl:
            await redis.execute("SETEX", key, ttl, payload)
        else:
            await redis.execute("SET", key, payload)
        logger.debug(f"Данные сохранены в кеш по ключу {key}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в кеш: {e}")


# Универсальная функция для получения данных из кеша
async def get_cached_data(key: str) -> Optional[Any]:
    """
    Получает данные из кеша по указанному ключу.

    Args:
        key: Ключ кеша

    Returns:
        Any: Данные из кеша или None, если данных нет
    """
    try:
        cached_data = await redis.execute("GET", key)
        if cached_data:
            loaded = orjson.loads(cached_data)
            logger.debug(f"Данные получены из кеша по ключу {key}: {len(loaded)}")
            return loaded
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении данных из кеша: {e}")
        return None


# Универсальная функция для инвалидации кеша по префиксу
async def invalidate_cache_by_prefix(prefix: str) -> None:
    """
    Инвалидирует все ключи кеша с указанным префиксом.

    Args:
        prefix: Префикс ключей кеша для инвалидации
    """
    try:
        keys = await redis.execute("KEYS", f"{prefix}:*")
        if keys:
            await redis.execute("DEL", *keys)
            logger.debug(f"Удалено {len(keys)} ключей кеша с префиксом {prefix}")
    except Exception as e:
        logger.error(f"Ошибка при инвалидации кеша: {e}")


# Универсальная функция для получения и кеширования данных
async def cached_query(
    cache_key: str,
    query_func: callable,
    ttl: Optional[int] = None,
    force_refresh: bool = False,
    use_key_format: bool = True,
    **query_params,
) -> Any:
    """
    Gets data from cache or executes query and saves result to cache.
    Supports existing key formats for compatibility.

    Args:
        cache_key: Cache key or key template from CACHE_KEYS
        query_func: Function to execute the query
        ttl: Cache TTL in seconds (None - indefinite)
        force_refresh: Force cache refresh
        use_key_format: Whether to check if cache_key matches a key template in CACHE_KEYS
        **query_params: Parameters to pass to the query function

    Returns:
        Any: Data from cache or query result
    """
    # Check if cache_key matches a pattern in CACHE_KEYS
    actual_key = cache_key
    if use_key_format and "{}" in cache_key:
        # Look for a template match in CACHE_KEYS
        for key_name, key_format in CACHE_KEYS.items():
            if cache_key == key_format:
                # We have a match, now look for the id or value to format with
                for param_name, param_value in query_params.items():
                    if param_name in ["id", "slug", "user", "topic_id", "author_id"]:
                        actual_key = cache_key.format(param_value)
                        break

    # If not forcing refresh, try to get data from cache
    if not force_refresh:
        cached_result = await get_cached_data(actual_key)
        if cached_result is not None:
            return cached_result

    # If data not in cache or refresh required, execute query
    try:
        result = await query_func(**query_params)
        if result is not None:
            # Save result to cache
            await cache_data(actual_key, result, ttl)
        return result
    except Exception as e:
        logger.error(f"Error executing query for caching: {e}")
        # In case of error, return data from cache if not forcing refresh
        if not force_refresh:
            return await get_cached_data(actual_key)
        raise
