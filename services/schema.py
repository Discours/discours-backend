from asyncio.log import logger
from enum import Enum

from ariadne import (
    MutationType,
    ObjectType,
    QueryType,
    SchemaBindable,
    graphql,
    load_schema_from_path,
    make_executable_schema,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from auth.middleware import CSRF_HEADER_NAME, CSRF_TOKEN_KEY
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
    from auth.orm import Author, AuthorBookmark, AuthorFollower, AuthorRating
    from orm import collection, community, draft, invite, notification, reaction, shout, topic

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
                create_table_if_not_exists(session.get_bind(), model)
                # logger.info(f"Created or verified table: {model.__tablename__}")
            except Exception as e:
                table_name = getattr(model, "__tablename__", str(model))
                logger.error(f"Error creating table {table_name}: {e}")
                raise


async def graphql_handler(request: Request) -> Response:
    """
    Обработчик GraphQL запросов с проверкой CSRF токена
    """
    try:
        # Проверяем CSRF токен для всех мутаций
        data = await request.json()
        op_name = data.get("operationName", "").lower()

        # Проверяем CSRF только для мутаций
        if op_name and (op_name.endswith("mutation") or op_name in ["login", "refreshtoken"]):
            # Получаем токен из заголовка
            request_csrf_token = request.headers.get(CSRF_HEADER_NAME)

            # Получаем токен из куки
            cookie_csrf_token = request.cookies.get(CSRF_TOKEN_KEY)

            # Строгая проверка токена
            if not request_csrf_token or not cookie_csrf_token:
                # Возвращаем ошибку как часть GraphQL-ответа
                return JSONResponse(
                    {
                        "data": None,
                        "errors": [{"message": "CSRF токен отсутствует", "extensions": {"code": "CSRF_TOKEN_MISSING"}}],
                    }
                )

            if request_csrf_token != cookie_csrf_token:
                # Возвращаем ошибку как часть GraphQL-ответа
                return JSONResponse(
                    {
                        "data": None,
                        "errors": [
                            {"message": "Недопустимый CSRF токен", "extensions": {"code": "CSRF_TOKEN_INVALID"}}
                        ],
                    }
                )

        # Существующая логика обработки GraphQL запроса
        schema = get_schema()
        result = await graphql(
            schema,
            data.get("query"),
            variable_values=data.get("variables"),
            operation_name=data.get("operationName"),
            context_value={"request": request},
        )

        # Обработка ошибок GraphQL
        if result.errors:
            return JSONResponse(
                {
                    "data": result.data,
                    "errors": [{"message": str(error), "locations": error.locations} for error in result.errors],
                }
            )

        return JSONResponse({"data": result.data})

    except Exception as e:
        logger.error(f"GraphQL handler error: {e}")
        return JSONResponse(
            {
                "data": None,
                "errors": [{"message": "Внутренняя ошибка сервера", "extensions": {"code": "INTERNAL_SERVER_ERROR"}}],
            }
        )


def get_schema():
    """
    Создает и возвращает GraphQL схему
    """
    return make_executable_schema(type_defs, resolvers)
