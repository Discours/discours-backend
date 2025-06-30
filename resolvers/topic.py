from typing import Any, Optional

from graphql import GraphQLResolveInfo
from sqlalchemy import desc, func, select, text

from auth.orm import Author
from cache.cache import (
    cache_topic,
    cached_query,
    get_cached_topic_authors,
    get_cached_topic_by_slug,
    get_cached_topic_followers,
    invalidate_cache_by_prefix,
    invalidate_topic_followers_cache,
)
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic, TopicFollower
from resolvers.stat import get_with_stat
from services.auth import login_required
from services.db import local_session
from services.redis import redis
from services.schema import mutation, query
from utils.logger import root_logger as logger


# Вспомогательная функция для получения всех тем без статистики
async def get_all_topics() -> list[Any]:
    """
    Получает все темы без статистики.
    Используется для случаев, когда нужен полный список тем без дополнительной информации.

    Returns:
        list: Список всех тем без статистики
    """
    cache_key = "topics:all:basic"

    # Функция для получения всех тем из БД
    async def fetch_all_topics() -> list[dict]:
        logger.debug("Получаем список всех тем из БД и кешируем результат")

        with local_session() as session:
            # Запрос на получение базовой информации о темах
            topics_query = select(Topic)
            topics = session.execute(topics_query).scalars().unique().all()

            # Преобразуем темы в словари
            return [topic.dict() for topic in topics]

    # Используем универсальную функцию для кеширования запросов
    return await cached_query(cache_key, fetch_all_topics)


# Вспомогательная функция для получения тем со статистикой с пагинацией
async def get_topics_with_stats(
    limit: int = 100, offset: int = 0, community_id: Optional[int] = None, by: Optional[str] = None
) -> dict[str, Any]:
    """
    Получает темы со статистикой с пагинацией.

    Args:
        limit: Максимальное количество возвращаемых тем
        offset: Смещение для пагинации
        community_id: Опциональный ID сообщества для фильтрации
        by: Опциональный параметр сортировки ('popular', 'authors', 'followers', 'comments')
            - 'popular' - по количеству публикаций (по умолчанию)
            - 'authors' - по количеству авторов
            - 'followers' - по количеству подписчиков
            - 'comments' - по количеству комментариев

    Returns:
        list: Список тем с их статистикой, отсортированный по популярности
    """
    # Формируем ключ кеша с помощью универсальной функции
    cache_key = f"topics:stats:limit={limit}:offset={offset}:community_id={community_id}:by={by}"

    # Функция для получения тем из БД
    async def fetch_topics_with_stats() -> list[dict]:
        logger.debug(f"Выполняем запрос на получение тем со статистикой: limit={limit}, offset={offset}, by={by}")

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
                    # Сортировка по популярности - по количеству публикаций
                    shouts_subquery = (
                        select(ShoutTopic.topic, func.count(ShoutTopic.shout).label("shouts_count"))
                        .join(Shout, ShoutTopic.shout == Shout.id)
                        .where(Shout.deleted_at.is_(None), Shout.published_at.isnot(None))
                        .group_by(ShoutTopic.topic)
                        .subquery()
                    )

                    base_query = base_query.outerjoin(shouts_subquery, Topic.id == shouts_subquery.c.topic).order_by(
                        desc(func.coalesce(shouts_subquery.c.shouts_count, 0))
                    )
                elif by == "authors":
                    # Сортировка по количеству авторов
                    authors_subquery = (
                        select(ShoutTopic.topic, func.count(func.distinct(ShoutAuthor.author)).label("authors_count"))
                        .join(Shout, ShoutTopic.shout == Shout.id)
                        .join(ShoutAuthor, ShoutAuthor.shout == Shout.id)
                        .where(Shout.deleted_at.is_(None), Shout.published_at.isnot(None))
                        .group_by(ShoutTopic.topic)
                        .subquery()
                    )

                    base_query = base_query.outerjoin(authors_subquery, Topic.id == authors_subquery.c.topic).order_by(
                        desc(func.coalesce(authors_subquery.c.authors_count, 0))
                    )
                elif by == "followers":
                    # Сортировка по количеству подписчиков
                    followers_subquery = (
                        select(TopicFollower.topic, func.count(TopicFollower.follower).label("followers_count"))
                        .group_by(TopicFollower.topic)
                        .subquery()
                    )

                    base_query = base_query.outerjoin(
                        followers_subquery, Topic.id == followers_subquery.c.topic
                    ).order_by(desc(func.coalesce(followers_subquery.c.followers_count, 0)))
                elif by == "comments":
                    # Сортировка по количеству комментариев
                    comments_subquery = (
                        select(ShoutTopic.topic, func.count(func.distinct(Reaction.id)).label("comments_count"))
                        .join(Shout, ShoutTopic.shout == Shout.id)
                        .join(Reaction, Reaction.shout == Shout.id)
                        .where(
                            Shout.deleted_at.is_(None),
                            Shout.published_at.isnot(None),
                            Reaction.kind == ReactionKind.COMMENT.value,
                            Reaction.deleted_at.is_(None),
                        )
                        .group_by(ShoutTopic.topic)
                        .subquery()
                    )

                    base_query = base_query.outerjoin(
                        comments_subquery, Topic.id == comments_subquery.c.topic
                    ).order_by(desc(func.coalesce(comments_subquery.c.comments_count, 0)))
                else:
                    # Неизвестный параметр сортировки - используем дефолтную (по популярности)
                    shouts_subquery = (
                        select(ShoutTopic.topic, func.count(ShoutTopic.shout).label("shouts_count"))
                        .join(Shout, ShoutTopic.shout == Shout.id)
                        .where(Shout.deleted_at.is_(None), Shout.published_at.isnot(None))
                        .group_by(ShoutTopic.topic)
                        .subquery()
                    )

                    base_query = base_query.outerjoin(shouts_subquery, Topic.id == shouts_subquery.c.topic).order_by(
                        desc(func.coalesce(shouts_subquery.c.shouts_count, 0))
                    )
            else:
                # По умолчанию сортируем по популярности (количество публикаций)
                # Это более логично для списка топиков сообщества
                shouts_subquery = (
                    select(ShoutTopic.topic, func.count(ShoutTopic.shout).label("shouts_count"))
                    .join(Shout, ShoutTopic.shout == Shout.id)
                    .where(Shout.deleted_at.is_(None), Shout.published_at.isnot(None))
                    .group_by(ShoutTopic.topic)
                    .subquery()
                )

                base_query = base_query.outerjoin(shouts_subquery, Topic.id == shouts_subquery.c.topic).order_by(
                    desc(func.coalesce(shouts_subquery.c.shouts_count, 0))
                )

            # Применяем лимит и смещение
            base_query = base_query.limit(limit).offset(offset)

            # Получаем темы
            topics = session.execute(base_query).scalars().unique().all()
            topic_ids = [topic.id for topic in topics]

            if not topic_ids:
                return []

            # Исправляю S608 - используем параметризированные запросы
            if topic_ids:
                placeholders = ",".join([f":id{i}" for i in range(len(topic_ids))])

                # Запрос на получение статистики по публикациям для выбранных тем
                shouts_stats_query = f"""
                SELECT st.topic, COUNT(DISTINCT s.id) as shouts_count
                FROM shout_topic st
                JOIN shout s ON st.shout = s.id AND s.deleted_at IS NULL AND s.published_at IS NOT NULL
                WHERE st.topic IN ({placeholders})
                GROUP BY st.topic
                """
                params = {f"id{i}": topic_id for i, topic_id in enumerate(topic_ids)}
                shouts_stats = {row[0]: row[1] for row in session.execute(text(shouts_stats_query), params)}

                # Запрос на получение статистики по подписчикам для выбранных тем
                followers_stats_query = f"""
                SELECT topic, COUNT(DISTINCT follower) as followers_count
                FROM topic_followers tf
                WHERE topic IN ({placeholders})
                GROUP BY topic
                """
                followers_stats = {row[0]: row[1] for row in session.execute(text(followers_stats_query), params)}

                # Запрос на получение статистики авторов для выбранных тем
                authors_stats_query = f"""
                SELECT st.topic, COUNT(DISTINCT sa.author) as authors_count
                FROM shout_topic st
                JOIN shout s ON st.shout = s.id AND s.deleted_at IS NULL AND s.published_at IS NOT NULL
                JOIN shout_author sa ON sa.shout = s.id
                WHERE st.topic IN ({placeholders})
                GROUP BY st.topic
                """
                authors_stats = {row[0]: row[1] for row in session.execute(text(authors_stats_query), params)}

                # Запрос на получение статистики комментариев для выбранных тем
                comments_stats_query = f"""
                SELECT st.topic, COUNT(DISTINCT r.id) as comments_count
                FROM shout_topic st
                JOIN shout s ON st.shout = s.id AND s.deleted_at IS NULL AND s.published_at IS NOT NULL
                JOIN reaction r ON r.shout = s.id AND r.kind = :comment_kind AND r.deleted_at IS NULL
                JOIN author a ON r.created_by = a.id
                WHERE st.topic IN ({placeholders})
                GROUP BY st.topic
                """
                params["comment_kind"] = ReactionKind.COMMENT.value
                comments_stats = {row[0]: row[1] for row in session.execute(text(comments_stats_query), params)}

            # Формируем результат с добавлением статистики
            result = []
            for topic in topics:
                topic_dict = topic.dict()
                topic_dict["stat"] = {
                    "shouts": shouts_stats.get(topic.id, 0),
                    "followers": followers_stats.get(topic.id, 0),
                    "authors": authors_stats.get(topic.id, 0),
                    "comments": comments_stats.get(topic.id, 0),
                }
                result.append(topic_dict)

                # Кешируем каждую тему отдельно для использования в других функциях
                await cache_topic(topic_dict)

            return result

    # Используем универсальную функцию для кеширования запросов
    return await cached_query(cache_key, fetch_topics_with_stats)


# Функция для инвалидации кеша тем
async def invalidate_topics_cache(topic_id: Optional[int] = None) -> None:
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
async def get_topics_all(_: None, _info: GraphQLResolveInfo) -> list[Any]:
    """
    Получает список всех тем без статистики.

    Returns:
        list: Список всех тем
    """
    return await get_all_topics()


# Запрос на получение тем по сообществу
@query.field("get_topics_by_community")
async def get_topics_by_community(
    _: None, _info: GraphQLResolveInfo, community_id: int, limit: int = 100, offset: int = 0, by: Optional[str] = None
) -> list[Any]:
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
    result = await get_topics_with_stats(limit, offset, community_id, by)
    return result.get("topics", []) if isinstance(result, dict) else result


# Запрос на получение тем по автору
@query.field("get_topics_by_author")
async def get_topics_by_author(
    _: None, _info: GraphQLResolveInfo, author_id: int = 0, slug: str = "", user: str = ""
) -> list[Any]:
    topics_by_author_query = select(Topic)
    if author_id:
        topics_by_author_query = topics_by_author_query.join(Author).where(Author.id == author_id)
    elif slug:
        topics_by_author_query = topics_by_author_query.join(Author).where(Author.slug == slug)
    elif user:
        topics_by_author_query = topics_by_author_query.join(Author).where(Author.id == user)

    return get_with_stat(topics_by_author_query)


# Запрос на получение одной темы по её slug
@query.field("get_topic")
async def get_topic(_: None, _info: GraphQLResolveInfo, slug: str) -> Optional[Any]:
    topic = await get_cached_topic_by_slug(slug, get_with_stat)
    if topic:
        return topic
    return None


# Мутация для создания новой темы
@mutation.field("create_topic")
@login_required
async def create_topic(_: None, _info: GraphQLResolveInfo, topic_input: dict[str, Any]) -> dict[str, Any]:
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
async def update_topic(_: None, _info: GraphQLResolveInfo, topic_input: dict[str, Any]) -> dict[str, Any]:
    slug = topic_input["slug"]
    with local_session() as session:
        topic = session.query(Topic).filter(Topic.slug == slug).first()
        if not topic:
            return {"error": "topic not found"}
        old_slug = str(getattr(topic, "slug", ""))
        Topic.update(topic, topic_input)
        session.add(topic)
        session.commit()

        # Инвалидируем кеш только для этой конкретной темы
        await invalidate_topics_cache(int(getattr(topic, "id", 0)))

        # Если slug изменился, удаляем старый ключ
        if old_slug != str(getattr(topic, "slug", "")):
            await redis.execute("DEL", f"topic:slug:{old_slug}")
            logger.debug(f"Удален ключ кеша для старого slug: {old_slug}")

        return {"topic": topic}


# Мутация для удаления темы
@mutation.field("delete_topic")
@login_required
async def delete_topic(_: None, info: GraphQLResolveInfo, slug: str) -> dict[str, Any]:
    viewer_id = info.context.get("author", {}).get("id")
    with local_session() as session:
        topic = session.query(Topic).filter(Topic.slug == slug).first()
        if not topic:
            return {"error": "invalid topic slug"}
        author = session.query(Author).filter(Author.id == viewer_id).first()
        if author:
            if getattr(topic, "created_by", None) != author.id:
                return {"error": "access denied"}

            session.delete(topic)
            session.commit()

            # Инвалидируем кеш всех тем и конкретной темы
            await invalidate_topics_cache()
            await redis.execute("DEL", f"topic:slug:{slug}")
            await redis.execute("DEL", f"topic:id:{getattr(topic, 'id', 0)}")

            return {}
    return {"error": "access denied"}


# Запрос на получение подписчиков темы
@query.field("get_topic_followers")
async def get_topic_followers(_: None, _info: GraphQLResolveInfo, slug: str) -> list[Any]:
    logger.debug(f"getting followers for @{slug}")
    topic = await get_cached_topic_by_slug(slug, get_with_stat)
    topic_id = getattr(topic, "id", None) if isinstance(topic, Topic) else topic.get("id") if topic else None
    return await get_cached_topic_followers(topic_id) if topic_id else []


# Запрос на получение авторов темы
@query.field("get_topic_authors")
async def get_topic_authors(_: None, _info: GraphQLResolveInfo, slug: str) -> list[Any]:
    logger.debug(f"getting authors for @{slug}")
    topic = await get_cached_topic_by_slug(slug, get_with_stat)
    topic_id = getattr(topic, "id", None) if isinstance(topic, Topic) else topic.get("id") if topic else None
    return await get_cached_topic_authors(topic_id) if topic_id else []


# Мутация для удаления темы по ID (для админ-панели)
@mutation.field("delete_topic_by_id")
@login_required
async def delete_topic_by_id(_: None, info: GraphQLResolveInfo, topic_id: int) -> dict[str, Any]:
    """
    Удаляет тему по ID. Используется в админ-панели.

    Args:
        topic_id: ID темы для удаления

    Returns:
        dict: Результат операции
    """
    viewer_id = info.context.get("author", {}).get("id")
    with local_session() as session:
        topic = session.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return {"success": False, "message": "Топик не найден"}

        author = session.query(Author).filter(Author.id == viewer_id).first()
        if not author:
            return {"success": False, "message": "Не авторизован"}

        # TODO: проверить права администратора
        # Для админ-панели допускаем удаление любых топиков администратором

        try:
            # Инвалидируем кеши подписчиков ПЕРЕД удалением данных из БД
            await invalidate_topic_followers_cache(topic_id)

            # Удаляем связанные данные (подписчики, связи с публикациями)
            session.query(TopicFollower).filter(TopicFollower.topic == topic_id).delete()
            session.query(ShoutTopic).filter(ShoutTopic.topic == topic_id).delete()

            # Удаляем сам топик
            session.delete(topic)
            session.commit()

            # Инвалидируем основные кеши топика
            await invalidate_topics_cache(topic_id)
            if topic.slug:
                await redis.execute("DEL", f"topic:slug:{topic.slug}")

            logger.info(f"Топик {topic_id} успешно удален")
            return {"success": True, "message": "Топик успешно удален"}

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при удалении топика {topic_id}: {e}")
            return {"success": False, "message": f"Ошибка при удалении: {e!s}"}


# Мутация для слияния тем
@mutation.field("merge_topics")
@login_required
async def merge_topics(_: None, info: GraphQLResolveInfo, merge_input: dict[str, Any]) -> dict[str, Any]:
    """
    Сливает несколько тем в одну с переносом всех связей.

    Args:
        merge_input: Данные для слияния:
            - target_topic_id: ID целевой темы (в которую сливаем)
            - source_topic_ids: Список ID исходных тем (которые сливаем)
            - preserve_target_properties: Сохранить свойства целевой темы

    Returns:
        dict: Результат операции с информацией о слиянии

    Функциональность:
        - Переносит всех подписчиков из исходных тем в целевую
        - Переносит все публикации из исходных тем в целевую
        - Обновляет связи с черновиками
        - Проверяет принадлежность тем к одному сообществу
        - Удаляет исходные темы после переноса
        - Инвалидирует соответствующие кеши
    """
    viewer_id = info.context.get("author", {}).get("id")
    target_topic_id = merge_input["target_topic_id"]
    source_topic_ids = merge_input["source_topic_ids"]
    preserve_target = merge_input.get("preserve_target_properties", True)

    # Проверяем права доступа
    if not viewer_id:
        return {"error": "Не авторизован"}

    # Проверяем что ID не пересекаются
    if target_topic_id in source_topic_ids:
        return {"error": "Целевая тема не может быть в списке исходных тем"}

    with local_session() as session:
        try:
            # Получаем целевую тему
            target_topic = session.query(Topic).filter(Topic.id == target_topic_id).first()
            if not target_topic:
                return {"error": f"Целевая тема с ID {target_topic_id} не найдена"}

            # Получаем исходные темы
            source_topics = session.query(Topic).filter(Topic.id.in_(source_topic_ids)).all()
            if len(source_topics) != len(source_topic_ids):
                found_ids = [t.id for t in source_topics]
                missing_ids = [topic_id for topic_id in source_topic_ids if topic_id not in found_ids]
                return {"error": f"Исходные темы с ID {missing_ids} не найдены"}

            # Проверяем что все темы принадлежат одному сообществу
            target_community = target_topic.community
            for source_topic in source_topics:
                if source_topic.community != target_community:
                    return {"error": f"Тема '{source_topic.title}' принадлежит другому сообществу"}

            # Получаем автора для проверки прав
            author = session.query(Author).filter(Author.id == viewer_id).first()
            if not author:
                return {"error": "Автор не найден"}

            # TODO: проверить права администратора или создателя тем
            # Для админ-панели допускаем слияние любых тем администратором

            # Собираем статистику для отчета
            merge_stats = {"followers_moved": 0, "publications_moved": 0, "drafts_moved": 0, "source_topics_deleted": 0}

            # Переносим подписчиков из исходных тем в целевую
            for source_topic in source_topics:
                # Получаем подписчиков исходной темы
                source_followers = session.query(TopicFollower).filter(TopicFollower.topic == source_topic.id).all()

                for follower in source_followers:
                    # Проверяем, не подписан ли уже пользователь на целевую тему
                    existing = (
                        session.query(TopicFollower)
                        .filter(TopicFollower.topic == target_topic_id, TopicFollower.follower == follower.follower)
                        .first()
                    )

                    if not existing:
                        # Создаем новую подписку на целевую тему
                        new_follower = TopicFollower(
                            topic=target_topic_id,
                            follower=follower.follower,
                            created_at=follower.created_at,
                            auto=follower.auto,
                        )
                        session.add(new_follower)
                        merge_stats["followers_moved"] += 1

                    # Удаляем старую подписку
                    session.delete(follower)

            # Переносим публикации из исходных тем в целевую
            from orm.shout import ShoutTopic

            for source_topic in source_topics:
                # Получаем связи публикаций с исходной темой
                shout_topics = session.query(ShoutTopic).filter(ShoutTopic.topic == source_topic.id).all()

                for shout_topic in shout_topics:
                    # Проверяем, не связана ли уже публикация с целевой темой
                    existing = (
                        session.query(ShoutTopic)
                        .filter(ShoutTopic.topic == target_topic_id, ShoutTopic.shout == shout_topic.shout)
                        .first()
                    )

                    if not existing:
                        # Создаем новую связь с целевой темой
                        new_shout_topic = ShoutTopic(
                            topic=target_topic_id, shout=shout_topic.shout, main=shout_topic.main
                        )
                        session.add(new_shout_topic)
                        merge_stats["publications_moved"] += 1

                    # Удаляем старую связь
                    session.delete(shout_topic)

            # Переносим черновики из исходных тем в целевую
            from orm.draft import DraftTopic

            for source_topic in source_topics:
                # Получаем связи черновиков с исходной темой
                draft_topics = session.query(DraftTopic).filter(DraftTopic.topic == source_topic.id).all()

                for draft_topic in draft_topics:
                    # Проверяем, не связан ли уже черновик с целевой темой
                    existing = (
                        session.query(DraftTopic)
                        .filter(DraftTopic.topic == target_topic_id, DraftTopic.shout == draft_topic.shout)
                        .first()
                    )

                    if not existing:
                        # Создаем новую связь с целевой темой
                        new_draft_topic = DraftTopic(
                            topic=target_topic_id, shout=draft_topic.shout, main=draft_topic.main
                        )
                        session.add(new_draft_topic)
                        merge_stats["drafts_moved"] += 1

                    # Удаляем старую связь
                    session.delete(draft_topic)

            # Объединяем parent_ids если не сохраняем только целевые свойства
            if not preserve_target:
                current_parent_ids: list[int] = list(target_topic.parent_ids or [])
                all_parent_ids = set(current_parent_ids)
                for source_topic in source_topics:
                    source_parent_ids: list[int] = list(source_topic.parent_ids or [])
                    if source_parent_ids:
                        all_parent_ids.update(source_parent_ids)
                # Убираем IDs исходных тем из parent_ids
                all_parent_ids.discard(target_topic_id)
                for source_id in source_topic_ids:
                    all_parent_ids.discard(source_id)
                target_topic.parent_ids = list(all_parent_ids) if all_parent_ids else []  # type: ignore[assignment]

            # Инвалидируем кеши ПЕРЕД удалением тем
            for source_topic in source_topics:
                await invalidate_topic_followers_cache(int(source_topic.id))
                if source_topic.slug:
                    await redis.execute("DEL", f"topic:slug:{source_topic.slug}")
                await redis.execute("DEL", f"topic:id:{source_topic.id}")

            # Удаляем исходные темы
            for source_topic in source_topics:
                session.delete(source_topic)
                merge_stats["source_topics_deleted"] += 1
                logger.info(f"Удалена исходная тема: {source_topic.title} (ID: {source_topic.id})")

            # Сохраняем изменения
            session.commit()

            # Инвалидируем кеши целевой темы и общие кеши
            await invalidate_topics_cache(target_topic_id)
            await invalidate_topic_followers_cache(target_topic_id)

            logger.info(f"Успешно слиты темы {source_topic_ids} в тему {target_topic_id}")
            logger.info(f"Статистика слияния: {merge_stats}")

            return {
                "topic": target_topic,
                "message": f"Успешно слито {len(source_topics)} тем в '{target_topic.title}'",
                "stats": merge_stats,
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при слиянии тем: {e}")
            return {"error": f"Ошибка при слиянии тем: {e!s}"}


# Мутация для простого назначения родителя темы
@mutation.field("set_topic_parent")
@login_required
async def set_topic_parent(
    _: None, info: GraphQLResolveInfo, topic_id: int, parent_id: int | None = None
) -> dict[str, Any]:
    """
    Простое назначение родительской темы для указанной темы.

    Args:
        topic_id: ID темы, которой назначаем родителя
        parent_id: ID родительской темы (None для корневой темы)

    Returns:
        dict: Результат операции

    Функциональность:
        - Устанавливает parent_ids для темы
        - Проверяет циклические зависимости
        - Проверяет принадлежность к одному сообществу
        - Инвалидирует кеши
    """
    viewer_id = info.context.get("author", {}).get("id")

    # Проверяем права доступа
    if not viewer_id:
        return {"error": "Не авторизован"}

    with local_session() as session:
        try:
            # Получаем тему
            topic = session.query(Topic).filter(Topic.id == topic_id).first()
            if not topic:
                return {"error": f"Тема с ID {topic_id} не найдена"}

            # Если устанавливаем корневую тему
            if parent_id is None:
                old_parent_ids: list[int] = list(topic.parent_ids or [])
                topic.parent_ids = []  # type: ignore[assignment]
                session.commit()

                # Инвалидируем кеши
                await invalidate_topics_cache(topic_id)

                return {
                    "topic": topic,
                    "message": f"Тема '{topic.title}' установлена как корневая",
                }

            # Получаем родительскую тему
            parent_topic = session.query(Topic).filter(Topic.id == parent_id).first()
            if not parent_topic:
                return {"error": f"Родительская тема с ID {parent_id} не найдена"}

            # Проверяем принадлежность к одному сообществу
            if topic.community != parent_topic.community:
                return {"error": "Тема и родительская тема должны принадлежать одному сообществу"}

            # Проверяем циклические зависимости
            def is_descendant(potential_parent: Topic, child_id: int) -> bool:
                """Проверяет, является ли тема потомком другой темы"""
                if potential_parent.id == child_id:
                    return True

                # Ищем всех потомков parent'а
                descendants = session.query(Topic).filter(Topic.parent_ids.op("@>")([potential_parent.id])).all()

                for descendant in descendants:
                    if descendant.id == child_id or is_descendant(descendant, child_id):
                        return True

                return False

            if is_descendant(topic, parent_id):
                return {"error": "Нельзя установить потомка как родителя (циклическая зависимость)"}

            # Устанавливаем новые parent_ids
            parent_parent_ids: list[int] = list(parent_topic.parent_ids or [])
            new_parent_ids = [*parent_parent_ids, parent_id]

            topic.parent_ids = new_parent_ids  # type: ignore[assignment]
            session.commit()

            # Инвалидируем кеши
            await invalidate_topics_cache(topic_id)
            await invalidate_topics_cache(parent_id)

            logger.info(f"Установлен родитель для темы {topic_id}: {parent_id}")

            return {
                "topic": topic,
                "message": f"Тема '{topic.title}' перемещена под '{parent_topic.title}'",
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при назначении родителя темы: {e}")
            return {"error": f"Ошибка при назначении родителя: {e!s}"}
