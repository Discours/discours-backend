from __future__ import annotations

from typing import Any

from graphql import GraphQLResolveInfo
from sqlalchemy.sql import and_

from auth.orm import Author, AuthorFollower
from orm.community import Community, CommunityFollower
from orm.shout import Shout, ShoutReactionsFollower
from orm.topic import Topic, TopicFollower
from services.auth import login_required
from services.db import local_session
from services.notify import notify_follower
from services.redis import redis
from services.schema import mutation, query
from utils.logger import root_logger as logger


@mutation.field("follow")
@login_required
async def follow(
    _: None, info: GraphQLResolveInfo, what: str, slug: str = "", entity_id: int | None = None
) -> dict[str, Any]:
    logger.debug("Начало выполнения функции 'follow'")
    viewer_id = info.context.get("author", {}).get("id")
    if not viewer_id:
        return {"error": "Access denied"}
    follower_dict = info.context.get("author") or {}
    logger.debug(f"follower: {follower_dict}")

    if not viewer_id or not follower_dict:
        logger.warning("Неавторизованный доступ при попытке подписаться")
        return {"error": "UnauthorizedError"}

    follower_id = follower_dict.get("id")
    logger.debug(f"follower_id: {follower_id}")

    # Поздние импорты для избежания циклических зависимостей
    from cache.cache import (
        cache_author,
        cache_topic,
        get_cached_follower_authors,
        get_cached_follower_topics,
    )

    entity_classes = {
        "AUTHOR": (Author, AuthorFollower, get_cached_follower_authors, cache_author),
        "TOPIC": (Topic, TopicFollower, get_cached_follower_topics, cache_topic),
        "COMMUNITY": (Community, CommunityFollower, None, None),  # Нет методов кэша для сообщества
        "SHOUT": (Shout, ShoutReactionsFollower, None, None),  # Нет методов кэша для shout
    }

    if what not in entity_classes:
        logger.error(f"Неверный тип для следования: {what}")
        return {"error": "invalid follow type"}

    entity_class, follower_class, get_cached_follows_method, cache_method = entity_classes[what]
    entity_type = what.lower()
    follows: list[dict[str, Any]] = []
    error: str | None = None

    try:
        logger.debug("Попытка получить сущность из базы данных")
        with local_session() as session:
            # Используем query для получения сущности
            entity_query = session.query(entity_class)

            # Проверяем наличие slug перед фильтрацией
            if hasattr(entity_class, "slug"):
                entity_query = entity_query.where(entity_class.slug == slug)

            entity = entity_query.first()

            if not entity:
                logger.warning(f"{what.lower()} не найден по slug: {slug}")
                return {"error": f"{what.lower()} not found"}

            # Получаем ID сущности
            if entity_id is None:
                entity_id = getattr(entity, "id", None)

            if not entity_id:
                logger.warning(f"Не удалось получить ID для {what.lower()}")
                return {"error": f"Cannot get ID for {what.lower()}"}

            # Если это автор, учитываем фильтрацию данных
            entity_dict = entity.dict() if hasattr(entity, "dict") else {}

            logger.debug(f"entity_id: {entity_id}, entity_dict: {entity_dict}")

            if entity_id is not None and isinstance(entity_id, int):
                existing_sub = (
                    session.query(follower_class)
                    .where(
                        follower_class.follower == follower_id,  # type: ignore[attr-defined]
                        getattr(follower_class, entity_type) == entity_id,  # type: ignore[attr-defined]
                    )
                    .first()
                )
                if existing_sub:
                    logger.info(f"Пользователь {follower_id} уже подписан на {what.lower()} с ID {entity_id}")
                    error = "already following"
                else:
                    logger.debug("Добавление новой записи в базу данных")
                    sub = follower_class(follower=follower_id, **{entity_type: entity_id})
                    logger.debug(f"Создан объект подписки: {sub}")
                    session.add(sub)
                    session.commit()
                    logger.info(f"Пользователь {follower_id} подписался на {what.lower()} с ID {entity_id}")

                # Инвалидируем кэш подписок пользователя после любой операции
                cache_key_pattern = f"author:follows-{entity_type}s:{follower_id}"
                await redis.execute("DEL", cache_key_pattern)
                logger.debug(f"Инвалидирован кэш подписок: {cache_key_pattern}")

                if cache_method:
                    logger.debug("Обновление кэша сущности")
                    await cache_method(entity_dict)

                if what == "AUTHOR" and not existing_sub:
                    logger.debug("Отправка уведомления автору о подписке")
                    if isinstance(follower_dict, dict) and isinstance(entity_id, int):
                        await notify_follower(follower=follower_dict, author_id=entity_id, action="follow")

        # Всегда получаем актуальный список подписок для возврата клиенту
        if get_cached_follows_method and isinstance(follower_id, int):
            logger.debug("Получение актуального списка подписок из кэша")
            existing_follows = await get_cached_follows_method(follower_id)

            # Если это авторы, получаем безопасную версию
            if what == "AUTHOR":
                follows_filtered = []

                for author_data in existing_follows:
                    # Создаем объект автора для использования метода dict
                    temp_author = Author()
                    for key, value in author_data.items():
                        if hasattr(temp_author, key):
                            setattr(temp_author, key, value)
                    # Добавляем отфильтрованную версию
                    follows_filtered.append(temp_author.dict())

                follows = follows_filtered
            else:
                follows = existing_follows

            logger.debug(f"Актуальный список подписок получен: {len(follows)} элементов")

        return {f"{entity_type}s": follows, "error": error}

    except Exception as exc:
        logger.exception("Произошла ошибка в функции 'follow'")
        return {"error": str(exc)}


@mutation.field("unfollow")
@login_required
async def unfollow(
    _: None, info: GraphQLResolveInfo, what: str, slug: str = "", entity_id: int | None = None
) -> dict[str, Any]:
    logger.debug("Начало выполнения функции 'unfollow'")
    viewer_id = info.context.get("author", {}).get("id")
    if not viewer_id:
        return {"error": "Access denied"}
    follower_dict = info.context.get("author") or {}
    logger.debug(f"follower: {follower_dict}")

    if not viewer_id or not follower_dict:
        logger.warning("Неавторизованный доступ при попытке отписаться")
        return {"error": "UnauthorizedError"}

    follower_id = follower_dict.get("id")
    logger.debug(f"follower_id: {follower_id}")

    # Поздние импорты для избежания циклических зависимостей
    from cache.cache import (
        cache_author,
        cache_topic,
        get_cached_follower_authors,
        get_cached_follower_topics,
    )

    entity_classes = {
        "AUTHOR": (Author, AuthorFollower, get_cached_follower_authors, cache_author),
        "TOPIC": (Topic, TopicFollower, get_cached_follower_topics, cache_topic),
        "COMMUNITY": (Community, CommunityFollower, None, None),  # Нет методов кэша для сообщества
        "SHOUT": (Shout, ShoutReactionsFollower, None, None),  # Нет методов кэша для shout
    }

    if what not in entity_classes:
        logger.error(f"Неверный тип для отписки: {what}")
        return {"error": "invalid unfollow type"}

    entity_class, follower_class, get_cached_follows_method, cache_method = entity_classes[what]
    entity_type = what.lower()
    follows: list[dict[str, Any]] = []

    try:
        logger.debug("Попытка получить сущность из базы данных")
        with local_session() as session:
            # Используем query для получения сущности
            entity_query = session.query(entity_class)
            if hasattr(entity_class, "slug"):
                entity_query = entity_query.where(entity_class.slug == slug)

            entity = entity_query.first()
            logger.debug(f"Полученная сущность: {entity}")
            if not entity:
                logger.warning(f"{what.lower()} не найден по slug: {slug}")
                return {"error": f"{what.lower()} not found"}

            if not entity_id:
                entity_id = getattr(entity, "id", None)
                if not entity_id:
                    logger.warning(f"Не удалось получить ID для {what.lower()}")
                    return {"error": f"Cannot get ID for {what.lower()}"}

            logger.debug(f"entity_id: {entity_id}")
            sub = (
                session.query(follower_class)
                .where(
                    and_(
                        follower_class.follower == follower_id,  # type: ignore[attr-defined]
                        getattr(follower_class, entity_type) == entity_id,  # type: ignore[attr-defined]
                    )
                )
                .first()
            )
            if not sub:
                logger.warning(f"Подписка не найдена для {what.lower()} с ID {entity_id}")
                return {"error": "Not following"}

            logger.debug(f"Найдена подписка для удаления: {sub}")
            session.delete(sub)
            session.commit()
            logger.info(f"Пользователь {follower_id} отписался от {what.lower()} с ID {entity_id}")

            # Инвалидируем кэш подписок пользователя
            cache_key_pattern = f"author:follows-{entity_type}s:{follower_id}"
            await redis.execute("DEL", cache_key_pattern)
            logger.debug(f"Инвалидирован кэш подписок: {cache_key_pattern}")

            if get_cached_follows_method and isinstance(follower_id, int):
                logger.debug("Получение актуального списка подписок из кэша")
                follows = await get_cached_follows_method(follower_id)
                logger.debug(f"Актуальный список подписок получен: {len(follows)} элементов")
            else:
                follows = []

            if what == "AUTHOR" and isinstance(follower_dict, dict):
                await notify_follower(follower=follower_dict, author_id=entity_id, action="unfollow")

            return {f"{entity_type}s": follows, "error": None}

    except Exception as exc:
        logger.exception("Произошла ошибка в функции 'unfollow'")
        return {"error": str(exc)}


@query.field("get_shout_followers")
def get_shout_followers(
    _: None, _info: GraphQLResolveInfo, slug: str = "", shout_id: int | None = None
) -> list[dict[str, Any]]:
    """
    Получает список подписчиков для шаута по slug или ID

    Args:
        _: GraphQL root
        _info: GraphQL context info
        slug: Slug шаута (опционально)
        shout_id: ID шаута (опционально)

    Returns:
        Список подписчиков шаута
    """
    if not slug and not shout_id:
        return []

    with local_session() as session:
        # Если slug не указан, ищем шаут по ID
        if not slug and shout_id is not None:
            shout = session.query(Shout).where(Shout.id == shout_id).first()
        else:
            # Ищем шаут по slug
            shout = session.query(Shout).where(Shout.slug == slug).first()

        if not shout:
            return []

        # Получаем подписчиков шаута
        followers_query = (
            session.query(Author)
            .join(ShoutReactionsFollower, Author.id == ShoutReactionsFollower.follower)
            .where(ShoutReactionsFollower.shout == shout.id)
        )

        followers = followers_query.all()

        # Возвращаем безопасную версию данных
        return [follower.dict() for follower in followers]
