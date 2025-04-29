import asyncio
import time
from typing import Optional

from sqlalchemy import select, text

from cache.cache import (
    cache_author,
    cached_query,
    get_cached_author,
    get_cached_author_by_user_id,
    get_cached_author_followers,
    get_cached_follower_authors,
    get_cached_follower_topics,
    invalidate_cache_by_prefix,
)
from orm.author import Author
from resolvers.stat import get_with_stat
from services.auth import login_required
from services.db import local_session
from services.redis import redis
from services.schema import mutation, query
from services.search import search_service
from utils.logger import root_logger as logger

DEFAULT_COMMUNITIES = [1]


# Вспомогательная функция для получения всех авторов без статистики
async def get_all_authors():
    """
    Получает всех авторов без статистики.
    Используется для случаев, когда нужен полный список авторов без дополнительной информации.

    Returns:
        list: Список всех авторов без статистики
    """
    cache_key = "authors:all:basic"

    # Функция для получения всех авторов из БД
    async def fetch_all_authors():
        logger.debug("Получаем список всех авторов из БД и кешируем результат")

        with local_session() as session:
            # Запрос на получение базовой информации об авторах
            authors_query = select(Author).where(Author.deleted_at.is_(None))
            authors = session.execute(authors_query).scalars().all()

            # Преобразуем авторов в словари
            return [author.dict() for author in authors]

    # Используем универсальную функцию для кеширования запросов
    return await cached_query(cache_key, fetch_all_authors)


# Вспомогательная функция для получения авторов со статистикой с пагинацией
async def get_authors_with_stats(limit=50, offset=0, by: Optional[str] = None):
    """
    Получает авторов со статистикой с пагинацией.

    Args:
        limit: Максимальное количество возвращаемых авторов
        offset: Смещение для пагинации
        by: Опциональный параметр сортировки (new/active)

    Returns:
        list: Список авторов с их статистикой
    """
    # Формируем ключ кеша с помощью универсальной функции
    cache_key = f"authors:stats:limit={limit}:offset={offset}"

    # Функция для получения авторов из БД
    async def fetch_authors_with_stats():
        logger.debug(f"Выполняем запрос на получение авторов со статистикой: limit={limit}, offset={offset}, by={by}")

        with local_session() as session:
            # Базовый запрос для получения авторов
            base_query = select(Author).where(Author.deleted_at.is_(None))

            # Применяем сортировку
            if by:
                if isinstance(by, dict):
                    # Обработка словаря параметров сортировки
                    from sqlalchemy import asc, desc

                    for field, direction in by.items():
                        column = getattr(Author, field, None)
                        if column:
                            if direction.lower() == "desc":
                                base_query = base_query.order_by(desc(column))
                            else:
                                base_query = base_query.order_by(column)
                elif by == "new":
                    base_query = base_query.order_by(desc(Author.created_at))
                elif by == "active":
                    base_query = base_query.order_by(desc(Author.last_seen))
                else:
                    # По умолчанию сортируем по времени создания
                    base_query = base_query.order_by(desc(Author.created_at))
            else:
                base_query = base_query.order_by(desc(Author.created_at))

            # Применяем лимит и смещение
            base_query = base_query.limit(limit).offset(offset)

            # Получаем авторов
            authors = session.execute(base_query).scalars().all()
            author_ids = [author.id for author in authors]

            if not author_ids:
                return []

            # Оптимизированный запрос для получения статистики по публикациям для авторов
            shouts_stats_query = f"""
            SELECT sa.author, COUNT(DISTINCT s.id) as shouts_count
            FROM shout_author sa
            JOIN shout s ON sa.shout = s.id AND s.deleted_at IS NULL AND s.published_at IS NOT NULL
            WHERE sa.author IN ({",".join(map(str, author_ids))})
            GROUP BY sa.author
            """
            shouts_stats = {row[0]: row[1] for row in session.execute(text(shouts_stats_query))}

            # Запрос на получение статистики по подписчикам для авторов
            followers_stats_query = f"""
            SELECT author, COUNT(DISTINCT follower) as followers_count
            FROM author_follower
            WHERE author IN ({",".join(map(str, author_ids))})
            GROUP BY author
            """
            followers_stats = {row[0]: row[1] for row in session.execute(text(followers_stats_query))}

            # Формируем результат с добавлением статистики
            result = []
            for author in authors:
                author_dict = author.dict()
                author_dict["stat"] = {
                    "shouts": shouts_stats.get(author.id, 0),
                    "followers": followers_stats.get(author.id, 0),
                }
                result.append(author_dict)

                # Кешируем каждого автора отдельно для использования в других функциях
                await cache_author(author_dict)

            return result

    # Используем универсальную функцию для кеширования запросов
    return await cached_query(cache_key, fetch_authors_with_stats)


# Функция для инвалидации кеша авторов
async def invalidate_authors_cache(author_id=None):
    """
    Инвалидирует кеши авторов при изменении данных.

    Args:
        author_id: Опциональный ID автора для точечной инвалидации.
               Если не указан, инвалидируются все кеши авторов.
    """
    if author_id:
        # Точечная инвалидация конкретного автора
        logger.debug(f"Инвалидация кеша для автора #{author_id}")
        specific_keys = [
            f"author:id:{author_id}",
            f"author:followers:{author_id}",
            f"author:follows-authors:{author_id}",
            f"author:follows-topics:{author_id}",
            f"author:follows-shouts:{author_id}",
        ]

        # Получаем user_id автора, если есть
        with local_session() as session:
            author = session.query(Author).filter(Author.id == author_id).first()
            if author and author.user:
                specific_keys.append(f"author:user:{author.user.strip()}")

        # Удаляем конкретные ключи
        for key in specific_keys:
            try:
                await redis.execute("DEL", key)
                logger.debug(f"Удален ключ кеша {key}")
            except Exception as e:
                logger.error(f"Ошибка при удалении ключа {key}: {e}")

        # Также ищем и удаляем ключи коллекций, содержащих данные об этом авторе
        collection_keys = await redis.execute("KEYS", "authors:stats:*")
        if collection_keys:
            await redis.execute("DEL", *collection_keys)
            logger.debug(f"Удалено {len(collection_keys)} коллекционных ключей авторов")
    else:
        # Общая инвалидация всех кешей авторов
        logger.debug("Полная инвалидация кеша авторов")
        await invalidate_cache_by_prefix("authors")


@mutation.field("update_author")
@login_required
async def update_author(_, info, profile):
    user_id = info.context.get("user_id")
    if not user_id:
        return {"error": "unauthorized", "author": None}
    try:
        with local_session() as session:
            author = session.query(Author).where(Author.user == user_id).first()
            if author:
                Author.update(author, profile)
                session.add(author)
                session.commit()
                author_query = select(Author).where(Author.user == user_id)
                result = get_with_stat(author_query)
                if result:
                    author_with_stat = result[0]
                    if isinstance(author_with_stat, Author):
                        author_dict = author_with_stat.dict()
                        # await cache_author(author_dict)
                        asyncio.create_task(cache_author(author_dict))
                return {"error": None, "author": author}
    except Exception as exc:
        import traceback

        logger.error(traceback.format_exc())
        return {"error": exc, "author": None}


@query.field("get_authors_all")
async def get_authors_all(_, _info):
    """
    Получает список всех авторов без статистики.

    Returns:
        list: Список всех авторов
    """
    return await get_all_authors()


@query.field("get_author")
async def get_author(_, _info, slug="", author_id=0):
    author_dict = None
    try:
        author_id = get_author_id_from(slug=slug, user="", author_id=author_id)
        if not author_id:
            raise ValueError("cant find")
        author_dict = await get_cached_author(int(author_id), get_with_stat)

        if not author_dict or not author_dict.get("stat"):
            # update stat from db
            author_query = select(Author).filter(Author.id == author_id)
            result = get_with_stat(author_query)
            if result:
                author_with_stat = result[0]
                if isinstance(author_with_stat, Author):
                    author_dict = author_with_stat.dict()
                    # await cache_author(author_dict)
                    asyncio.create_task(cache_author(author_dict))
    except ValueError:
        pass
    except Exception as exc:
        import traceback

        logger.error(f"{exc}:\n{traceback.format_exc()}")
    return author_dict


@query.field("get_author_id")
async def get_author_id(_, _info, user: str):
    user_id = user.strip()
    logger.info(f"getting author id for {user_id}")
    author = None
    try:
        author = await get_cached_author_by_user_id(user_id, get_with_stat)
        if author:
            return author

        author_query = select(Author).filter(Author.user == user_id)
        result = get_with_stat(author_query)
        if result:
            author_with_stat = result[0]
            if isinstance(author_with_stat, Author):
                author_dict = author_with_stat.dict()
                # await cache_author(author_dict)
                asyncio.create_task(cache_author(author_dict))
                return author_with_stat
    except Exception as exc:
        logger.error(f"Error getting author: {exc}")
    return None


@query.field("load_authors_by")
async def load_authors_by(_, _info, by, limit, offset):
    """
    Загружает авторов по заданному критерию с пагинацией.

    Args:
        by: Критерий сортировки авторов (new/active)
        limit: Максимальное количество возвращаемых авторов
        offset: Смещение для пагинации

    Returns:
        list: Список авторов с учетом критерия
    """
    # Используем оптимизированную функцию для получения авторов
    return await get_authors_with_stats(limit, offset, by)


@query.field("load_authors_search")
async def load_authors_search_resolver(_, text: str, limit: int = 10, offset: int = 0):
    """Resolver for searching authors by text."""
    logger.info(f"Executing load_authors_search for text: '{text}', limit: {limit}, offset: {offset}")

    # Get author IDs from search engine (already sorted by relevance)
    search_results = await search_service.search_authors(text, limit, offset)

    if not search_results:
        logger.info(f"No authors found in search for '{text}'")
        return []

    author_ids = [result.get("id") for result in search_results if result.get("id")]
    if not author_ids:
        logger.warning(f"Search for '{text}' returned results but no valid IDs.")
        return []

    logger.info(f"Search returned {len(author_ids)} author IDs: {author_ids}")

    # Fetch full author objects from DB
    with local_session() as session:
        # Simple query to get authors by IDs - no need for stats here
        authors_query = select(Author).filter(Author.id.in_(author_ids))
        db_authors = session.execute(authors_query).scalars().all()
    
    if not db_authors:
        logger.warning(f"No authors found in DB for IDs: {author_ids}")
        return []

    # Create a dictionary for quick lookup
    authors_dict = {str(author.id): author for author in db_authors}
    
    # Keep the order from search results (maintains the relevance sorting)
    ordered_authors = [authors_dict[author_id] for author_id in author_ids if author_id in authors_dict]

    logger.info(f"Returning {len(ordered_authors)} authors matching search order.")
    return ordered_authors


def get_author_id_from(slug="", user=None, author_id=None):
    try:
        author_id = None
        if author_id:
            return author_id
        with local_session() as session:
            author = None
            if slug:
                author = session.query(Author).filter(Author.slug == slug).first()
                if author:
                    author_id = author.id
                    return author_id
            if user:
                author = session.query(Author).filter(Author.user == user).first()
                if author:
                    author_id = author.id
    except Exception as exc:
        logger.error(exc)
    return author_id


@query.field("get_author_follows")
async def get_author_follows(_, _info, slug="", user=None, author_id=0):
    logger.debug(f"getting follows for @{slug}")
    author_id = get_author_id_from(slug=slug, user=user, author_id=author_id)
    if not author_id:
        return {}

    followed_authors = await get_cached_follower_authors(author_id)
    followed_topics = await get_cached_follower_topics(author_id)

    # TODO: Get followed communities too
    return {
        "authors": followed_authors,
        "topics": followed_topics,
        "communities": DEFAULT_COMMUNITIES,
        "shouts": [],
    }


@query.field("get_author_follows_topics")
async def get_author_follows_topics(_, _info, slug="", user=None, author_id=None):
    logger.debug(f"getting followed topics for @{slug}")
    author_id = get_author_id_from(slug=slug, user=user, author_id=author_id)
    if not author_id:
        return []
    followed_topics = await get_cached_follower_topics(author_id)
    return followed_topics


@query.field("get_author_follows_authors")
async def get_author_follows_authors(_, _info, slug="", user=None, author_id=None):
    logger.debug(f"getting followed authors for @{slug}")
    author_id = get_author_id_from(slug=slug, user=user, author_id=author_id)
    if not author_id:
        return []
    followed_authors = await get_cached_follower_authors(author_id)
    return followed_authors


def create_author(user_id: str, slug: str, name: str = ""):
    author = Author()
    author.user = user_id  # Связь с user_id из системы авторизации
    author.slug = slug  # Идентификатор из системы авторизации
    author.created_at = author.updated_at = int(time.time())
    author.name = name or slug  # если не указано

    with local_session() as session:
        session.add(author)
        session.commit()
        return author


@query.field("get_author_followers")
async def get_author_followers(_, _info, slug: str = "", user: str = "", author_id: int = 0):
    logger.debug(f"getting followers for author @{slug} or ID:{author_id}")
    author_id = get_author_id_from(slug=slug, user=user, author_id=author_id)
    if not author_id:
        return []
    followers = await get_cached_author_followers(author_id)
    return followers
