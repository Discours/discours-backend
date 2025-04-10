from sqlalchemy import desc, select, text

from cache.cache import (
    cache_topic,
    cached_query,
    get_cached_topic_authors,
    get_cached_topic_by_slug,
    get_cached_topic_followers,
    invalidate_cache_by_prefix
)
from orm.author import Author
from orm.topic import Topic
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
    cache_key = "topics:all:basic"

    # Функция для получения всех тем из БД
    async def fetch_all_topics():
        logger.debug("Получаем список всех тем из БД и кешируем результат")

        with local_session() as session:
            # Запрос на получение базовой информации о темах
            topics_query = select(Topic)
            topics = session.execute(topics_query).scalars().all()

            # Преобразуем темы в словари
            return [topic.dict() for topic in topics]

    # Используем универсальную функцию для кеширования запросов
    return await cached_query(cache_key, fetch_all_topics)


# Вспомогательная функция для получения тем со статистикой с пагинацией
async def get_topics_with_stats(limit=100, offset=0, community_id=None, by=None):
    """
    Получает темы со статистикой с пагинацией.

    Args:
        limit: Максимальное количество возвращаемых тем
        offset: Смещение для пагинации
        community_id: Опциональный ID сообщества для фильтрации
        by: Опциональный параметр сортировки

    Returns:
        list: Список тем с их статистикой
    """
    # Формируем ключ кеша с помощью универсальной функции
    cache_key = f"topics:stats:limit={limit}:offset={offset}:community_id={community_id}"

    # Функция для получения тем из БД
    async def fetch_topics_with_stats():
        logger.debug(f"Выполняем запрос на получение тем со статистикой: limit={limit}, offset={offset}")

        with local_session() as session:
            # Базовый запрос для получения тем
            base_query = select(Topic)

            # Добавляем фильтр по сообществу, если указан
            if community_id:
                base_query = base_query.where(Topic.community == community_id)

            # Применяем сортировку на основе параметра by
            if by:
                if isinstance(by, dict):
                    # Обработка словаря параметров сортировки
                    for field, direction in by.items():
                        column = getattr(Topic, field, None)
                        if column:
                            if direction.lower() == "desc":
                                base_query = base_query.order_by(desc(column))
                            else:
                                base_query = base_query.order_by(column)
                elif by == "popular":
                    # Сортировка по популярности (количеству публикаций)
                    # Примечание: это требует дополнительного запроса или подзапроса
                    base_query = base_query.order_by(
                        desc(Topic.id)
                    )  # Временно, нужно заменить на proper implementation
                else:
                    # По умолчанию сортируем по ID в обратном порядке
                    base_query = base_query.order_by(desc(Topic.id))
            else:
                # По умолчанию сортируем по ID в обратном порядке
                base_query = base_query.order_by(desc(Topic.id))

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
            
            # Запрос на получение статистики авторов для выбранных тем
            authors_stats_query = f"""
            SELECT st.topic, COUNT(DISTINCT sa.author) as authors_count
            FROM shout_topic st
            JOIN shout s ON st.shout = s.id AND s.deleted_at IS NULL AND s.published_at IS NOT NULL
            JOIN shout_author sa ON sa.shout = s.id
            WHERE st.topic IN ({",".join(map(str, topic_ids))})
            GROUP BY st.topic
            """
            authors_stats = {row[0]: row[1] for row in session.execute(text(authors_stats_query))}

            # Запрос на получение статистики комментариев для выбранных тем
            comments_stats_query = f"""
            SELECT st.topic, COUNT(DISTINCT r.id) as comments_count
            FROM shout_topic st
            JOIN shout s ON st.shout = s.id AND s.deleted_at IS NULL AND s.published_at IS NOT NULL
            JOIN reaction r ON r.shout = s.id
            WHERE st.topic IN ({",".join(map(str, topic_ids))})
            GROUP BY st.topic
            """
            comments_stats = {row[0]: row[1] for row in session.execute(text(comments_stats_query))}


            # Формируем результат с добавлением статистики
            result = []
            for topic in topics:
                topic_dict = topic.dict()
                topic_dict["stat"] = {
                    "shouts": shouts_stats.get(topic.id, 0),
                    "followers": followers_stats.get(topic.id, 0),
                    "authors": authors_stats.get(topic.id, 0),
                    "comments": comments_stats.get(topic.id, 0)
                }
                result.append(topic_dict)

                # Кешируем каждую тему отдельно для использования в других функциях
                await cache_topic(topic_dict)

            return result

    # Используем универсальную функцию для кеширования запросов
    return await cached_query(cache_key, fetch_topics_with_stats)


# Функция для инвалидации кеша тем
async def invalidate_topics_cache(topic_id=None):
    """
    Инвалидирует кеши тем при изменении данных.

    Args:
        topic_id: Опциональный ID темы для точечной инвалидации.
               Если не указан, инвалидируются все кеши тем.
    """
    if topic_id:
        # Точечная инвалидация конкретной темы
        logger.debug(f"Инвалидация кеша для темы #{topic_id}")
        specific_keys = [
            f"topic:id:{topic_id}",
            f"topic:authors:{topic_id}",
            f"topic:followers:{topic_id}",
            f"topic_shouts_{topic_id}",
        ]

        # Получаем slug темы, если есть
        with local_session() as session:
            topic = session.query(Topic).filter(Topic.id == topic_id).first()
            if topic and topic.slug:
                specific_keys.append(f"topic:slug:{topic.slug}")

        # Удаляем конкретные ключи
        for key in specific_keys:
            try:
                await redis.execute("DEL", key)
                logger.debug(f"Удален ключ кеша {key}")
            except Exception as e:
                logger.error(f"Ошибка при удалении ключа {key}: {e}")

        # Также ищем и удаляем ключи коллекций, содержащих данные об этой теме
        collection_keys = await redis.execute("KEYS", "topics:stats:*")
        if collection_keys:
            await redis.execute("DEL", *collection_keys)
            logger.debug(f"Удалено {len(collection_keys)} коллекционных ключей тем")
    else:
        # Общая инвалидация всех кешей тем
        logger.debug("Полная инвалидация кеша тем")
        await invalidate_cache_by_prefix("topics")


# Запрос на получение всех тем
@query.field("get_topics_all")
async def get_topics_all(_, _info):
    """
    Получает список всех тем без статистики.

    Returns:
        list: Список всех тем
    """
    return await get_all_topics()


# Запрос на получение тем по сообществу
@query.field("get_topics_by_community")
async def get_topics_by_community(_, _info, community_id: int, limit=100, offset=0, by=None):
    """
    Получает список тем, принадлежащих указанному сообществу с пагинацией и статистикой.

    Args:
        community_id: ID сообщества
        limit: Максимальное количество возвращаемых тем
        offset: Смещение для пагинации
        by: Опциональные параметры сортировки

    Returns:
        list: Список тем с их статистикой
    """
    return await get_topics_with_stats(limit, offset, community_id, by)


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
            old_slug = topic.slug
            Topic.update(topic, topic_input)
            session.add(topic)
            session.commit()

            # Инвалидируем кеш только для этой конкретной темы
            await invalidate_topics_cache(topic.id)

            # Если slug изменился, удаляем старый ключ
            if old_slug != topic.slug:
                await redis.execute("DEL", f"topic:slug:{old_slug}")
                logger.debug(f"Удален ключ кеша для старого slug: {old_slug}")

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
