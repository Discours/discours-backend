import asyncio
import time
from typing import Any, Optional, TypedDict

from graphql import GraphQLResolveInfo
from sqlalchemy import select, text

from auth.orm import Author
from cache.cache import (
    cache_author,
    cached_query,
    get_cached_author,
    get_cached_author_followers,
    get_cached_follower_authors,
    get_cached_follower_topics,
    invalidate_cache_by_prefix,
)
from resolvers.stat import get_with_stat
from services.auth import login_required
from services.common_result import CommonResult
from services.db import local_session
from services.redis import redis
from services.schema import mutation, query
from utils.logger import root_logger as logger

DEFAULT_COMMUNITIES = [1]


# Определение типа AuthorsBy на основе схемы GraphQL
class AuthorsBy(TypedDict, total=False):
    """
    Тип для параметра сортировки авторов, соответствующий схеме GraphQL.

    Поля:
        last_seen: Временная метка последнего посещения
        created_at: Временная метка создания
        slug: Уникальный идентификатор автора
        name: Имя автора
        topic: Тема, связанная с автором
        order: Поле для сортировки (shouts, followers, rating, comments, name)
        after: Временная метка для фильтрации "после"
        stat: Поле статистики
    """

    last_seen: Optional[int]
    created_at: Optional[int]
    slug: Optional[str]
    name: Optional[str]
    topic: Optional[str]
    order: Optional[str]
    after: Optional[int]
    stat: Optional[str]


# Вспомогательная функция для получения всех авторов без статистики
async def get_all_authors(current_user_id: Optional[int] = None) -> list[Any]:
    """
    Получает всех авторов без статистики.
    Используется для случаев, когда нужен полный список авторов без дополнительной информации.

    Args:
        current_user_id: ID текущего пользователя для проверки прав доступа
        is_admin: Флаг, указывающий, является ли пользователь администратором

    Returns:
        list: Список всех авторов без статистики
    """
    cache_key = "authors:all:basic"

    # Функция для получения всех авторов из БД
    async def fetch_all_authors() -> list[Any]:
        """
        Выполняет запрос к базе данных для получения всех авторов.
        """
        logger.debug("Получаем список всех авторов из БД и кешируем результат")

        with local_session() as session:
            # Запрос на получение базовой информации об авторах
            authors_query = select(Author).where(Author.deleted_at.is_(None))
            authors = session.execute(authors_query).scalars().unique().all()

            # Преобразуем авторов в словари с учетом прав доступа
            return [author.dict(False) for author in authors]

    # Используем универсальную функцию для кеширования запросов
    return await cached_query(cache_key, fetch_all_authors)


# Вспомогательная функция для получения авторов со статистикой с пагинацией
async def get_authors_with_stats(
    limit: int = 10, offset: int = 0, by: Optional[AuthorsBy] = None, current_user_id: Optional[int] = None
):
    """
    Получает авторов со статистикой с пагинацией.

    Args:
        limit: Максимальное количество возвращаемых авторов
        offset: Смещение для пагинации
        by: Опциональный параметр сортировки (AuthorsBy)
        current_user_id: ID текущего пользователя
    Returns:
        list: Список авторов с их статистикой
    """
    # Формируем ключ кеша с помощью универсальной функции
    order_value = by.get("order", "default") if by else "default"
    cache_key = f"authors:stats:limit={limit}:offset={offset}:order={order_value}"

    # Функция для получения авторов из БД
    async def fetch_authors_with_stats() -> list[Any]:
        """
        Выполняет запрос к базе данных для получения авторов со статистикой.
        """
        logger.debug(f"Выполняем запрос на получение авторов со статистикой: limit={limit}, offset={offset}, by={by}")

        # Импорты SQLAlchemy для избежания конфликтов имен
        from sqlalchemy import and_, asc, func
        from sqlalchemy import desc as sql_desc

        from auth.orm import AuthorFollower
        from orm.shout import Shout, ShoutAuthor

        with local_session() as session:
            # Базовый запрос для получения авторов
            base_query = select(Author).where(Author.deleted_at.is_(None))

            # vars for statistics sorting
            stats_sort_field = None
            default_sort_applied = False

            if by:
                if "order" in by:
                    order_value = by["order"]
                    logger.debug(f"Found order field with value: {order_value}")
                    if order_value in ["shouts", "followers", "rating", "comments"]:
                        stats_sort_field = order_value
                        logger.debug(f"Applying statistics-based sorting by: {stats_sort_field}")
                        # Не применяем другую сортировку, так как будем использовать stats_sort_field
                        default_sort_applied = True
                    elif order_value == "name":
                        # Sorting by name in ascending order
                        base_query = base_query.order_by(asc(Author.name))
                        logger.debug("Applying alphabetical sorting by name")
                        default_sort_applied = True
                    else:
                        # If order is not a stats field, treat it as a regular field
                        column = getattr(Author, order_value, None)
                        if column:
                            base_query = base_query.order_by(sql_desc(column))
                            logger.debug(f"Applying sorting by column: {order_value}")
                            default_sort_applied = True
                        else:
                            logger.warning(f"Unknown order field: {order_value}")
                else:
                    # Regular sorting by fields
                    for field, direction in by.items():
                        column = getattr(Author, field, None)
                        if column:
                            if direction.lower() == "desc":
                                base_query = base_query.order_by(sql_desc(column))
                            else:
                                base_query = base_query.order_by(column)
                            logger.debug(f"Applying sorting by field: {field}, direction: {direction}")
                            default_sort_applied = True
                        else:
                            logger.warning(f"Unknown field: {field}")

            # Если сортировка еще не применена, используем сортировку по умолчанию
            if not default_sort_applied and not stats_sort_field:
                base_query = base_query.order_by(sql_desc(Author.created_at))
                logger.debug("Applying default sorting by created_at (no by parameter)")

            # If sorting by statistics, modify the query
            if stats_sort_field == "shouts":
                # Sorting by the number of shouts
                logger.debug("Building subquery for shouts sorting")
                subquery = (
                    select(ShoutAuthor.author, func.count(func.distinct(Shout.id)).label("shouts_count"))
                    .select_from(ShoutAuthor)
                    .join(Shout, ShoutAuthor.shout == Shout.id)
                    .where(and_(Shout.deleted_at.is_(None), Shout.published_at.is_not(None)))
                    .group_by(ShoutAuthor.author)
                    .subquery()
                )

                # Сбрасываем предыдущую сортировку и применяем новую
                base_query = base_query.outerjoin(subquery, Author.id == subquery.c.author).order_by(
                    sql_desc(func.coalesce(subquery.c.shouts_count, 0))
                )
                logger.debug("Applied sorting by shouts count")

                # Логирование для отладки сортировки
                try:
                    # Получаем SQL запрос для проверки
                    sql_query = str(base_query.compile(compile_kwargs={"literal_binds": True}))
                    logger.debug(f"Generated SQL query for shouts sorting: {sql_query}")
                except Exception as e:
                    logger.error(f"Error generating SQL query: {e}")
            elif stats_sort_field == "followers":
                # Sorting by the number of followers
                logger.debug("Building subquery for followers sorting")
                subquery = (
                    select(
                        AuthorFollower.author,
                        func.count(func.distinct(AuthorFollower.follower)).label("followers_count"),
                    )
                    .select_from(AuthorFollower)
                    .group_by(AuthorFollower.author)
                    .subquery()
                )

                # Сбрасываем предыдущую сортировку и применяем новую
                base_query = base_query.outerjoin(subquery, Author.id == subquery.c.author).order_by(
                    sql_desc(func.coalesce(subquery.c.followers_count, 0))
                )
                logger.debug("Applied sorting by followers count")

                # Логирование для отладки сортировки
                try:
                    # Получаем SQL запрос для проверки
                    sql_query = str(base_query.compile(compile_kwargs={"literal_binds": True}))
                    logger.debug(f"Generated SQL query for followers sorting: {sql_query}")
                except Exception as e:
                    logger.error(f"Error generating SQL query: {e}")

            # Применяем лимит и смещение
            base_query = base_query.limit(limit).offset(offset)

            # Получаем авторов
            authors = session.execute(base_query).scalars().unique().all()
            author_ids = [author.id for author in authors]

            if not author_ids:
                return []

            # Логирование результатов для отладки сортировки
            if stats_sort_field:
                logger.debug(f"Query returned {len(authors)} authors with sorting by {stats_sort_field}")

            # Оптимизированный запрос для получения статистики по публикациям для авторов
            placeholders = ", ".join([f":id{i}" for i in range(len(author_ids))])
            shouts_stats_query = f"""
            SELECT sa.author, COUNT(DISTINCT s.id) as shouts_count
            FROM shout_author sa
            JOIN shout s ON sa.shout = s.id AND s.deleted_at IS NULL AND s.published_at IS NOT NULL
            WHERE sa.author IN ({placeholders})
            GROUP BY sa.author
            """
            params = {f"id{i}": author_id for i, author_id in enumerate(author_ids)}
            shouts_stats = {row[0]: row[1] for row in session.execute(text(shouts_stats_query), params)}

            # Запрос на получение статистики по подписчикам для авторов
            followers_stats_query = f"""
            SELECT author, COUNT(DISTINCT follower) as followers_count
            FROM author_follower
            WHERE author IN ({placeholders})
            GROUP BY author
            """
            followers_stats = {row[0]: row[1] for row in session.execute(text(followers_stats_query), params)}

            # Формируем результат с добавлением статистики
            result = []
            for author in authors:
                # Получаем словарь с учетом прав доступа
                author_dict = author.dict()
                author_dict["stat"] = {
                    "shouts": shouts_stats.get(author.id, 0),
                    "followers": followers_stats.get(author.id, 0),
                }

                result.append(author_dict)

                # Кешируем каждого автора отдельно для использования в других функциях
                # Важно: кэшируем полный словарь для админов
                await cache_author(author.dict())

            return result

    # Используем универсальную функцию для кеширования запросов
    return await cached_query(cache_key, fetch_authors_with_stats)


# Функция для инвалидации кеша авторов
async def invalidate_authors_cache(author_id=None) -> None:
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

        # Получаем author_id автора, если есть
        with local_session() as session:
            author = session.query(Author).filter(Author.id == author_id).first()
            if author and Author.id:
                specific_keys.append(f"author:id:{Author.id}")

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
async def update_author(_: None, info: GraphQLResolveInfo, profile: dict[str, Any]) -> CommonResult:
    """Update author profile"""
    author_id = info.context.get("author", {}).get("id")
    is_admin = info.context.get("is_admin", False)
    if not author_id:
        return CommonResult(error="unauthorized", author=None)
    try:
        with local_session() as session:
            author = session.query(Author).where(Author.id == author_id).first()
            if author:
                Author.update(author, profile)
                session.add(author)
                session.commit()
                author_query = select(Author).where(Author.id == author_id)
                result = get_with_stat(author_query)
                if result:
                    author_with_stat = result[0]
                    if isinstance(author_with_stat, Author):
                        # Кэшируем полную версию для админов
                        author_dict = author_with_stat.dict(is_admin)
                        _t = asyncio.create_task(cache_author(author_dict))

                        # Возвращаем обычную полную версию, т.к. это владелец
                        return CommonResult(error=None, author=author)
        # Если мы дошли до сюда, значит автор не найден
        return CommonResult(error="Author not found", author=None)
    except Exception as exc:
        import traceback

        logger.error(traceback.format_exc())
        return CommonResult(error=str(exc), author=None)


@query.field("get_authors_all")
async def get_authors_all(_: None, info: GraphQLResolveInfo) -> list[Any]:
    """Get all authors"""
    # Получаем ID текущего пользователя и флаг админа из контекста
    viewer_id = info.context.get("author", {}).get("id")
    info.context.get("is_admin", False)
    return await get_all_authors(viewer_id)


@query.field("get_author")
async def get_author(
    _: None, info: GraphQLResolveInfo, slug: Optional[str] = None, author_id: Optional[int] = None
) -> dict[str, Any] | None:
    """Get specific author by slug or ID"""
    # Получаем ID текущего пользователя и флаг админа из контекста
    is_admin = info.context.get("is_admin", False)

    author_dict = None
    try:
        author_id = get_author_id_from(slug=slug, user="", author_id=author_id)
        if not author_id:
            msg = "cant find"
            raise ValueError(msg)

        # Получаем данные автора из кэша (полные данные)
        cached_author = await get_cached_author(int(author_id), get_with_stat)

        # Применяем фильтрацию на стороне клиента, так как в кэше хранится полная версия
        if cached_author:
            # Создаем объект автора для использования метода dict
            temp_author = Author()
            for key, value in cached_author.items():
                if hasattr(temp_author, key):
                    setattr(temp_author, key, value)
            # Получаем отфильтрованную версию
            author_dict = temp_author.dict(is_admin)
            # Добавляем статистику, которая могла быть в кэшированной версии
            if "stat" in cached_author:
                author_dict["stat"] = cached_author["stat"]

        if not author_dict or not author_dict.get("stat"):
            # update stat from db
            author_query = select(Author).filter(Author.id == author_id)
            result = get_with_stat(author_query)
            if result:
                author_with_stat = result[0]
                if isinstance(author_with_stat, Author):
                    # Кэшируем полные данные для админов
                    original_dict = author_with_stat.dict(True)
                    _t = asyncio.create_task(cache_author(original_dict))

                    # Возвращаем отфильтрованную версию
                    author_dict = author_with_stat.dict(is_admin)
                    # Добавляем статистику
                    if hasattr(author_with_stat, "stat"):
                        author_dict["stat"] = author_with_stat.stat
    except ValueError:
        pass
    except Exception as exc:
        import traceback

        logger.error(f"{exc}:\n{traceback.format_exc()}")
    return author_dict


@query.field("load_authors_by")
async def load_authors_by(
    _: None, info: GraphQLResolveInfo, by: AuthorsBy, limit: int = 10, offset: int = 0
) -> list[Any]:
    """Load authors by different criteria"""
    try:
        # Получаем ID текущего пользователя и флаг админа из контекста
        viewer_id = info.context.get("author", {}).get("id")
        info.context.get("is_admin", False)

        # Логирование для отладки
        logger.debug(f"load_authors_by called with by={by}, limit={limit}, offset={offset}")

        # Проверяем наличие параметра order в словаре
        if "order" in by:
            logger.debug(f"Sorting by order={by['order']}")

        # Используем оптимизированную функцию для получения авторов
        return await get_authors_with_stats(limit, offset, by, viewer_id)
    except Exception as exc:
        import traceback

        logger.error(f"{exc}:\n{traceback.format_exc()}")
        return []


@query.field("load_authors_search")
async def load_authors_search(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> list[Any]:
    """Search for authors"""
    # TODO: Implement search functionality
    return []


def get_author_id_from(
    slug: Optional[str] = None, user: Optional[str] = None, author_id: Optional[int] = None
) -> Optional[int]:
    """Get author ID from different identifiers"""
    try:
        if author_id:
            return author_id
        with local_session() as session:
            author = None
            if slug:
                author = session.query(Author).filter(Author.slug == slug).first()
                if author:
                    return int(author.id)
            if user:
                author = session.query(Author).filter(Author.id == user).first()
                if author:
                    return int(author.id)
    except Exception as exc:
        logger.error(exc)
    return None


@query.field("get_author_follows")
async def get_author_follows(
    _, info: GraphQLResolveInfo, slug: Optional[str] = None, user: Optional[str] = None, author_id: Optional[int] = None
) -> dict[str, Any]:
    """Get entities followed by author"""
    # Получаем ID текущего пользователя и флаг админа из контекста
    viewer_id = info.context.get("author", {}).get("id")
    is_admin = info.context.get("is_admin", False)

    logger.debug(f"getting follows for @{slug}")
    author_id = get_author_id_from(slug=slug, user=user, author_id=author_id)
    if not author_id:
        return {"error": "Author not found"}

    # Получаем данные из кэша
    followed_authors_raw = await get_cached_follower_authors(author_id)
    followed_topics = await get_cached_follower_topics(author_id)

    # Фильтруем чувствительные данные авторов
    followed_authors = []
    for author_data in followed_authors_raw:
        # Создаем объект автора для использования метода dict
        temp_author = Author()
        for key, value in author_data.items():
            if hasattr(temp_author, key):
                setattr(temp_author, key, value)
        # Добавляем отфильтрованную версию
        # temp_author - это объект Author, который мы хотим сериализовать
        # current_user_id - ID текущего авторизованного пользователя (может быть None)
        # is_admin - булево значение, является ли текущий пользователь админом
        has_access = is_admin or (viewer_id is not None and str(viewer_id) == str(temp_author.id))
        followed_authors.append(temp_author.dict(has_access))

    # TODO: Get followed communities too
    return {
        "authors": followed_authors,
        "topics": followed_topics,
        "communities": DEFAULT_COMMUNITIES,
        "shouts": [],
        "error": None,
    }


@query.field("get_author_follows_topics")
async def get_author_follows_topics(
    _,
    _info: GraphQLResolveInfo,
    slug: Optional[str] = None,
    user: Optional[str] = None,
    author_id: Optional[int] = None,
) -> list[Any]:
    """Get topics followed by author"""
    logger.debug(f"getting followed topics for @{slug}")
    author_id = get_author_id_from(slug=slug, user=user, author_id=author_id)
    if not author_id:
        return []
    result = await get_cached_follower_topics(author_id)
    # Ensure we return a list, not a dict
    if isinstance(result, dict):
        return result.get("topics", [])
    return result if isinstance(result, list) else []


@query.field("get_author_follows_authors")
async def get_author_follows_authors(
    _, info: GraphQLResolveInfo, slug: Optional[str] = None, user: Optional[str] = None, author_id: Optional[int] = None
) -> list[Any]:
    """Get authors followed by author"""
    # Получаем ID текущего пользователя и флаг админа из контекста
    viewer_id = info.context.get("author", {}).get("id")
    is_admin = info.context.get("is_admin", False)

    logger.debug(f"getting followed authors for @{slug}")
    author_id = get_author_id_from(slug=slug, user=user, author_id=author_id)
    if not author_id:
        return []

    # Получаем данные из кэша
    followed_authors_raw = await get_cached_follower_authors(author_id)

    # Фильтруем чувствительные данные авторов
    followed_authors = []
    for author_data in followed_authors_raw:
        # Создаем объект автора для использования метода dict
        temp_author = Author()
        for key, value in author_data.items():
            if hasattr(temp_author, key):
                setattr(temp_author, key, value)
        # Добавляем отфильтрованную версию
        # temp_author - это объект Author, который мы хотим сериализовать
        # current_user_id - ID текущего авторизованного пользователя (может быть None)
        # is_admin - булево значение, является ли текущий пользователь админом
        has_access = is_admin or (viewer_id is not None and str(viewer_id) == str(temp_author.id))
        followed_authors.append(temp_author.dict(has_access))

    return followed_authors


def create_author(**kwargs) -> Author:
    """Create new author"""
    author = Author()
    # Use setattr to avoid MyPy complaints about Column assignment
    author.id = kwargs.get("user_id")  # type: ignore[assignment] # Связь с user_id из системы авторизации  # type: ignore[assignment]
    author.slug = kwargs.get("slug")  # type: ignore[assignment] # Идентификатор из системы авторизации  # type: ignore[assignment]
    author.created_at = int(time.time())  # type: ignore[assignment]
    author.updated_at = int(time.time())  # type: ignore[assignment]
    author.name = kwargs.get("name") or kwargs.get("slug")  # type: ignore[assignment] # если не указано  # type: ignore[assignment]

    with local_session() as session:
        session.add(author)
        session.commit()
        return author


@query.field("get_author_followers")
async def get_author_followers(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> list[Any]:
    """Get followers of an author"""
    # Получаем ID текущего пользователя и флаг админа из контекста
    viewer_id = info.context.get("author", {}).get("id")
    is_admin = info.context.get("is_admin", False)

    logger.debug(f"getting followers for author @{kwargs.get('slug')} or ID:{kwargs.get('author_id')}")
    author_id = get_author_id_from(slug=kwargs.get("slug"), user=kwargs.get("user"), author_id=kwargs.get("author_id"))
    if not author_id:
        return []

    # Получаем данные из кэша
    followers_raw = await get_cached_author_followers(author_id)

    # Фильтруем чувствительные данные авторов
    followers = []
    for follower_data in followers_raw:
        # Создаем объект автора для использования метода dict
        temp_author = Author()
        for key, value in follower_data.items():
            if hasattr(temp_author, key):
                setattr(temp_author, key, value)
        # Добавляем отфильтрованную версию
        # temp_author - это объект Author, который мы хотим сериализовать
        # current_user_id - ID текущего авторизованного пользователя (может быть None)
        # is_admin - булево значение, является ли текущий пользователь админом
        has_access = is_admin or (viewer_id is not None and str(viewer_id) == str(temp_author.id))
        followers.append(temp_author.dict(has_access))

    return followers
