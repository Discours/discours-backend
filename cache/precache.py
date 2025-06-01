import asyncio

from sqlalchemy import and_, join, select

from auth.orm import Author, AuthorFollower
from cache.cache import cache_author, cache_topic
from orm.shout import Shout, ShoutAuthor, ShoutReactionsFollower, ShoutTopic
from orm.topic import Topic, TopicFollower
from resolvers.stat import get_with_stat
from services.db import local_session
from services.redis import redis
from utils.encoders import fast_json_dumps
from utils.logger import root_logger as logger


# Предварительное кеширование подписчиков автора
async def precache_authors_followers(author_id, session) -> None:
    authors_followers: set[int] = set()
    followers_query = select(AuthorFollower.follower).where(AuthorFollower.author == author_id)
    result = session.execute(followers_query)
    authors_followers.update(row[0] for row in result if row[0])

    followers_payload = fast_json_dumps(list(authors_followers))
    await redis.execute("SET", f"author:followers:{author_id}", followers_payload)


# Предварительное кеширование подписок автора
async def precache_authors_follows(author_id, session) -> None:
    follows_topics_query = select(TopicFollower.topic).where(TopicFollower.follower == author_id)
    follows_authors_query = select(AuthorFollower.author).where(AuthorFollower.follower == author_id)
    follows_shouts_query = select(ShoutReactionsFollower.shout).where(ShoutReactionsFollower.follower == author_id)

    follows_topics = {row[0] for row in session.execute(follows_topics_query) if row[0]}
    follows_authors = {row[0] for row in session.execute(follows_authors_query) if row[0]}
    follows_shouts = {row[0] for row in session.execute(follows_shouts_query) if row[0]}

    topics_payload = fast_json_dumps(list(follows_topics))
    authors_payload = fast_json_dumps(list(follows_authors))
    shouts_payload = fast_json_dumps(list(follows_shouts))

    await asyncio.gather(
        redis.execute("SET", f"author:follows-topics:{author_id}", topics_payload),
        redis.execute("SET", f"author:follows-authors:{author_id}", authors_payload),
        redis.execute("SET", f"author:follows-shouts:{author_id}", shouts_payload),
    )


# Предварительное кеширование авторов тем
async def precache_topics_authors(topic_id: int, session) -> None:
    topic_authors_query = (
        select(ShoutAuthor.author)
        .select_from(join(ShoutTopic, Shout, ShoutTopic.shout == Shout.id))
        .join(ShoutAuthor, ShoutAuthor.shout == Shout.id)
        .filter(
            and_(
                ShoutTopic.topic == topic_id,
                Shout.published_at.is_not(None),
                Shout.deleted_at.is_(None),
            )
        )
    )
    topic_authors = {row[0] for row in session.execute(topic_authors_query) if row[0]}

    authors_payload = fast_json_dumps(list(topic_authors))
    await redis.execute("SET", f"topic:authors:{topic_id}", authors_payload)


# Предварительное кеширование подписчиков тем
async def precache_topics_followers(topic_id: int, session) -> None:
    followers_query = select(TopicFollower.follower).where(TopicFollower.topic == topic_id)
    topic_followers = {row[0] for row in session.execute(followers_query) if row[0]}

    followers_payload = fast_json_dumps(list(topic_followers))
    await redis.execute("SET", f"topic:followers:{topic_id}", followers_payload)


async def precache_data() -> None:
    logger.info("precaching...")
    try:
        # Список паттернов ключей, которые нужно сохранить при FLUSHDB
        preserve_patterns = [
            "migrated_views_*",  # Данные миграции просмотров
            "session:*",  # Сессии пользователей
            "env_vars:*",  # Переменные окружения
            "oauth_*",  # OAuth токены
        ]

        # Сохраняем все важные ключи перед очисткой
        all_keys_to_preserve = []
        preserved_data = {}

        for pattern in preserve_patterns:
            keys = await redis.execute("KEYS", pattern)
            if keys:
                all_keys_to_preserve.extend(keys)
                logger.info(f"Найдено {len(keys)} ключей по паттерну '{pattern}'")

        if all_keys_to_preserve:
            logger.info(f"Сохраняем {len(all_keys_to_preserve)} важных ключей перед FLUSHDB")
            for key in all_keys_to_preserve:
                try:
                    # Определяем тип ключа и сохраняем данные
                    key_type = await redis.execute("TYPE", key)
                    if key_type == "hash":
                        preserved_data[key] = await redis.execute("HGETALL", key)
                    elif key_type == "string":
                        preserved_data[key] = await redis.execute("GET", key)
                    elif key_type == "set":
                        preserved_data[key] = await redis.execute("SMEMBERS", key)
                    elif key_type == "list":
                        preserved_data[key] = await redis.execute("LRANGE", key, 0, -1)
                    elif key_type == "zset":
                        preserved_data[key] = await redis.execute("ZRANGE", key, 0, -1, "WITHSCORES")
                except Exception as e:
                    logger.error(f"Ошибка при сохранении ключа {key}: {e}")
                    continue

        await redis.execute("FLUSHDB")
        logger.info("redis: FLUSHDB")

        # Восстанавливаем все сохранённые ключи
        if preserved_data:
            logger.info(f"Восстанавливаем {len(preserved_data)} сохранённых ключей")
            for key, data in preserved_data.items():
                try:
                    if isinstance(data, dict) and data:
                        # Hash
                        flattened = []
                        for field, val in data.items():
                            flattened.extend([field, val])
                        if flattened:
                            await redis.execute("HSET", key, *flattened)
                    elif isinstance(data, str) and data:
                        # String
                        await redis.execute("SET", key, data)
                    elif isinstance(data, list) and data:
                        # List или ZSet
                        if any(isinstance(item, (list, tuple)) and len(item) == 2 for item in data):
                            # ZSet with scores
                            for item in data:
                                if isinstance(item, (list, tuple)) and len(item) == 2:
                                    await redis.execute("ZADD", key, item[1], item[0])
                        else:
                            # Regular list
                            await redis.execute("LPUSH", key, *data)
                    elif isinstance(data, set) and data:
                        # Set
                        await redis.execute("SADD", key, *data)
                except Exception as e:
                    logger.error(f"Ошибка при восстановлении ключа {key}: {e}")
                    continue

        with local_session() as session:
            # topics
            q = select(Topic).where(Topic.community == 1)
            topics = get_with_stat(q)
            for topic in topics:
                topic_dict = topic.dict() if hasattr(topic, "dict") else topic
                await cache_topic(topic_dict)
                await asyncio.gather(
                    precache_topics_followers(topic_dict["id"], session),
                    precache_topics_authors(topic_dict["id"], session),
                )
            logger.info(f"{len(topics)} topics and their followings precached")

            # authors
            authors = get_with_stat(select(Author))
            # logger.info(f"{len(authors)} authors found in database")
            for author in authors:
                if isinstance(author, Author):
                    profile = author.dict()
                    author_id = profile.get("id")
                    # user_id = profile.get("user", "").strip()
                    if author_id:  # and user_id:
                        await cache_author(profile)
                        await asyncio.gather(
                            precache_authors_followers(author_id, session),
                            precache_authors_follows(author_id, session),
                        )
                else:
                    logger.error(f"fail caching {author}")
            logger.info(f"{len(authors)} authors and their followings precached")
    except Exception as exc:
        import traceback

        traceback.print_exc()
        logger.error(f"Error in precache_data: {exc}")
