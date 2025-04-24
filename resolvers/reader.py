import orjson
from graphql import GraphQLResolveInfo
from sqlalchemy import and_, nulls_last, text
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import asc, case, desc, func, select

from orm.author import Author
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic
from services.db import json_array_builder, json_builder, local_session
from services.schema import query
from services.search import search_body_text, search_title_text, search_author_text, get_body_search_count, get_title_search_count, get_author_search_count
from services.viewed import ViewedStorage
from utils.logger import root_logger as logger


def apply_options(q, options, reactions_created_by=0):
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
            q = q.filter(Reaction.created_by == reactions_created_by)
            if "commented" in filters:
                q = q.filter(Reaction.body.is_not(None))
    q = apply_sorting(q, options)
    limit = options.get("limit", 10)
    offset = options.get("offset", 0)
    return q, limit, offset


def has_field(info, fieldname: str) -> bool:
    """
    Проверяет, запрошено ли поле :fieldname: в GraphQL запросе

    :param info: Информация о контексте GraphQL
    :param fieldname: Имя запрашиваемого поля
    :return: True, если поле запрошено, False в противном случае
    """
    field_node = info.field_nodes[0]
    for selection in field_node.selection_set.selections:
        if hasattr(selection, "name") and selection.name.value == fieldname:
            return True
    return False


def query_with_stat(info):
    """
    :param info: Информация о контексте GraphQL - для получения id авторизованного пользователя
    :return: Запрос с подзапросами статистики.

    Добавляет подзапрос статистики
    """
    q = select(Shout).filter(
        and_(
            Shout.published_at.is_not(None),  # Проверяем published_at
            Shout.deleted_at.is_(None),  # Проверяем deleted_at
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
                "id", main_topic.id, "title", main_topic.title, "slug", main_topic.slug, "is_main", main_topic_join.main
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
                .filter(Reaction.kind == ReactionKind.COMMENT.value)
                .label("comments_count"),
                func.sum(
                    case(
                        (Reaction.kind == ReactionKind.LIKE.value, 1),
                        (Reaction.kind == ReactionKind.DISLIKE.value, -1),
                        else_=0,
                    )
                )
                .filter(Reaction.reply_to.is_(None))
                .label("rating"),
                func.max(Reaction.created_at)
                .filter(Reaction.kind == ReactionKind.COMMENT.value)
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


def get_shouts_with_links(info, q, limit=20, offset=0):
    """
    получение публикаций с применением пагинации
    """
    shouts = []
    try:
        q = q.limit(limit).offset(offset)

        with local_session() as session:
            shouts_result = session.execute(q).all()

            if not shouts_result:
                logger.warning("No shouts found in query result")
                return []

            for idx, row in enumerate(shouts_result):
                try:
                    shout = None
                    if hasattr(row, "Shout"):
                        shout = row.Shout
                    if shout:
                        shout_id = int(f"{shout.id}")
                        shout_dict = shout.dict()

                        if has_field(info, "created_by") and shout_dict.get("created_by"):
                            main_author_id = shout_dict.get("created_by")
                            a = session.query(Author).filter(Author.id == main_author_id).first()
                            shout_dict["created_by"] = {
                                "id": main_author_id,
                                "name": a.name,
                                "slug": a.slug,
                                "pic": a.pic,
                            }

                        if has_field(info, "stat"):
                            stat = {}
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
                            shout_dict["topics"] = topics

                        if has_field(info, "main_topic"):
                            main_topic = None
                            if hasattr(row, "main_topic"):
                                main_topic = (
                                    orjson.loads(row.main_topic) if isinstance(row.main_topic, str) else row.main_topic
                                )

                            if not main_topic and topics and len(topics) > 0:
                                main_topic = {
                                    "id": topics[0]["id"],
                                    "title": topics[0]["title"],
                                    "slug": topics[0]["slug"],
                                    "is_main": True,
                                }
                            elif not main_topic:
                                main_topic = {"id": 0, "title": "no topic", "slug": "notopic", "is_main": True}
                            shout_dict["main_topic"] = main_topic

                        if has_field(info, "authors") and hasattr(row, "authors"):
                            shout_dict["authors"] = (
                                orjson.loads(row.authors) if isinstance(row.authors, str) else row.authors
                            )

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
    finally:
        return shouts


def apply_filters(q, filters):
    """
    Применение общих фильтров к запросу.

    :param q: Исходный запрос.
    :param filters: Словарь фильтров.
    :return: Запрос с примененными фильтрами.
    """
    if isinstance(filters, dict):
        if "featured" in filters:
            featured_filter = filters.get("featured")
            if featured_filter:
                q = q.filter(Shout.featured_at.is_not(None))
            else:
                q = q.filter(Shout.featured_at.is_(None))
        by_layouts = filters.get("layouts")
        if by_layouts and isinstance(by_layouts, list):
            q = q.filter(Shout.layout.in_(by_layouts))
        by_author = filters.get("author")
        if by_author:
            q = q.filter(Shout.authors.any(slug=by_author))
        by_topic = filters.get("topic")
        if by_topic:
            q = q.filter(Shout.topics.any(slug=by_topic))
        by_after = filters.get("after")
        if by_after:
            ts = int(by_after)
            q = q.filter(Shout.created_at > ts)

    return q


@query.field("get_shout")
async def get_shout(_, info: GraphQLResolveInfo, slug="", shout_id=0):
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
        return shouts[0] if shouts else None

    except Exception as exc:
        logger.error(f"Error in get_shout: {exc}", exc_info=True)
        return None


def apply_sorting(q, options):
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
        q = q.distinct(Shout.published_at, Shout.id).order_by(Shout.published_at.desc(), Shout.id)

    return q


@query.field("load_shouts_by")
async def load_shouts_by(_, info: GraphQLResolveInfo, options):
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
async def load_shouts_search(_, info, text, options):
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
    
    if isinstance(text, str) and len(text) > 2:
        # Search in titles, bodies and combine results
        title_results = await search_title_text(text, limit * 2, 0)
        body_results = await search_body_text(text, limit * 2, 0)
        
        # Also get author search results if requested
        include_authors = options.get("include_authors", False)
        author_results = []
        if include_authors:
            author_results = await search_author_text(text, limit, 0)
            # Process author results differently if needed
        
        # Combine results and deduplicate by ID
        combined_results = {}
        
        # Process title results first (typically more relevant)
        for result in title_results:
            shout_id = result.get("id")
            if shout_id:
                combined_results[shout_id] = {
                    "id": shout_id,
                    "score": result.get("score", 0) * 1.2  # Slightly boost title matches
                }
        
        # Process body results, keeping higher scores if already present
        for result in body_results:
            shout_id = result.get("id")
            if shout_id:
                if shout_id in combined_results:
                    # Keep the higher score
                    combined_results[shout_id]["score"] = max(
                        combined_results[shout_id]["score"], 
                        result.get("score", 0)
                    )
                else:
                    combined_results[shout_id] = {
                        "id": shout_id,
                        "score": result.get("score", 0)
                    }
        
        # Convert to list and sort by score
        results = list(combined_results.values())
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # Apply pagination
        results = results[offset:offset+limit]
        
        # If no results, return empty list
        if not results:
            logger.info(f"No search results found for '{text}'")
            return []
        
        # Extract IDs and scores
        scores = {}
        hits_ids = []
        for sr in results:
            shout_id = sr.get("id")
            if shout_id:
                shout_id = str(shout_id)
                scores[shout_id] = sr.get("score")
                hits_ids.append(shout_id)

        # Query DB for only the IDs in the current page
        q = query_with_stat(info)
        q = q.filter(Shout.id.in_(hits_ids))
        q = apply_filters(q, options.get("filters", {}))

        shouts = get_shouts_with_links(info, q, len(hits_ids), 0)
        
        # Add scores from search results
        for shout in shouts:
            shout_id = str(shout['id'])
            shout["score"] = scores.get(shout_id, 0)

        # Re-sort by search score to maintain ranking
        shouts.sort(key=lambda x: scores.get(str(x['id']), 0), reverse=True)
        
        # Add author search results to the response if requested
        if include_authors and author_results:
            # Format author results according to your schema
            formatted_authors = []
            for author in author_results:
                formatted_authors.append({
                    "id": author.get("id"),
                    "name": author.get("name", ""),
                    "score": author.get("score", 0),
                    "bio": author.get("bio", "")
                })
            
            # Return combined results
            return {
                "shouts": shouts,
                "authors": formatted_authors
            }
        
        return shouts
    return []



@query.field("get_search_results_count")
async def get_search_results_count(_, info, text):
    """
    Returns the total count of search results for a search query.
    
    :param _: Root query object (unused)
    :param info: GraphQL context information
    :param text: Search query text
    :return: Total count of results
    """
    if isinstance(text, str) and len(text) > 2:
        # Get counts from both title and body searches
        body_count = await get_body_search_count(text)
        title_count = await get_title_search_count(text)
        author_count = await get_author_search_count(text)
        
        # Return combined counts
        return {
            "count": body_count + title_count,  # Total document count
            "details": {
                "body_count": body_count,
                "title_count": title_count,
                "author_count": author_count
            }
        }
    return {"count": 0, "details": {"body_count": 0, "title_count": 0, "author_count": 0}}


@query.field("load_shouts_unrated")
async def load_shouts_unrated(_, info, options):
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
                Reaction.deleted_at.is_(None), Reaction.kind.in_([ReactionKind.LIKE.value, ReactionKind.DISLIKE.value])
            )
        )
        .group_by(Reaction.shout)
        .having(func.count("*") >= 3)
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
async def load_shouts_random_top(_, info, options):
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
    q = q.filter(Shout.id.in_(subquery))
    q = q.order_by(func.random())
    limit = options.get("limit", 10)
    return get_shouts_with_links(info, q, limit)
