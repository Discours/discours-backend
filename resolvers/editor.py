import time
from typing import Any

import orjson
from graphql import GraphQLResolveInfo
from sqlalchemy import and_, desc, select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import coalesce

from auth.orm import Author
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic
from resolvers.follower import follow
from resolvers.stat import get_with_stat
from services.auth import login_required
from services.common_result import CommonResult
from services.db import local_session
from services.notify import notify_shout
from services.schema import mutation, query
from services.search import search_service
from utils.extract_text import extract_text
from utils.logger import root_logger as logger


async def cache_by_id(entity, entity_id: int, cache_method) -> None:
    """Cache an entity by its ID using the provided cache method.

    Args:
        entity: The SQLAlchemy model class to query
        entity_id (int): The ID of the entity to cache
        cache_method: The caching function to use

    Returns:
        dict: The cached entity data if successful, None if entity not found

    Example:
        >>> async def test_cache():
        ...     author = await cache_by_id(Author, 1, cache_author)
        ...     assert author['id'] == 1
        ...     assert 'name' in author
        ...     return author
    """
    caching_query = select(entity).where(entity.id == entity_id)
    result = get_with_stat(caching_query)
    if not result or not result[0]:
        logger.warning(f"{entity.__name__} with id {entity_id} not found")
        return None
    x = result[0]
    d = x.dict()  # convert object to dictionary
    await cache_method(d)
    return d


@query.field("get_my_shout")
@login_required
async def get_my_shout(_: None, info, shout_id: int) -> dict[str, Any]:
    """Get a shout by ID if the requesting user has permission to view it.

    DEPRECATED: use `load_drafts` instead

    Args:
        info: GraphQL resolver info containing context
        shout_id (int): ID of the shout to retrieve

    Returns:
        dict: Contains either:
            - error (str): Error message if retrieval failed
            - shout (Shout): The requested shout if found and accessible

    Permissions:
        User must be:
        - The shout creator
        - Listed as an author
        - Have editor role

    Example:
        >>> async def test_get_my_shout():
        ...     context = {'user_id': '123', 'author': {'id': 1}, 'roles': []}
        ...     info = type('Info', (), {'context': context})()
        ...     result = await get_my_shout(None, info, 1)
        ...     assert result['error'] is None
        ...     assert result['shout'].id == 1
        ...     return result
    """
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    roles = info.context.get("roles", [])
    shout = None
    if not author_id:
        return {"error": "unauthorized", "shout": None}
    with local_session() as session:
        shout = (
            session.query(Shout)
            .where(Shout.id == shout_id)
            .options(joinedload(Shout.authors), joinedload(Shout.topics))
            .where(Shout.deleted_at.is_(None))
            .first()
        )
        if not shout:
            return {"error": "no shout found", "shout": None}

        # Преобразуем media JSON в список объектов MediaItem
        if hasattr(shout, "media") and shout.media:
            if isinstance(shout.media, str):
                try:
                    shout.media = orjson.loads(shout.media)
                except Exception as e:
                    logger.error(f"Error parsing shout media: {e}")
                    shout.media = []
            elif isinstance(shout.media, list):
                shout.media = shout.media or []
        else:
            shout.media = []  # type: ignore[assignment]

        logger.debug(f"got {len(shout.authors)} shout authors, created by {shout.created_by}")
        is_editor = "editor" in roles
        logger.debug(f"viewer is{'' if is_editor else ' not'} editor")
        is_creator = author_id == shout.created_by
        logger.debug(f"viewer is{'' if is_creator else ' not'} creator")
        is_author = bool(list(filter(lambda x: x.id == int(author_id), list(shout.authors))))
        logger.debug(f"viewer is{'' if is_creator else ' not'} author")
        can_edit = is_editor or is_author or is_creator

        if not can_edit:
            return {"error": "forbidden", "shout": None}

        logger.debug("got shout editor with data")
        return {"error": None, "shout": shout}


@query.field("get_shouts_drafts")
@login_required
async def get_shouts_drafts(_: None, info: GraphQLResolveInfo) -> list[dict]:
    author_dict = info.context.get("author") or {}
    if not author_dict:
        return []  # Return empty list instead of error dict
    author_id = author_dict.get("id")
    shouts = []
    with local_session() as session:
        if author_id:
            q = (
                select(Shout)
                .options(joinedload(Shout.authors), joinedload(Shout.topics))
                .where(and_(Shout.deleted_at.is_(None), Shout.created_by == int(author_id)))
                .where(Shout.published_at.is_(None))
                .order_by(desc(coalesce(Shout.updated_at, Shout.created_at)))
                .group_by(Shout.id)
            )
            shouts = [shout.dict() for [shout] in session.execute(q).unique()]
    return shouts


# @mutation.field("create_shout")
# @login_required
async def create_shout(_: None, info: GraphQLResolveInfo, inp: dict) -> dict:
    logger.info(f"Starting create_shout with input: {inp}")
    author_dict = info.context.get("author") or {}
    logger.debug(f"Context author: {author_dict}")

    if not author_dict:
        logger.error("Author profile not found in context")
        return {"error": "author profile was not found"}

    author_id = author_dict.get("id")
    if author_id:
        try:
            with local_session() as session:
                author_id = int(author_id)
                current_time = int(time.time())
                slug = inp.get("slug") or f"draft-{current_time}"

                logger.info(f"Creating shout with input: {inp}")
                # Создаем публикацию без topics
                body = inp.get("body", "")
                lead = inp.get("lead", "")
                body_text = extract_text(body)
                lead_text = extract_text(lead)
                seo_parts = lead_text.strip() or body_text.strip()[:300].split(". ")[:-1]
                seo = inp.get("seo", ". ".join(seo_parts))
                new_shout = Shout(
                    slug=slug,
                    body=body,
                    seo=seo,
                    lead=lead,
                    layout=inp.get("layout", "article"),
                    title=inp.get("title", ""),
                    created_by=author_id,
                    created_at=current_time,
                    community=1,
                )

                # Проверяем уникальность slug
                logger.debug(f"Checking for existing slug: {slug}")
                same_slug_shout = session.query(Shout).where(Shout.slug == new_shout.slug).first()
                c = 1
                while same_slug_shout is not None:
                    logger.debug(f"Found duplicate slug, trying iteration {c}")
                    new_shout.slug = f"{slug}-{c}"  # type: ignore[assignment]
                    same_slug_shout = session.query(Shout).where(Shout.slug == new_shout.slug).first()
                    c += 1

                try:
                    logger.info("Creating new shout object")
                    session.add(new_shout)
                    session.commit()
                    logger.info(f"Created shout with ID: {new_shout.id}")
                except Exception as e:
                    logger.error(f"Error creating shout object: {e}", exc_info=True)
                    return {"error": f"Database error: {e!s}"}

                # Связываем с автором
                try:
                    logger.debug(f"Linking author {author_id} to shout {new_shout.id}")
                    sa = ShoutAuthor(shout=new_shout.id, author=author_id)
                    session.add(sa)
                except Exception as e:
                    logger.error(f"Error linking author: {e}", exc_info=True)
                    return {"error": f"Error linking author: {e!s}"}

                # Связываем с темами

                input_topics = inp.get("topics", [])
                if input_topics:
                    try:
                        logger.debug(f"Linking topics: {[t.slug for t in input_topics]}")
                        main_topic = inp.get("main_topic")
                        for topic in input_topics:
                            st = ShoutTopic(
                                topic=topic.id,
                                shout=new_shout.id,
                                main=(topic.slug == main_topic) if main_topic else False,
                            )
                            session.add(st)
                            logger.debug(f"Added topic {topic.slug} {'(main)' if st.main else ''}")
                    except Exception as e:
                        logger.error(f"Error linking topics: {e}", exc_info=True)
                        return {"error": f"Error linking topics: {e!s}"}

                try:
                    session.commit()
                    logger.info("Final commit successful")
                except Exception as e:
                    logger.error(f"Error in final commit: {e}", exc_info=True)
                    return {"error": f"Error in final commit: {e!s}"}

                # Получаем созданную публикацию
                shout = session.query(Shout).where(Shout.id == new_shout.id).first()

                if shout:
                    # Подписываем автора
                    try:
                        logger.debug("Following created shout")
                        await follow(None, info, "shout", shout.slug)
                    except Exception as e:
                        logger.warning(f"Error following shout: {e}", exc_info=True)

                    logger.info(f"Successfully created shout {shout.id}")
                    return {"shout": shout}

        except Exception as e:
            logger.error(f"Unexpected error in create_shout: {e}", exc_info=True)
            return {"error": f"Unexpected error: {e!s}"}

    error_msg = "cant create shout" if author_id else "unauthorized"
    logger.error(f"Create shout failed: {error_msg}")
    return {"error": error_msg}


def patch_main_topic(session: Any, main_topic_slug: str, shout: Any) -> None:
    """Update the main topic for a shout."""
    logger.info(f"Starting patch_main_topic for shout#{shout.id} with slug '{main_topic_slug}'")
    logger.debug(f"Current shout topics: {[(t.topic.slug, t.main) for t in shout.topics]}")

    with session.begin():
        # Получаем текущий главный топик
        old_main = (
            session.query(ShoutTopic).where(and_(ShoutTopic.shout == shout.id, ShoutTopic.main.is_(True))).first()
        )
        if old_main:
            logger.info(f"Found current main topic: {old_main.topic.slug}")
        else:
            logger.info("No current main topic found")

        # Находим новый главный топик
        main_topic = session.query(Topic).where(Topic.slug == main_topic_slug).first()
        if not main_topic:
            logger.error(f"Main topic with slug '{main_topic_slug}' not found")
            return

        logger.info(f"Found new main topic: {main_topic.slug} (id={main_topic.id})")

        # Находим связь с новым главным топиком
        new_main = (
            session.query(ShoutTopic)
            .where(and_(ShoutTopic.shout == shout.id, ShoutTopic.topic == main_topic.id))
            .first()
        )
        logger.debug(f"Found new main topic relation: {new_main is not None}")

        if old_main and new_main and old_main is not new_main:
            logger.info(f"Updating main topic flags: {old_main.topic.slug} -> {new_main.topic.slug}")
            old_main.main = False  # type: ignore[assignment]
            session.add(old_main)

            new_main.main = True  # type: ignore[assignment]
            session.add(new_main)

            session.flush()
            logger.info(f"Main topic updated for shout#{shout.id}")
        else:
            logger.warning(f"No changes needed for main topic (old={old_main is not None}, new={new_main is not None})")


def patch_topics(session: Any, shout: Any, topics_input: list[Any]) -> None:
    """Update the topics associated with a shout.

    Args:
        session: SQLAlchemy session
        shout (Shout): The shout to update
        topics_input (list): List of topic dicts with fields:
            - id (int): Topic ID (<0 for new topics)
            - slug (str): Topic slug
            - title (str): Topic title (for new topics)

    Side Effects:
        - Creates new topics if needed
        - Updates shout-topic associations
        - Refreshes shout object with new topics

    Example:
        >>> def test_patch_topics():
        ...     topics = [
        ...         {'id': -1, 'slug': 'new-topic', 'title': 'New Topic'},
        ...         {'id': 1, 'slug': 'existing-topic'}
        ...     ]
        ...     with local_session() as session:
        ...         shout = session.query(Shout).first()
        ...         patch_topics(session, shout, topics)
        ...         assert len(shout.topics) == 2
        ...         assert any(t.slug == 'new-topic' for t in shout.topics)
        ...         return shout.topics
    """
    logger.info(f"Starting patch_topics for shout#{shout.id}")
    logger.info(f"Received topics_input: {topics_input}")

    # Создаем новые топики если есть
    new_topics_to_link = [Topic(**new_topic) for new_topic in topics_input if new_topic["id"] < 0]
    if new_topics_to_link:
        logger.info(f"Creating new topics: {[t.dict() for t in new_topics_to_link]}")
        session.add_all(new_topics_to_link)
        session.flush()

    # Получаем текущие связи
    current_links = session.query(ShoutTopic).where(ShoutTopic.shout == shout.id).all()
    logger.info(f"Current topic links: {[{t.topic: t.main} for t in current_links]}")

    # Удаляем старые связи
    if current_links:
        logger.info(f"Removing old topic links for shout#{shout.id}")
        for link in current_links:
            session.delete(link)
        session.flush()

    # Создаем новые связи
    for topic_input in topics_input:
        topic_id = topic_input["id"]
        if topic_id < 0:
            topic = next(t for t in new_topics_to_link if t.slug == topic_input["slug"])
            topic_id = topic.id

        logger.info(f"Creating new topic link: shout#{shout.id} -> topic#{topic_id}")
        new_link = ShoutTopic(shout=shout.id, topic=topic_id, main=False)
        session.add(new_link)

    session.flush()
    # Обновляем связи в объекте шаута
    session.refresh(shout)

    logger.info(f"Successfully updated topics for shout#{shout.id}")
    logger.info(f"Final shout topics: {[t.dict() for t in shout.topics]}")


# @mutation.field("update_shout")
# @login_required
async def update_shout(
    _: None, info: GraphQLResolveInfo, shout_id: int, shout_input: dict | None = None, *, publish: bool = False
) -> CommonResult:
    # Поздние импорты для избежания циклических зависимостей
    from cache.cache import (
        cache_author,
        cache_topic,
        invalidate_shout_related_cache,
        invalidate_shouts_cache,
    )

    """Update an existing shout with optional publishing"""
    logger.info(f"update_shout called with shout_id={shout_id}, publish={publish}")

    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    if not author_id:
        logger.error("UnauthorizedError update attempt")
        return CommonResult(error="unauthorized", shout=None)

    logger.info(f"Starting update_shout with id={shout_id}, publish={publish}")
    logger.debug(f"Full shout_input: {shout_input}")  # DraftInput
    roles = info.context.get("roles", [])
    current_time = int(time.time())
    shout_input = shout_input or {}
    shout_id = shout_id or shout_input.get("id", shout_id)
    slug = shout_input.get("slug")

    try:
        with local_session() as session:
            if author_id:
                logger.info(f"Processing update for shout#{shout_id} by author #{author_id}")
                shout_by_id = (
                    session.query(Shout)
                    .options(joinedload(Shout.topics).joinedload(ShoutTopic.topic), joinedload(Shout.authors))
                    .where(Shout.id == shout_id)
                    .first()
                )

                if not shout_by_id:
                    logger.error(f"shout#{shout_id} not found")
                    return CommonResult(error="shout not found", shout=None)

                logger.info(f"Found shout#{shout_id}")

                # Логируем текущие топики
                current_topics = (
                    [{"id": t.id, "slug": t.slug, "title": t.title} for t in shout_by_id.topics]
                    if shout_by_id.topics
                    else []
                )
                logger.info(f"Current topics for shout#{shout_id}: {current_topics}")

                if slug != shout_by_id.slug:
                    same_slug_shout = session.query(Shout).where(Shout.slug == slug).first()
                    c = 1
                    while same_slug_shout is not None:
                        c += 1
                        same_slug_shout.slug = f"{slug}-{c}"  # type: ignore[assignment]
                        same_slug_shout = session.query(Shout).where(Shout.slug == slug).first()
                    shout_input["slug"] = slug
                    logger.info(f"shout#{shout_id} slug patched")

                if filter(lambda x: x.id == author_id, list(shout_by_id.authors)) or "editor" in roles:
                    logger.info(f"Author #{author_id} has permission to edit shout#{shout_id}")

                    # topics patch
                    topics_input = shout_input.get("topics")
                    if topics_input:
                        logger.info(f"Received topics_input for shout#{shout_id}: {topics_input}")
                        try:
                            patch_topics(session, shout_by_id, topics_input)
                            logger.info(f"Successfully patched topics for shout#{shout_id}")

                            # Обновляем связи в сессии после patch_topics
                            session.refresh(shout_by_id)

                        except Exception as e:
                            logger.error(f"Error patching topics: {e}", exc_info=True)
                            return CommonResult(error=f"Failed to update topics: {e!s}", shout=None)

                        del shout_input["topics"]
                        for tpc in topics_input:
                            await cache_by_id(Topic, tpc["id"], cache_topic)
                    else:
                        logger.warning(f"No topics_input received for shout#{shout_id}")

                    # main topic
                    main_topic = shout_input.get("main_topic")
                    if main_topic:
                        logger.info(f"Updating main topic for shout#{shout_id} to {main_topic}")
                        patch_main_topic(session, main_topic, shout_by_id)

                    shout_by_id.updated_at = current_time  # type: ignore[assignment]
                    if publish:
                        logger.info(f"Publishing shout#{shout_id}")
                        shout_by_id.published_at = current_time  # type: ignore[assignment]
                        # Проверяем наличие связи с автором
                        logger.info(f"Checking author link for shout#{shout_id} and author#{author_id}")
                        author_link = (
                            session.query(ShoutAuthor)
                            .where(and_(ShoutAuthor.shout == shout_id, ShoutAuthor.author == author_id))
                            .first()
                        )

                        if not author_link:
                            logger.info(f"Adding missing author link for shout#{shout_id}")
                            sa = ShoutAuthor(shout=shout_id, author=author_id)
                            session.add(sa)
                            session.flush()
                            logger.info("Author link added successfully")
                        else:
                            logger.info("Author link already exists")

                    # Логируем финальное состояние перед сохранением
                    logger.info(f"Final shout_input for update: {shout_input}")
                    Shout.update(shout_by_id, shout_input)
                    session.add(shout_by_id)

                    try:
                        session.commit()
                        # Обновляем объект после коммита чтобы получить все связи
                        session.refresh(shout_by_id)
                        logger.info(f"Successfully committed updates for shout#{shout_id}")
                    except Exception as e:
                        logger.error(f"Commit failed: {e}", exc_info=True)
                        return CommonResult(error=f"Failed to save changes: {e!s}", shout=None)

                    # После обновления проверяем топики
                    updated_topics = (
                        [{"id": t.id, "slug": t.slug, "title": t.title} for t in shout_by_id.topics]
                        if shout_by_id.topics
                        else []
                    )
                    logger.info(f"Updated topics for shout#{shout_id}: {updated_topics}")

                    # Инвалидация кэша после обновления
                    try:
                        logger.info("Invalidating cache after shout update")

                        cache_keys = [
                            "feed",  # лента
                            f"author_{author_id}",  # публикации автора
                            "random_top",  # случайные топовые
                            "unrated",  # неоцененные
                        ]

                        # Добавляем ключи для тем публикации
                        for topic in shout_by_id.topics:
                            cache_keys.append(f"topic_{topic.id}")
                            cache_keys.append(f"topic_shouts_{topic.id}")

                        await invalidate_shouts_cache(cache_keys)
                        await invalidate_shout_related_cache(shout_by_id, author_id)

                        # Обновляем кэш тем и авторов
                        for topic in shout_by_id.topics:
                            await cache_by_id(Topic, topic.id, cache_topic)
                        for author in shout_by_id.authors:
                            await cache_author(author.dict())

                        logger.info("Cache invalidated successfully")
                    except Exception as cache_error:
                        logger.warning(f"Cache invalidation error: {cache_error}", exc_info=True)

                    if not publish:
                        await notify_shout(shout_by_id.dict(), "update")
                    else:
                        await notify_shout(shout_by_id.dict(), "published")
                        # search service indexing
                        search_service.index(shout_by_id)
                        for a in shout_by_id.authors:
                            await cache_by_id(Author, a.id, cache_author)
                    logger.info(f"shout#{shout_id} updated")

                    # Return success with the updated shout
                    return CommonResult(error=None, shout=shout_by_id)

                logger.warning(f"Access denied: author #{author_id} cannot edit shout#{shout_id}")
                return CommonResult(error="access denied", shout=None)

            return CommonResult(error="cant update shout", shout=None)
    except Exception as e:
        logger.error(f"Exception in update_shout: {e}", exc_info=True)
        return CommonResult(error="cant update shout", shout=None)


# @mutation.field("delete_shout")
# @login_required
async def delete_shout(_: None, info: GraphQLResolveInfo, shout_id: int) -> CommonResult:
    # Поздние импорты для избежания циклических зависимостей
    from cache.cache import (
        invalidate_shout_related_cache,
    )

    """Delete a shout (mark as deleted)"""
    author_dict = info.context.get("author", {})
    if not author_dict:
        return CommonResult(error="author profile was not found", shout=None)

    author_id = author_dict.get("id")
    roles = info.context.get("roles", [])

    with local_session() as session:
        if author_id and shout_id:
            shout = session.query(Shout).where(Shout.id == shout_id).first()
            if shout:
                # Check if user has permission to delete
                if any(x.id == author_id for x in shout.authors) or "editor" in roles:
                    # Use setattr to avoid MyPy complaints about Column assignment
                    shout.deleted_at = int(time.time())  # type: ignore[assignment]
                    session.add(shout)
                    session.commit()

                    # Get shout data for notification
                    shout_dict = shout.dict()

                    # Invalidate cache
                    await invalidate_shout_related_cache(shout, author_id)

                    # Notify about deletion
                    await notify_shout(shout_dict, "delete")
                    return CommonResult(error=None, shout=shout)
                return CommonResult(error="access denied", shout=None)
        return CommonResult(error="shout not found", shout=None)


def get_main_topic(topics: list[Any]) -> dict[str, Any]:
    """Get the main topic from a list of ShoutTopic objects."""
    logger.info(f"Starting get_main_topic with {len(topics) if topics else 0} topics")
    logger.debug(f"Topics data: {[(t.slug, getattr(t, 'main', False)) for t in topics] if topics else []}")

    if not topics:
        logger.warning("No topics provided to get_main_topic")
        return {"id": 0, "title": "no topic", "slug": "notopic", "is_main": True}

    # Проверяем, является ли topics списком объектов ShoutTopic или Topic
    if hasattr(topics[0], "topic") and topics[0].topic:
        # Для ShoutTopic объектов (старый формат)
        # Find first main topic in original order
        main_topic_rel = next((st for st in topics if getattr(st, "main", False)), None)
        logger.debug(
            f"Found main topic relation: {main_topic_rel.topic.slug if main_topic_rel and main_topic_rel.topic else None}"
        )

        if main_topic_rel and main_topic_rel.topic:
            result = {
                "slug": main_topic_rel.topic.slug,
                "title": main_topic_rel.topic.title,
                "id": main_topic_rel.topic.id,
                "is_main": True,
            }
            logger.info(f"Returning main topic: {result}")
            return result

        # If no main found but topics exist, return first
        if topics and topics[0].topic:
            logger.info(f"No main topic found, using first topic: {topics[0].topic.slug}")
            return {
                "slug": topics[0].topic.slug,
                "title": topics[0].topic.title,
                "id": topics[0].topic.id,
                "is_main": True,
            }
    # Для Topic объектов (новый формат из selectinload)
    # После смены на selectinload у нас просто список Topic объектов
    elif topics:
        logger.info(f"Using first topic as main: {topics[0].slug}")
        return {
            "slug": topics[0].slug,
            "title": topics[0].title,
            "id": topics[0].id,
            "is_main": True,
        }

    logger.warning("No valid topics found, returning default")
    return {"slug": "notopic", "title": "no topic", "id": 0, "is_main": True}


@mutation.field("unpublish_shout")
@login_required
async def unpublish_shout(_: None, info: GraphQLResolveInfo, shout_id: int) -> CommonResult:
    """
    Unpublish a shout by setting published_at to NULL
    """
    # Поздние импорты для избежания циклических зависимостей
    from cache.cache import (
        invalidate_shout_related_cache,
        invalidate_shouts_cache,
    )

    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    roles = info.context.get("roles", [])

    if not author_id:
        return CommonResult(error="Author ID is required", shout=None)

    try:
        with local_session() as session:
            # Получаем шаут с авторами
            shout = session.query(Shout).options(joinedload(Shout.authors)).where(Shout.id == shout_id).first()

            if not shout:
                return CommonResult(error="Shout not found", shout=None)

            # Проверяем права доступа
            can_edit = any(author.id == author_id for author in shout.authors) or "editor" in roles

            if can_edit:
                shout.published_at = None  # type: ignore[assignment]
                shout.updated_at = int(time.time())  # type: ignore[assignment]
                session.add(shout)
                session.commit()

                # Инвалидация кэша
                cache_keys = [
                    "feed",
                    f"author_{author_id}",
                    "random_top",
                    "unrated",
                ]

                # Добавляем ключи для тем публикации
                for topic in shout.topics:
                    cache_keys.append(f"topic_{topic.id}")
                    cache_keys.append(f"topic_shouts_{topic.id}")

                await invalidate_shouts_cache(cache_keys)
                await invalidate_shout_related_cache(shout, author_id)

                # Получаем обновленные данные шаута
                session.refresh(shout)

                logger.info(f"Shout {shout_id} unpublished successfully")
                return CommonResult(error=None, shout=shout)
            return CommonResult(error="Access denied", shout=None)

    except Exception as e:
        logger.error(f"Error unpublishing shout {shout_id}: {e}", exc_info=True)
        return CommonResult(error=f"Failed to unpublish shout: {e!s}", shout=None)
