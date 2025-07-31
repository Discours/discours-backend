from typing import Any, Optional

import orjson
from graphql import GraphQLResolveInfo
from sqlalchemy import Select, and_, nulls_last, text
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.expression import asc, case, desc, func, select

from auth.orm import Author
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic
from services.db import json_array_builder, json_builder, local_session
from services.schema import query
from services.search import SearchService, search_text
from services.viewed import ViewedStorage
from utils.logger import root_logger as logger


def apply_options(q: Select, options: dict[str, Any], reactions_created_by: int = 0) -> tuple[Select, int, int]:
    """
    Применяет опции фильтрации и сортировки
    [опционально] выбирая те публикации, на которые есть реакции/комментарии от указанного автора

    :param q: Исходный запрос.
    :param options: Опции фильтрации и сортировки.
    :param reactions_created_by: Идентификатор автора.
    :return: Запрос с примененными опциями.
    """
    filters = options.get("filters")
    if isinstance(filters, dict):
        q = apply_filters(q, filters)
        if reactions_created_by:
            q = q.join(Reaction, Reaction.shout == Shout.id)
            q = q.where(Reaction.created_by == reactions_created_by)
            if "commented" in filters:
                q = q.where(Reaction.body.is_not(None))
    q = apply_sorting(q, options)
    limit = options.get("limit", 10)
    offset = options.get("offset", 0)
    return q, limit, offset


def has_field(info: GraphQLResolveInfo, fieldname: str) -> bool:
    """
    Проверяет, запрошено ли поле :fieldname: в GraphQL запросе

    :param info: Информация о контексте GraphQL
    :param fieldname: Имя запрашиваемого поля
    :return: True, если поле запрошено, False в противном случае
    """
    field_node = info.field_nodes[0]
    if field_node.selection_set is None:
        return False
    for selection in field_node.selection_set.selections:
        if hasattr(selection, "name") and selection.name.value == fieldname:
            return True
    return False


def query_with_stat(info: GraphQLResolveInfo) -> Select:
    """
    :param info: Информация о контексте GraphQL - для получения id авторизованного пользователя
    :return: Запрос с подзапросами статистики.

    Добавляет подзапрос статистики
    """
    q = select(Shout).where(
        and_(
            Shout.published_at.is_not(None),  # type: ignore[union-attr]
            Shout.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )

    # Главный автор
    main_author = aliased(Author)
    q = q.join(main_author, main_author.id == Shout.created_by)
    q = q.add_columns(
        json_builder(
            "id",
            main_author.id,
            "name",
            main_author.name,
            "slug",
            main_author.slug,
            "pic",
            main_author.pic,
            "created_at",
            main_author.created_at,
        ).label("main_author")
    )

    if has_field(info, "main_topic"):
        main_topic_join = aliased(ShoutTopic)
        main_topic = aliased(Topic)
        q = q.join(main_topic_join, and_(main_topic_join.shout == Shout.id, main_topic_join.main.is_(True)))
        q = q.join(main_topic, main_topic.id == main_topic_join.topic)
        q = q.add_columns(
            json_builder(
                "id",
                main_topic.id,
                "title",
                main_topic.title,
                "slug",
                main_topic.slug,
                "is_main",
                main_topic_join.main,
            ).label("main_topic")
        )

    if has_field(info, "authors"):
        authors_subquery = (
            select(
                ShoutAuthor.shout,
                json_array_builder(
                    json_builder(
                        "id",
                        Author.id,
                        "name",
                        Author.name,
                        "slug",
                        Author.slug,
                        "pic",
                        Author.pic,
                        "caption",
                        ShoutAuthor.caption,
                        "created_at",
                        Author.created_at,
                    )
                ).label("authors"),
            )
            .outerjoin(Author, ShoutAuthor.author == Author.id)
            .where(ShoutAuthor.shout == Shout.id)
            .group_by(ShoutAuthor.shout)
            .subquery()
        )
        q = q.outerjoin(authors_subquery, authors_subquery.c.shout == Shout.id)
        q = q.add_columns(authors_subquery.c.authors)

    if has_field(info, "topics"):
        topics_subquery = (
            select(
                ShoutTopic.shout,
                json_array_builder(
                    json_builder("id", Topic.id, "title", Topic.title, "slug", Topic.slug, "is_main", ShoutTopic.main)
                ).label("topics"),
            )
            .outerjoin(Topic, ShoutTopic.topic == Topic.id)
            .where(ShoutTopic.shout == Shout.id)
            .group_by(ShoutTopic.shout)
            .subquery()
        )
        q = q.outerjoin(topics_subquery, topics_subquery.c.shout == Shout.id)
        q = q.add_columns(topics_subquery.c.topics)

    if has_field(info, "stat"):
        stats_subquery = (
            select(
                Reaction.shout,
                func.count(func.distinct(Reaction.id))
                .where(Reaction.kind == ReactionKind.COMMENT.value)
                .label("comments_count"),
                func.sum(
                    case(
                        (Reaction.kind == ReactionKind.LIKE.value, 1),
                        (Reaction.kind == ReactionKind.DISLIKE.value, -1),
                        else_=0,
                    )
                )
                .where(Reaction.reply_to.is_(None))
                .label("rating"),
                func.max(Reaction.created_at)
                .where(Reaction.kind == ReactionKind.COMMENT.value)
                .label("last_commented_at"),
            )
            .where(Reaction.deleted_at.is_(None))
            .group_by(Reaction.shout)
            .subquery()
        )
        q = q.outerjoin(stats_subquery, stats_subquery.c.shout == Shout.id)
        q = q.add_columns(
            json_builder(
                "comments_count",
                func.coalesce(stats_subquery.c.comments_count, 0),
                "rating",
                func.coalesce(stats_subquery.c.rating, 0),
                "last_commented_at",
                func.coalesce(stats_subquery.c.last_commented_at, 0),
            ).label("stat")
        )

    return q


def get_shouts_with_links(info: GraphQLResolveInfo, q: Select, limit: int = 20, offset: int = 0) -> list[Shout]:
    """
    получение публикаций с применением пагинации
    """
    shouts = []
    try:
        # logger.info(f"Starting get_shouts_with_links with limit={limit}, offset={offset}")
        q = q.limit(limit).offset(offset)

        with local_session() as session:
            shouts_result = session.execute(q).all()
            # logger.info(f"Got {len(shouts_result) if shouts_result else 0} shouts from query")

            if not shouts_result:
                logger.warning("No shouts found in query result")
                return []

            for idx, row in enumerate(shouts_result):
                try:
                    shout = None
                    if hasattr(row, "Shout"):
                        shout = row.Shout
                        # logger.debug(f"Processing shout#{shout.id} at index {idx}")
                    if shout:
                        shout_id = int(f"{shout.id}")
                        shout_dict = shout.dict()

                        # Обработка поля created_by
                        if has_field(info, "created_by") and shout_dict.get("created_by"):
                            main_author_id = shout_dict.get("created_by")
                            a = session.query(Author).where(Author.id == main_author_id).first()
                            if a:
                                shout_dict["created_by"] = {
                                    "id": main_author_id,
                                    "name": a.name,
                                    "slug": a.slug or f"user-{main_author_id}",
                                    "pic": a.pic,
                                }

                        # Обработка поля updated_by
                        if has_field(info, "updated_by"):
                            if shout_dict.get("updated_by"):
                                updated_by_id = shout_dict.get("updated_by")
                                updated_author = session.query(Author).where(Author.id == updated_by_id).first()
                                if updated_author:
                                    shout_dict["updated_by"] = {
                                        "id": updated_author.id,
                                        "name": updated_author.name,
                                        "slug": updated_author.slug or f"user-{updated_author.id}",
                                        "pic": updated_author.pic,
                                    }
                                else:
                                    # Если автор не найден, устанавливаем поле в null
                                    shout_dict["updated_by"] = None
                            else:
                                # Если updated_by не указан, устанавливаем поле в null
                                shout_dict["updated_by"] = None

                        # Обработка поля deleted_by
                        if has_field(info, "deleted_by"):
                            if shout_dict.get("deleted_by"):
                                deleted_by_id = shout_dict.get("deleted_by")
                                deleted_author = session.query(Author).where(Author.id == deleted_by_id).first()
                                if deleted_author:
                                    shout_dict["deleted_by"] = {
                                        "id": deleted_author.id,
                                        "name": deleted_author.name,
                                        "slug": deleted_author.slug or f"user-{deleted_author.id}",
                                        "pic": deleted_author.pic,
                                    }
                                else:
                                    # Если автор не найден, устанавливаем поле в null
                                    shout_dict["deleted_by"] = None
                            else:
                                # Если deleted_by не указан, устанавливаем поле в null
                                shout_dict["deleted_by"] = None

                        if has_field(info, "stat"):
                            stat = {}
                            if hasattr(row, "stat"):
                                if isinstance(row.stat, str):
                                    stat = orjson.loads(row.stat)
                                elif isinstance(row.stat, dict):
                                    stat = row.stat
                            viewed = ViewedStorage.get_shout(shout_id=shout_id) or 0
                            shout_dict["stat"] = {**stat, "viewed": viewed}

                        # Обработка main_topic и topics
                        topics = None
                        if has_field(info, "topics") and hasattr(row, "topics"):
                            topics = orjson.loads(row.topics) if isinstance(row.topics, str) else row.topics
                            # logger.debug(f"Shout#{shout_id} topics: {topics}")
                            shout_dict["topics"] = topics

                        if has_field(info, "main_topic"):
                            main_topic = None
                            if hasattr(row, "main_topic"):
                                # logger.debug(f"Raw main_topic for shout#{shout_id}: {row.main_topic}")
                                main_topic = (
                                    orjson.loads(row.main_topic) if isinstance(row.main_topic, str) else row.main_topic
                                )
                                # logger.debug(f"Parsed main_topic for shout#{shout_id}: {main_topic}")

                            if not main_topic and topics and len(topics) > 0:
                                # logger.info(f"No main_topic found for shout#{shout_id}, using first topic from list")
                                main_topic = {
                                    "id": topics[0]["id"],
                                    "title": topics[0]["title"],
                                    "slug": topics[0]["slug"],
                                    "is_main": True,
                                }
                            elif not main_topic:
                                logger.warning(f"No main_topic and no topics found for shout#{shout_id}")
                                main_topic = {
                                    "id": 0,
                                    "title": "no topic",
                                    "slug": "notopic",
                                    "is_main": True,
                                }
                            shout_dict["main_topic"] = main_topic
                            # logger.debug(f"Final main_topic for shout#{shout_id}: {main_topic}")

                        if has_field(info, "authors") and hasattr(row, "authors"):
                            authors_data = orjson.loads(row.authors) if isinstance(row.authors, str) else row.authors
                            # Проверяем и добавляем значение по умолчанию для slug, если оно пустое
                            if authors_data:
                                for author in authors_data:
                                    if not author.get("slug"):
                                        author["slug"] = f"user-{author.get('id', 'unknown')}"
                            shout_dict["authors"] = authors_data

                        if has_field(info, "media") and shout.media:
                            # Обработка поля media
                            media_data = shout.media
                            if isinstance(media_data, str):
                                try:
                                    media_data = orjson.loads(media_data)
                                except orjson.JSONDecodeError:
                                    media_data = []
                            shout_dict["media"] = [media_data] if isinstance(media_data, dict) else media_data

                        shouts.append(shout_dict)

                except Exception as row_error:
                    logger.error(f"Error processing row {idx}: {row_error}", exc_info=True)
                    continue

    except Exception as e:
        logger.error(f"Fatal error in get_shouts_with_links: {e}", exc_info=True)
        raise

    logger.info(f"Returning {len(shouts)} shouts from get_shouts_with_links")
    return shouts


def apply_filters(q: Select, filters: dict[str, Any]) -> Select:
    """
    Применение общих фильтров к запросу.

    :param q: Исходный запрос.
    :param filters: Словарь фильтров.
    :return: Запрос с примененными фильтрами.
    """
    if isinstance(filters, dict):
        if "featured" in filters:
            featured_filter = filters.get("featured")
            featured_at_col = getattr(Shout, "featured_at", None)
            if featured_at_col is not None:
                q = q.where(featured_at_col.is_not(None)) if featured_filter else q.where(featured_at_col.is_(None))
        by_layouts = filters.get("layouts")
        if by_layouts and isinstance(by_layouts, list):
            q = q.where(Shout.layout.in_(by_layouts))
        by_author = filters.get("author")
        if by_author:
            q = q.where(Shout.authors.any(slug=by_author))
        by_topic = filters.get("topic")
        if by_topic:
            q = q.where(Shout.topics.any(slug=by_topic))
        by_after = filters.get("after")
        if by_after:
            ts = int(by_after)
            q = q.where(Shout.created_at > ts)
        by_community = filters.get("community")
        if by_community:
            q = q.where(Shout.community == by_community)

    return q


@query.field("get_shout")
async def get_shout(_: None, info: GraphQLResolveInfo, slug: str = "", shout_id: int = 0) -> Optional[Shout]:
    """
    Получение публикации по slug или id.

    :param _: Корневой объект запроса (не используется)
    :param info: Информация о контексте GraphQL
    :param slug: Уникальный идентификатор публикации
    :param shout_id: ID публикации
    :return: Данные публикации с включенной статистикой
    """
    try:
        # Получаем базовый запрос с подзапросами статистики
        q = query_with_stat(info)

        # Применяем фильтр по slug или id
        if slug:
            q = q.where(Shout.slug == slug)
        elif shout_id:
            q = q.where(Shout.id == shout_id)
        else:
            return None

        # Получаем результат через get_shouts_with_stats с limit=1
        shouts = get_shouts_with_links(info, q, limit=1)

        # Возвращаем первую (и единственную) публикацию, если она найдена
        if shouts:
            return shouts[0]
        return None

    except Exception as exc:
        logger.error(f"Error in get_shout: {exc}", exc_info=True)
        return None


def apply_sorting(q: Select, options: dict[str, Any]) -> Select:
    """
    Применение сортировки с сохранением порядка
    """
    order_str = options.get("order_by")
    if order_str in ["rating", "comments_count", "last_commented_at"]:
        query_order_by = desc(text(order_str)) if options.get("order_by_desc", True) else asc(text(order_str))
        q = q.distinct(text(order_str), Shout.id).order_by(  # DISTINCT ON включает поле сортировки
            nulls_last(query_order_by), Shout.id
        )
    else:
        published_at_col = getattr(Shout, "published_at", Shout.id)
        q = q.distinct(published_at_col, Shout.id).order_by(published_at_col.desc(), Shout.id)

    return q


@query.field("load_shouts_by")
async def load_shouts_by(_: None, info: GraphQLResolveInfo, options: dict[str, Any]) -> list[Shout]:
    """
    Загрузка публикаций с фильтрацией, сортировкой и пагинацией.

    :param _: Корневой объект запроса (не используется)
    :param info: Информация о контексте GraphQL
    :param options: Опции фильтрации и сортировки
    :return: Список публикаций, удовлетворяющих критериям
    """
    # Базовый запрос со статистикой
    q = query_with_stat(info)

    # Применяем остальные опции фильтрации
    q, limit, offset = apply_options(q, options)

    # Передача сформированного запроса в метод получения публикаций с учетом сортировки и пагинации
    return get_shouts_with_links(info, q, limit, offset)


@query.field("load_shouts_search")
async def load_shouts_search(
    _: None, info: GraphQLResolveInfo, text: str, options: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Поиск публикаций по тексту.

    :param _: Корневой объект запроса (не используется)
    :param info: Информация о контексте GraphQL
    :param text: Строка поиска.
    :param options: Опции фильтрации и сортировки.
    :return: Список публикаций, найденных по тексту.
    """
    limit = options.get("limit", 10)
    offset = options.get("offset", 0)

    logger.info(f"[load_shouts_search] Starting search for '{text}' with limit={limit}, offset={offset}")

    if isinstance(text, str) and len(text) > 2:
        logger.debug(f"[load_shouts_search] Calling search_text service for '{text}'")
        results = await search_text(text, limit, offset)

        logger.debug(f"[load_shouts_search] Search service returned {len(results)} results for '{text}'")

        scores = {}
        hits_ids = []
        for i, sr in enumerate(results):
            shout_id = sr.get("id")
            if shout_id:
                shout_id = str(shout_id)
                scores[shout_id] = sr.get("score", 0.0)
                hits_ids.append(shout_id)
                logger.debug(f"[load_shouts_search] Result {i}: id={shout_id}, score={scores[shout_id]}")
            else:
                logger.warning(f"[load_shouts_search] Result {i} missing id: {sr}")

        logger.debug(f"[load_shouts_search] Extracted {len(hits_ids)} shout IDs: {hits_ids}")

        if not hits_ids:
            logger.warning(f"[load_shouts_search] No valid shout IDs found for query '{text}'")
            return []

        q = (
            query_with_stat(info)
            if has_field(info, "stat")
            else select(Shout).where(and_(Shout.published_at.is_not(None), Shout.deleted_at.is_(None)))
        )
        q = q.where(Shout.id.in_(hits_ids))
        q = apply_filters(q, options)
        q = apply_sorting(q, options)

        logger.debug(f"[load_shouts_search] Executing database query for {len(hits_ids)} shout IDs")
        shouts = get_shouts_with_links(info, q, limit, offset)
        logger.debug(f"[load_shouts_search] Database returned {len(shouts)} shouts")
        shouts_dicts: list[dict[str, Any]] = []
        for shout in shouts:
            shout_dict = shout.dict()
            shout_id_str = shout_dict.get("id")
            if shout_id_str:
                shout_dict["score"] = scores.get(shout_id_str, 0.0)
            shouts_dicts.append(shout_dict)

        shouts_dicts.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        logger.info(f"[load_shouts_search] Returning {len(shouts_dicts)} sorted shouts for '{text}'")
        return shouts_dicts
    logger.warning(f"[load_shouts_search] Invalid search query: '{text}' (length={len(text) if text else 0})")

    return []


@query.field("load_shouts_unrated")
async def load_shouts_unrated(_: None, info: GraphQLResolveInfo, options: dict[str, Any]) -> list[Shout]:
    """
    Загрузка публикаций с менее чем 3 реакциями типа LIKE/DISLIKE

    :param _: Корневой объект запроса (не используется)
    :param info: Информация о контексте GraphQL
    :param options: Опции фильтрации и сортировки.
    :return: Список публикаций.
    """
    rated_shouts = (
        select(Reaction.shout)
        .where(
            and_(
                Reaction.deleted_at.is_(None),
                Reaction.kind.in_([ReactionKind.LIKE.value, ReactionKind.DISLIKE.value]),
            )
        )
        .group_by(Reaction.shout)
        .having(func.count(Reaction.id) >= 3)
        .scalar_subquery()
    )

    q = select(Shout).where(and_(Shout.published_at.is_not(None), Shout.deleted_at.is_(None)))
    q = q.join(Author, Author.id == Shout.created_by)
    q = q.add_columns(
        json_builder("id", Author.id, "name", Author.name, "slug", Author.slug, "pic", Author.pic).label("main_author")
    )
    q = q.join(ShoutTopic, and_(ShoutTopic.shout == Shout.id, ShoutTopic.main.is_(True)))
    q = q.join(Topic, Topic.id == ShoutTopic.topic)
    q = q.add_columns(json_builder("id", Topic.id, "title", Topic.title, "slug", Topic.slug).label("main_topic"))
    q = q.where(Shout.id.not_in(rated_shouts))
    q = q.order_by(func.random())

    limit = options.get("limit", 5)
    offset = options.get("offset", 0)
    return get_shouts_with_links(info, q, limit, offset)


@query.field("load_shouts_random_top")
async def load_shouts_random_top(_: None, info: GraphQLResolveInfo, options: dict[str, Any]) -> list[Shout]:
    """
    Загрузка случайных публикаций, упорядоченных по топовым реакциям.

    :param _info: Информация о контексте GraphQL.
    :param options: Опции фильтрации и сортировки.
    :return: Список случайных публикаций.
    """
    aliased_reaction = aliased(Reaction)

    subquery = select(Shout.id).outerjoin(aliased_reaction).where(Shout.deleted_at.is_(None))

    filters = options.get("filters")
    if isinstance(filters, dict):
        subquery = apply_filters(subquery, filters)

    subquery = subquery.group_by(Shout.id).order_by(
        desc(
            func.sum(
                case(
                    # не учитывать реакции на комментарии
                    (aliased_reaction.reply_to.is_not(None), 0),
                    (aliased_reaction.kind == ReactionKind.LIKE.value, 1),
                    (aliased_reaction.kind == ReactionKind.DISLIKE.value, -1),
                    else_=0,
                )
            )
        )
    )

    random_limit = options.get("random_limit", 100)
    subquery = subquery.limit(random_limit)
    q = query_with_stat(info)
    q = q.where(Shout.id.in_(subquery))
    q = q.order_by(func.random())
    limit = options.get("limit", 10)
    return get_shouts_with_links(info, q, limit)


async def fetch_all_shouts(
    session: Session,
    search_service: SearchService,
    limit: int = 100,
    offset: int = 0,
    search_query: str = "",
) -> list[Shout]:
    """
    Получает все shout'ы с возможностью поиска и пагинации.

    :param session: Сессия базы данных
    :param search_service: Сервис поиска
    :param limit: Максимальное количество возвращаемых shout'ов
    :param offset: Смещение для пагинации
    :param search_query: Строка поиска
    :return: Список shout'ов
    """
    try:
        # Базовый запрос для получения shout'ов
        q = select(Shout).where(and_(Shout.published_at.is_not(None), Shout.deleted_at.is_(None)))

        # Применяем поиск, если есть строка поиска
        if search_query:
            search_results = await search_service.search(search_query, limit=100, offset=0)
            if search_results:
                # Извлекаем ID из результатов поиска
                shout_ids = [result.get("id") for result in search_results if result.get("id")]
                if shout_ids:
                    q = q.where(Shout.id.in_(shout_ids))

        # Применяем лимит и смещение
        q = q.limit(limit).offset(offset)

        # Выполняем запрос
        result = session.execute(q).scalars().all()

        return list(result)
    except Exception as e:
        logger.error(f"Error fetching shouts: {e}")
        return []
    finally:
        session.close()
