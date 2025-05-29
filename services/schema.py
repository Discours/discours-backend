from asyncio.log import logger

from ariadne import MutationType, ObjectType, QueryType

from services.db import create_table_if_not_exists, local_session

query = QueryType()
mutation = MutationType()
type_draft = ObjectType("Draft")
resolvers = [query, mutation, type_draft]


def create_all_tables():
    """Create all database tables in the correct order."""
    from auth.orm import Author, AuthorBookmark, AuthorFollower, AuthorRating
    from orm import community, draft, notification, reaction, shout, topic

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
        # collection.Collection,
        # collection.ShoutCollection,
        # invite.Invite
    ]

    with local_session() as session:
        for model in models_in_order:
            try:
                create_table_if_not_exists(session.get_bind(), model)
                # logger.info(f"Created or verified table: {model.__tablename__}")
            except Exception as e:
                logger.error(f"Error creating table {model.__tablename__}: {e}")
                raise
