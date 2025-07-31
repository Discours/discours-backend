from asyncio.log import logger
from enum import Enum

from ariadne import (
    MutationType,
    ObjectType,
    QueryType,
    SchemaBindable,
    load_schema_from_path,
)

from auth.orm import Author, AuthorBookmark, AuthorFollower, AuthorRating
from orm import collection, community, draft, invite, notification, reaction, shout, topic
from services.db import create_table_if_not_exists, local_session

# Создаем основные типы
query = QueryType()
mutation = MutationType()
type_draft = ObjectType("Draft")
type_community = ObjectType("Community")
type_collection = ObjectType("Collection")
type_author = ObjectType("Author")

# Загружаем определения типов из файлов схемы
type_defs = load_schema_from_path("schema/")

# Список всех типов для схемы
resolvers: SchemaBindable | type[Enum] | list[SchemaBindable | type[Enum]] = [
    query,
    mutation,
    type_draft,
    type_community,
    type_collection,
    type_author,
]


def create_all_tables() -> None:
    """Create all database tables in the correct order."""
    # Порядок важен - сначала таблицы без внешних ключей, затем зависимые таблицы
    models_in_order = [
        # user.User,  # Базовая таблица auth
        Author,  # Базовая таблица
        community.Community,  # Базовая таблица
        topic.Topic,  # Базовая таблица
        # Связи для базовых таблиц
        AuthorFollower,  # Зависит от Author
        community.CommunityFollower,  # Зависит от Community
        topic.TopicFollower,  # Зависит от Topic
        # Черновики (теперь без зависимости от Shout)
        draft.Draft,  # Зависит только от Author
        draft.DraftAuthor,  # Зависит от Draft и Author
        draft.DraftTopic,  # Зависит от Draft и Topic
        # Основные таблицы контента
        shout.Shout,  # Зависит от Author и Draft
        shout.ShoutAuthor,  # Зависит от Shout и Author
        shout.ShoutTopic,  # Зависит от Shout и Topic
        # Реакции
        reaction.Reaction,  # Зависит от Author и Shout
        shout.ShoutReactionsFollower,  # Зависит от Shout и Reaction
        # Дополнительные таблицы
        AuthorRating,  # Зависит от Author
        AuthorBookmark,  # Зависит от Author
        notification.Notification,  # Зависит от Author
        notification.NotificationSeen,  # Зависит от Notification
        collection.Collection,  # Зависит от Author
        collection.ShoutCollection,  # Зависит от Collection и Shout
        invite.Invite,  # Зависит от Author и Shout
    ]

    with local_session() as session:
        for model in models_in_order:
            try:
                # Ensure model is a type[DeclarativeBase]
                if not hasattr(model, "__tablename__"):
                    logger.warning(f"Skipping {model} - not a DeclarativeBase model")
                    continue

                create_table_if_not_exists(session.get_bind(), model)  # type: ignore[arg-type]
                # logger.info(f"Created or verified table: {model.__tablename__}")
            except Exception as e:
                table_name = getattr(model, "__tablename__", str(model))
                logger.error(f"Error creating table {table_name}: {e}")
                raise
