import asyncio
import sys
import traceback
from typing import Any, Optional

from sqlalchemy import and_, distinct, func, join, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import Select

from auth.orm import Author, AuthorFollower
from orm.community import Community, CommunityFollower
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic, TopicFollower
from services.db import local_session
from utils.logger import root_logger as logger

# Type alias for queries
QueryType = Select


def add_topic_stat_columns(q: QueryType) -> QueryType:
    """
    Добавляет статистические колонки к запросу тем.

    :param q: SQL-запрос для получения тем.
    :return: Запрос с добавленными колонками статистики.
    """
    # Создаем алиасы для предотвращения конфликтов имен
    aliased_shout = aliased(ShoutTopic)

    # Создаем новый объект запроса для тем
    new_q = select(Topic)

    # Применяем необходимые фильтры и добавляем колонки статистики
    new_q = (
        new_q.join(
            aliased_shout,
            aliased_shout.topic == Topic.id,
        )
        .join(
            Shout,
            and_(
                aliased_shout.shout == Shout.id,
                Shout.deleted_at.is_(None),
            ),
        )
        .add_columns(
            func.count(distinct(aliased_shout.shout)).label("shouts_stat")
        )  # Подсчет уникальных публикаций для темы
    )

    aliased_follower = aliased(TopicFollower)

    # Добавляем количество подписчиков темы
    new_q = new_q.outerjoin(aliased_follower, aliased_follower.topic == Topic.id).add_columns(
        func.count(distinct(aliased_follower.follower)).label("followers_stat")
    )

    # Группировка по идентификатору темы
    return new_q.group_by(Topic.id)


def add_author_stat_columns(q: QueryType) -> QueryType:
    """
    Добавляет статистические колонки к запросу авторов.

    :param q: SQL-запрос для получения авторов.
    :return: Запрос с добавленными колонками статистики.
    """
    # Подзапрос для подсчета публикаций
    shouts_subq = (
        select(func.count(distinct(Shout.id)))
        .select_from(ShoutAuthor)
        .join(Shout, and_(Shout.id == ShoutAuthor.shout, Shout.deleted_at.is_(None)))
        .where(ShoutAuthor.author == Author.id)
        .scalar_subquery()
    )

    # Подзапрос для подсчета подписчиков
    followers_subq = (
        select(func.count(distinct(AuthorFollower.follower)))
        .where(AuthorFollower.author == Author.id)
        .scalar_subquery()
    )

    # Основной запрос
    return (
        q.select_from(Author)
        .add_columns(shouts_subq.label("shouts_stat"), followers_subq.label("followers_stat"))
        .group_by(Author.id)
    )


def get_topic_shouts_stat(topic_id: int) -> int:
    """
    Получает количество опубликованных постов для темы
    """
    q = (
        select(func.count(distinct(ShoutTopic.shout)))
        .select_from(join(ShoutTopic, Shout, ShoutTopic.shout == Shout.id))
        .where(
            and_(
                ShoutTopic.topic == topic_id,
                Shout.published_at.is_not(None),
                Shout.deleted_at.is_(None),
            )
        )
    )

    with local_session() as session:
        result = session.execute(q).scalar()
        return int(result) if result else 0


def get_topic_authors_stat(topic_id: int) -> int:
    """
    Получает количество уникальных авторов для указанной темы.

    :param topic_id: Идентификатор темы.
    :return: Количество уникальных авторов, связанных с темой.
    """
    count_query = (
        select(func.count(distinct(ShoutAuthor.author)))
        .select_from(join(ShoutTopic, Shout, ShoutTopic.shout == Shout.id))
        .join(ShoutAuthor, ShoutAuthor.shout == Shout.id)
        .where(
            and_(
                ShoutTopic.topic == topic_id,
                Shout.published_at.is_not(None),
                Shout.deleted_at.is_(None),
            )
        )
    )

    # Выполнение запроса и получение результата
    with local_session() as session:
        result = session.execute(count_query).scalar()
        return int(result) if result else 0


def get_topic_followers_stat(topic_id: int) -> int:
    """
    Получает количество подписчиков для указанной темы.

    :param topic_id: Идентификатор темы.
    :return: Количество уникальных подписчиков темы.
    """
    aliased_followers = aliased(TopicFollower)
    q = select(func.count(distinct(aliased_followers.follower))).where(aliased_followers.topic == topic_id)
    with local_session() as session:
        result = session.execute(q).scalar()
        return int(result) if result else 0


def get_topic_comments_stat(topic_id: int) -> int:
    """
    Получает количество комментариев для всех публикаций в указанной теме.

    :param topic_id: Идентификатор темы.
    :return: Общее количество комментариев к публикациям темы.
    """
    # Подзапрос для получения количества комментариев для каждой публикации
    sub_comments = (
        select(
            Shout.id.label("shout_id"),
            func.coalesce(func.count(Reaction.id), 0).label("comments_count"),
        )
        .join(ShoutTopic, ShoutTopic.shout == Shout.id)
        .join(Topic, ShoutTopic.topic == Topic.id)
        .outerjoin(
            Reaction,
            and_(
                Reaction.shout == Shout.id,
                Reaction.kind == ReactionKind.COMMENT.value,
                Reaction.deleted_at.is_(None),
            ),
        )
        .group_by(Shout.id)
        .subquery()
    )
    # Запрос для суммирования количества комментариев по теме
    q = select(func.coalesce(func.sum(sub_comments.c.comments_count), 0)).where(ShoutTopic.topic == topic_id)
    q = q.outerjoin(sub_comments, ShoutTopic.shout == sub_comments.c.shout_id)
    with local_session() as session:
        result = session.execute(q).scalar()
        return int(result) if result else 0


def get_author_shouts_stat(author_id: int) -> int:
    """
    Получает количество опубликованных постов для автора
    """
    aliased_shout_author = aliased(ShoutAuthor)
    aliased_shout = aliased(Shout)

    q = (
        select(func.count(distinct(aliased_shout.id)))
        .select_from(aliased_shout)
        .join(aliased_shout_author, aliased_shout.id == aliased_shout_author.shout)
        .where(
            and_(
                aliased_shout_author.author == author_id,
                aliased_shout.published_at.is_not(None),
                aliased_shout.deleted_at.is_(None),
            )
        )
    )

    with local_session() as session:
        result = session.execute(q).scalar()
        return int(result) if result else 0


def get_author_authors_stat(author_id: int) -> int:
    """
    Получает количество уникальных авторов, с которыми взаимодействовал указанный автор
    """
    q = (
        select(func.count(distinct(ShoutAuthor.author)))
        .select_from(ShoutAuthor)
        .join(Shout, ShoutAuthor.shout == Shout.id)
        .join(Reaction, Reaction.shout == Shout.id)
        .where(
            and_(
                Reaction.created_by == author_id,
                Shout.published_at.is_not(None),
                Shout.deleted_at.is_(None),
                Reaction.deleted_at.is_(None),
            )
        )
    )

    with local_session() as session:
        result = session.execute(q).scalar()
        return int(result) if result else 0


def get_author_followers_stat(author_id: int) -> int:
    """
    Получает количество подписчиков для указанного автора
    """
    q = select(func.count(AuthorFollower.follower)).where(AuthorFollower.author == author_id)

    with local_session() as session:
        result = session.execute(q).scalar()
        return int(result) if result else 0


def get_author_comments_stat(author_id: int) -> int:
    q = (
        select(func.coalesce(func.count(Reaction.id), 0).label("comments_count"))
        .select_from(Author)
        .outerjoin(
            Reaction,
            and_(
                Reaction.created_by == Author.id,
                Reaction.kind == ReactionKind.COMMENT.value,
                Reaction.deleted_at.is_(None),
            ),
        )
        .where(Author.id == author_id)
        .group_by(Author.id)
    )

    with local_session() as session:
        result = session.execute(q).scalar()
        if result and hasattr(result, "comments_count"):
            return int(result.comments_count)
        return 0


def get_with_stat(q: QueryType) -> list[Any]:
    """
    Выполняет запрос с добавлением статистики.

    :param q: SQL-запрос для выполнения.
    :return: Список объектов с добавленной статистикой.
    """
    records = []
    try:
        with local_session() as session:
            # Определяем, является ли запрос запросом авторов
            author_prefixes = ("select author", "select * from author")
            is_author = f"{q}".lower().startswith(author_prefixes)

            # Добавляем колонки статистики в запрос
            q = add_author_stat_columns(q) if is_author else add_topic_stat_columns(q)

            # Выполняем запрос
            result = session.execute(q).unique()
            for cols in result:
                entity = cols[0]
                stat = {}
                stat["shouts"] = cols[1]  # Статистика по публикациям
                stat["followers"] = cols[2]  # Статистика по подписчикам
                if is_author:
                    # Дополнительная проверка типа entity.id
                    if not hasattr(entity, "id"):
                        logger.error(f"Entity does not have id attribute: {entity}")
                        continue
                    entity_id = entity.id
                    if not isinstance(entity_id, int):
                        logger.error(f"Entity id is not integer: {entity_id} (type: {type(entity_id)})")
                        continue

                    stat["authors"] = get_author_authors_stat(entity_id)  # Статистика по подпискам на авторов
                    stat["comments"] = get_author_comments_stat(entity_id)  # Статистика по комментариям
                else:
                    # Дополнительная проверка типа entity.id для тем
                    if not hasattr(entity, "id"):
                        logger.error(f"Entity does not have id attribute: {entity}")
                        continue
                    entity_id = entity.id
                    if not isinstance(entity_id, int):
                        logger.error(f"Entity id is not integer: {entity_id} (type: {type(entity_id)})")
                        continue

                    stat["authors"] = get_topic_authors_stat(entity_id)  # Статистика по авторам темы
                entity.stat = stat
                records.append(entity)
    except Exception as exc:
        logger.debug(q)
        traceback.print_exc()
        logger.error(exc, exc_info=True)
    return records


def author_follows_authors(author_id: int) -> list[Any]:
    """
    Получает список авторов, на которых подписан указанный автор.

    :param author_id: Идентификатор автора.
    :return: Список авторов с добавленной статистикой.
    """
    af = aliased(AuthorFollower, name="af")
    author_follows_authors_query = (
        select(Author).select_from(join(Author, af, Author.id == af.author)).where(af.follower == author_id)
    )
    return get_with_stat(author_follows_authors_query)


def author_follows_topics(author_id: int) -> list[Any]:
    """
    Получает список тем, на которые подписан указанный автор.

    :param author_id: Идентификатор автора.
    :return: Список тем с добавленной статистикой.
    """
    author_follows_topics_query = (
        select(Topic)
        .select_from(join(Topic, TopicFollower, Topic.id == TopicFollower.topic))
        .where(TopicFollower.follower == author_id)
    )
    return get_with_stat(author_follows_topics_query)


def update_author_stat(author_id: int) -> None:
    """
    Обновляет статистику для указанного автора и сохраняет её в кэше.

    :param author_id: Идентификатор автора.
    """
    # Поздний импорт для избежания циклических зависимостей
    from cache.cache import cache_author

    author_query = select(Author).where(Author.id == author_id)
    try:
        result = get_with_stat(author_query)
        if result:
            author_with_stat = result[0]
            if isinstance(author_with_stat, Author):
                author_dict = author_with_stat.dict()
                # Асинхронное кэширование данных автора
                task = asyncio.create_task(cache_author(author_dict))
                # Store task reference to prevent garbage collection
                if not hasattr(update_author_stat, "stat_tasks"):
                    update_author_stat.stat_tasks = set()  # type: ignore[attr-defined]
                update_author_stat.stat_tasks.add(task)  # type: ignore[attr-defined]
                task.add_done_callback(update_author_stat.stat_tasks.discard)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.error(exc, exc_info=True)


def get_followers_count(entity_type: str, entity_id: int) -> int:
    """Получает количество подписчиков для сущности"""
    try:
        with local_session() as session:
            if entity_type == "topic":
                result = (
                    session.query(func.count(TopicFollower.follower)).where(TopicFollower.topic == entity_id).scalar()
                )
            elif entity_type == "author":
                # Count followers of this author
                result = (
                    session.query(func.count(AuthorFollower.follower))
                    .where(AuthorFollower.author == entity_id)
                    .scalar()
                )
            elif entity_type == "community":
                result = (
                    session.query(func.count(CommunityFollower.follower))
                    .where(CommunityFollower.community == entity_id)
                    .scalar()
                )
            else:
                return 0

            return int(result) if result else 0
    except Exception as e:
        logger.error(f"Error getting followers count: {e}")
        return 0


def get_following_count(entity_type: str, entity_id: int) -> int:
    """Получает количество подписок сущности"""
    try:
        with local_session() as session:
            if entity_type == "author":
                # Count what this author follows
                topic_follows = (
                    session.query(func.count(TopicFollower.topic)).where(TopicFollower.follower == entity_id).scalar()
                    or 0
                )
                community_follows = (
                    session.query(func.count(CommunityFollower.community))
                    .where(CommunityFollower.follower == entity_id)
                    .scalar()
                    or 0
                )
                return int(topic_follows) + int(community_follows)
            return 0
    except Exception as e:
        logger.error(f"Error getting following count: {e}")
        return 0


def get_shouts_count(
    author_id: Optional[int] = None, topic_id: Optional[int] = None, community_id: Optional[int] = None
) -> int:
    """Получает количество публикаций"""
    try:
        with local_session() as session:
            query = session.query(func.count(Shout.id)).where(Shout.published_at.isnot(None))

            if author_id:
                query = query.where(Shout.created_by == author_id)
            if topic_id:
                # This would need ShoutTopic association table
                pass
            if community_id:
                query = query.where(Shout.community == community_id)

            result = query.scalar()
            return int(result) if result else 0
    except Exception as e:
        logger.error(f"Error getting shouts count: {e}")
        return 0


def get_authors_count(community_id: Optional[int] = None) -> int:
    """Получает количество авторов"""
    try:
        with local_session() as session:
            if community_id:
                # Count authors in specific community
                result = (
                    session.query(func.count(distinct(CommunityFollower.follower)))
                    .where(CommunityFollower.community == community_id)
                    .scalar()
                )
            else:
                # Count all authors
                result = session.query(func.count(Author.id)).where(Author.deleted_at.is_(None)).scalar()

            return int(result) if result else 0
    except Exception as e:
        logger.error(f"Error getting authors count: {e}")
        return 0


def get_topics_count(author_id: Optional[int] = None) -> int:
    """Получает количество топиков"""
    try:
        with local_session() as session:
            if author_id:
                # Count topics followed by author
                result = (
                    session.query(func.count(TopicFollower.topic)).where(TopicFollower.follower == author_id).scalar()
                )
            else:
                # Count all topics
                result = session.query(func.count(Topic.id)).scalar()

            return int(result) if result else 0
    except Exception as e:
        logger.error(f"Error getting topics count: {e}")
        return 0


def get_communities_count() -> int:
    """Получает количество сообществ"""
    try:
        with local_session() as session:
            result = session.query(func.count(Community.id)).scalar()
            return int(result) if result else 0
    except Exception as e:
        logger.error(f"Error getting communities count: {e}")
        return 0


def get_reactions_count(shout_id: Optional[int] = None, author_id: Optional[int] = None) -> int:
    """Получает количество реакций"""
    try:
        with local_session() as session:
            query = session.query(func.count(Reaction.id))

            if shout_id:
                query = query.where(Reaction.shout == shout_id)
            if author_id:
                query = query.where(Reaction.created_by == author_id)

            result = query.scalar()
            return int(result) if result else 0
    except Exception as e:
        logger.error(f"Error getting reactions count: {e}")
        return 0


def get_comments_count_by_shout(shout_id: int) -> int:
    """Получает количество комментариев к статье"""
    try:
        with local_session() as session:
            # Using text() to access 'kind' column which might be enum
            result = (
                session.query(func.count(Reaction.id))
                .where(
                    and_(
                        Reaction.shout == shout_id,
                        Reaction.kind == "comment",  # Assuming 'comment' is a valid enum value
                    )
                )
                .scalar()
            )

            return int(result) if result else 0
    except Exception as e:
        logger.error(f"Error getting comments count: {e}")
        return 0


async def get_stat_background_task() -> None:
    """Фоновая задача для обновления статистики"""
    try:
        if not hasattr(sys.modules[__name__], "stat_tasks"):
            sys.modules[__name__].stat_tasks = set()  # type: ignore[attr-defined]

        # Perform background statistics calculations
        logger.info("Running background statistics update")

        # Here you would implement actual background statistics updates
        # This is just a placeholder

    except Exception as e:
        logger.error(f"Error in background statistics task: {e}")
