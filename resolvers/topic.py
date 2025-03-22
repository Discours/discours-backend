import time

from sqlalchemy import func, select, text

from cache.cache import (
    cache_topic,
    get_cached_topic_authors,
    get_cached_topic_by_slug,
    get_cached_topic_followers,
    redis_operation,
)
from cache.memorycache import cache_region
from orm.author import Author
from orm.shout import Shout, ShoutTopic
from orm.topic import Topic, TopicFollower
from resolvers.stat import get_with_stat
from services.auth import login_required
from services.db import local_session
from services.redis import redis
from services.schema import mutation, query
from utils.logger import root_logger as logger


# Вспомогательная функция для получения всех тем без статистики
async def get_all_topics():
    """
    Получает все темы без статистики.
    Используется для случаев, когда нужен полный список тем без дополнительной информации.

    Returns:
        list: Список всех тем без статистики
    """
    # Пытаемся получить данные из кеша
    cached_topics = await redis_operation("GET", "topics:all:basic")

    if cached_topics:
        logger.debug("Используем кешированные базовые данные о темах из Redis")
        try:
            import json

            return json.loads(cached_topics)
        except Exception as e:
            logger.error(f"Ошибка при десериализации тем из Redis: {e}")

    # Если в кеше нет данных, выполняем запрос в БД
    logger.debug("Получаем список всех тем из БД и кешируем результат")

    with local_session() as session:
        # Запрос на получение базовой информации о темах
        topics_query = select(Topic)
        topics = session.execute(topics_query).scalars().all()

        # Преобразуем темы в словари
        result = [topic.dict() for topic in topics]

    # Кешируем результат в Redis без TTL (будет обновляться только при изменениях)
    try:
        import json

        await redis_operation("SET", "topics:all:basic", json.dumps(result))
    except Exception as e:
        logger.error(f"Ошибка при кешировании тем в Redis: {e}")

    return result


# Вспомогательная функция для получения тем со статистикой с пагинацией
async def get_topics_with_stats(limit=100, offset=0, community_id=None):
    """
    Получает темы со статистикой с пагинацией.

    Args:
        limit: Максимальное количество возвращаемых тем
        offset: Смещение для пагинации
        community_id: Опциональный ID сообщества для фильтрации

    Returns:
        list: Список тем с их статистикой
    """
    # Формируем ключ кеша с учетом параметров
    cache_key = f"topics:stats:limit={limit}:offset={offset}"
    if community_id:
        cache_key += f":community={community_id}"

    # Пытаемся получить данные из кеша
    cached_topics = await redis_operation("GET", cache_key)

    if cached_topics:
        logger.debug(f"Используем кешированные данные о темах из Redis: {cache_key}")
        try:
            import json

            return json.loads(cached_topics)
        except Exception as e:
            logger.error(f"Ошибка при десериализации тем из Redis: {e}")

    # Если в кеше нет данных, выполняем оптимизированный запрос
    logger.debug(f"Выполняем запрос на получение тем со статистикой: limit={limit}, offset={offset}")

    with local_session() as session:
        # Базовый запрос для получения тем
        base_query = select(Topic)

        # Добавляем фильтр по сообществу, если указан
        if community_id:
            base_query = base_query.where(Topic.community == community_id)

        # Применяем лимит и смещение
        base_query = base_query.limit(limit).offset(offset)

        # Получаем темы
        topics = session.execute(base_query).scalars().all()
        topic_ids = [topic.id for topic in topics]

        if not topic_ids:
            return []

        # Запрос на получение статистики по публикациям для выбранных тем
        shouts_stats_query = f"""
        SELECT st.topic, COUNT(DISTINCT s.id) as shouts_count
        FROM shout_topic st
        JOIN shout s ON st.shout = s.id AND s.deleted_at IS NULL
        WHERE st.topic IN ({",".join(map(str, topic_ids))})
        GROUP BY st.topic
        """
        shouts_stats = {row[0]: row[1] for row in session.execute(text(shouts_stats_query))}

        # Запрос на получение статистики по подписчикам для выбранных тем
        followers_stats_query = f"""
        SELECT topic, COUNT(DISTINCT follower) as followers_count
        FROM topic_followers
        WHERE topic IN ({",".join(map(str, topic_ids))})
        GROUP BY topic
        """
        followers_stats = {row[0]: row[1] for row in session.execute(text(followers_stats_query))}

        # Формируем результат с добавлением статистики
        result = []
        for topic in topics:
            topic_dict = topic.dict()
            topic_dict["stat"] = {
                "shouts": shouts_stats.get(topic.id, 0),
                "followers": followers_stats.get(topic.id, 0),
            }
            result.append(topic_dict)

            # Кешируем каждую тему отдельно для использования в других функциях
            await cache_topic(topic_dict)

    # Кешируем полный результат в Redis без TTL (будет обновляться только при изменениях)
    try:
        import json

        await redis_operation("SET", cache_key, json.dumps(result))
    except Exception as e:
        logger.error(f"Ошибка при кешировании тем в Redis: {e}")

    return result


# Функция для инвалидации кеша тем
async def invalidate_topics_cache():
    """
    Инвалидирует все кеши тем при изменении данных.
    """
    logger.debug("Инвалидация кеша тем")

    # Получаем все ключи, начинающиеся с "topics:"
    topic_keys = await redis.execute("KEYS", "topics:*")

    if topic_keys:
        # Удаляем все найденные ключи
        await redis.execute("DEL", *topic_keys)
        logger.debug(f"Удалено {len(topic_keys)} ключей кеша тем")


# Запрос на получение всех тем
@query.field("get_topics_all")
async def get_topics_all(_, _info):
    """
    Получает список всех тем без статистики.

    Returns:
        list: Список всех тем
    """
    return await get_all_topics()


# Запрос на получение тем с пагинацией и статистикой
@query.field("get_topics_paginated")
async def get_topics_paginated(_, _info, limit=100, offset=0):
    """
    Получает список тем с пагинацией и статистикой.

    Args:
        limit: Максимальное количество возвращаемых тем
        offset: Смещение для пагинации

    Returns:
        list: Список тем с их статистикой
    """
    return await get_topics_with_stats(limit, offset)


# Запрос на получение тем по сообществу
@query.field("get_topics_by_community")
async def get_topics_by_community(_, _info, community_id: int, limit=100, offset=0):
    """
    Получает список тем, принадлежащих указанному сообществу с пагинацией и статистикой.

    Args:
        community_id: ID сообщества
        limit: Максимальное количество возвращаемых тем
        offset: Смещение для пагинации

    Returns:
        list: Список тем с их статистикой
    """
    return await get_topics_with_stats(limit, offset, community_id)


# Запрос на получение тем по автору
@query.field("get_topics_by_author")
async def get_topics_by_author(_, _info, author_id=0, slug="", user=""):
    topics_by_author_query = select(Topic)
    if author_id:
        topics_by_author_query = topics_by_author_query.join(Author).where(Author.id == author_id)
    elif slug:
        topics_by_author_query = topics_by_author_query.join(Author).where(Author.slug == slug)
    elif user:
        topics_by_author_query = topics_by_author_query.join(Author).where(Author.user == user)

    return get_with_stat(topics_by_author_query)


# Запрос на получение одной темы по её slug
@query.field("get_topic")
async def get_topic(_, _info, slug: str):
    topic = await get_cached_topic_by_slug(slug, get_with_stat)
    if topic:
        return topic


# Мутация для создания новой темы
@mutation.field("create_topic")
@login_required
async def create_topic(_, _info, topic_input):
    with local_session() as session:
        # TODO: проверить права пользователя на создание темы для конкретного сообщества
        # и разрешение на создание
        new_topic = Topic(**topic_input)
        session.add(new_topic)
        session.commit()

        # Инвалидируем кеш всех тем
        await invalidate_topics_cache()

        return {"topic": new_topic}


# Мутация для обновления темы
@mutation.field("update_topic")
@login_required
async def update_topic(_, _info, topic_input):
    slug = topic_input["slug"]
    with local_session() as session:
        topic = session.query(Topic).filter(Topic.slug == slug).first()
        if not topic:
            return {"error": "topic not found"}
        else:
            Topic.update(topic, topic_input)
            session.add(topic)
            session.commit()

            # Инвалидируем кеш всех тем и конкретной темы
            await invalidate_topics_cache()
            await redis.execute("DEL", f"topic:slug:{slug}")
            await redis.execute("DEL", f"topic:id:{topic.id}")

            return {"topic": topic}


# Мутация для удаления темы
@mutation.field("delete_topic")
@login_required
async def delete_topic(_, info, slug: str):
    user_id = info.context["user_id"]
    with local_session() as session:
        t: Topic = session.query(Topic).filter(Topic.slug == slug).first()
        if not t:
            return {"error": "invalid topic slug"}
        author = session.query(Author).filter(Author.user == user_id).first()
        if author:
            if t.created_by != author.id:
                return {"error": "access denied"}

            session.delete(t)
            session.commit()

            # Инвалидируем кеш всех тем и конкретной темы
            await invalidate_topics_cache()
            await redis.execute("DEL", f"topic:slug:{slug}")
            await redis.execute("DEL", f"topic:id:{t.id}")

            return {}
    return {"error": "access denied"}


# Запрос на получение подписчиков темы
@query.field("get_topic_followers")
async def get_topic_followers(_, _info, slug: str):
    logger.debug(f"getting followers for @{slug}")
    topic = await get_cached_topic_by_slug(slug, get_with_stat)
    topic_id = topic.id if isinstance(topic, Topic) else topic.get("id")
    followers = await get_cached_topic_followers(topic_id)
    return followers


# Запрос на получение авторов темы
@query.field("get_topic_authors")
async def get_topic_authors(_, _info, slug: str):
    logger.debug(f"getting authors for @{slug}")
    topic = await get_cached_topic_by_slug(slug, get_with_stat)
    topic_id = topic.id if isinstance(topic, Topic) else topic.get("id")
    authors = await get_cached_topic_authors(topic_id)
    return authors
