from typing import Any

from graphql import GraphQLResolveInfo

from auth.decorators import editor_or_admin_required
from auth.orm import Author
from orm.collection import Collection, ShoutCollection
from services.db import local_session
from services.schema import mutation, query, type_collection


@query.field("get_collections_all")
async def get_collections_all(_: None, _info: GraphQLResolveInfo) -> list[Collection]:
    """Получает все коллекции"""
    from sqlalchemy.orm import joinedload

    with local_session() as session:
        # Загружаем коллекции с проверкой существования авторов
        collections = (
            session.query(Collection)
            .options(joinedload(Collection.created_by_author))
            .join(
                Author,
                Collection.created_by == Author.id,  # INNER JOIN - исключает коллекции без авторов
            )
            .filter(
                Collection.created_by.isnot(None),  # Дополнительная проверка
                Author.id.isnot(None),  # Проверяем что автор существует
            )
            .all()
        )

        # Дополнительная проверка валидности данных
        valid_collections = []
        for collection in collections:
            if (
                collection.created_by
                and hasattr(collection, "created_by_author")
                and collection.created_by_author
                and collection.created_by_author.id
            ):
                valid_collections.append(collection)
            else:
                from utils.logger import root_logger as logger

                logger.warning(f"Исключена коллекция {collection.id} ({collection.slug}) - проблемы с автором")

        return valid_collections


@query.field("get_collection")
async def get_collection(_: None, _info: GraphQLResolveInfo, slug: str) -> Collection | None:
    """Получает коллекцию по slug"""
    q = local_session().query(Collection).where(Collection.slug == slug)
    return q.first()


@query.field("get_collections_by_author")
async def get_collections_by_author(
    _: None, _info: GraphQLResolveInfo, slug: str = "", user: str = "", author_id: int = 0
) -> list[Collection]:
    """Получает коллекции автора"""
    with local_session() as session:
        q = session.query(Collection)

        if slug:
            author = session.query(Author).where(Author.slug == slug).first()
            if author:
                q = q.where(Collection.created_by == author.id)
        elif user:
            author = session.query(Author).where(Author.id == user).first()
            if author:
                q = q.where(Collection.created_by == author.id)
        elif author_id:
            q = q.where(Collection.created_by == author_id)

        return q.all()


@mutation.field("create_collection")
@editor_or_admin_required
async def create_collection(_: None, info: GraphQLResolveInfo, collection_input: dict[str, Any]) -> dict[str, Any]:
    """Создает новую коллекцию"""
    # Получаем author_id из контекста через декоратор авторизации
    request = info.context.get("request")
    author_id = None

    if hasattr(request, "auth") and request.auth and hasattr(request.auth, "author_id"):
        author_id = request.auth.author_id
    elif hasattr(request, "scope") and "auth" in request.scope:
        auth_info = request.scope.get("auth", {})
        if isinstance(auth_info, dict):
            author_id = auth_info.get("author_id")
        elif hasattr(auth_info, "author_id"):
            author_id = auth_info.author_id

    if not author_id:
        return {"error": "Не удалось определить автора"}

    try:
        with local_session() as session:
            # Исключаем created_by из входных данных - он всегда из токена
            filtered_input = {k: v for k, v in collection_input.items() if k != "created_by"}

            # Создаем новую коллекцию с обязательным created_by из токена
            new_collection = Collection(created_by=author_id, **filtered_input)
            session.add(new_collection)
            session.commit()
            return {"error": None}
    except Exception as e:
        return {"error": f"Ошибка создания коллекции: {e!s}"}


@mutation.field("update_collection")
@editor_or_admin_required
async def update_collection(_: None, info: GraphQLResolveInfo, collection_input: dict[str, Any]) -> dict[str, Any]:
    """Обновляет существующую коллекцию"""
    # Получаем author_id из контекста через декоратор авторизации
    request = info.context.get("request")
    author_id = None

    if hasattr(request, "auth") and request.auth and hasattr(request.auth, "author_id"):
        author_id = request.auth.author_id
    elif hasattr(request, "scope") and "auth" in request.scope:
        auth_info = request.scope.get("auth", {})
        if isinstance(auth_info, dict):
            author_id = auth_info.get("author_id")
        elif hasattr(auth_info, "author_id"):
            author_id = auth_info.author_id

    if not author_id:
        return {"error": "Не удалось определить автора"}

    slug = collection_input.get("slug")
    if not slug:
        return {"error": "Не указан slug коллекции"}

    try:
        with local_session() as session:
            # Находим коллекцию для обновления
            collection = session.query(Collection).filter(Collection.slug == slug).first()
            if not collection:
                return {"error": "Коллекция не найдена"}

            # Проверяем права на редактирование (создатель или админ/редактор)
            with local_session() as auth_session:
                author = auth_session.query(Author).filter(Author.id == author_id).first()
                user_roles = [role.id for role in author.roles] if author and author.roles else []

                # Разрешаем редактирование если пользователь - создатель или имеет роль admin/editor
                if collection.created_by != author_id and "admin" not in user_roles and "editor" not in user_roles:
                    return {"error": "Недостаточно прав для редактирования этой коллекции"}

            # Обновляем поля коллекции
            for key, value in collection_input.items():
                # Исключаем изменение created_by - создатель не может быть изменен
                if hasattr(collection, key) and key not in ["slug", "created_by"]:
                    setattr(collection, key, value)

            session.commit()
            return {"error": None}
    except Exception as e:
        return {"error": f"Ошибка обновления коллекции: {e!s}"}


@mutation.field("delete_collection")
@editor_or_admin_required
async def delete_collection(_: None, info: GraphQLResolveInfo, slug: str) -> dict[str, Any]:
    """Удаляет коллекцию"""
    # Получаем author_id из контекста через декоратор авторизации
    request = info.context.get("request")
    author_id = None

    if hasattr(request, "auth") and request.auth and hasattr(request.auth, "author_id"):
        author_id = request.auth.author_id
    elif hasattr(request, "scope") and "auth" in request.scope:
        auth_info = request.scope.get("auth", {})
        if isinstance(auth_info, dict):
            author_id = auth_info.get("author_id")
        elif hasattr(auth_info, "author_id"):
            author_id = auth_info.author_id

    if not author_id:
        return {"error": "Не удалось определить автора"}

    try:
        with local_session() as session:
            # Находим коллекцию для удаления
            collection = session.query(Collection).filter(Collection.slug == slug).first()
            if not collection:
                return {"error": "Коллекция не найдена"}

            # Проверяем права на удаление (создатель или админ/редактор)
            with local_session() as auth_session:
                author = auth_session.query(Author).filter(Author.id == author_id).first()
                user_roles = [role.id for role in author.roles] if author and author.roles else []

                # Разрешаем удаление если пользователь - создатель или имеет роль admin/editor
                if collection.created_by != author_id and "admin" not in user_roles and "editor" not in user_roles:
                    return {"error": "Недостаточно прав для удаления этой коллекции"}

            # Удаляем связи с публикациями
            session.query(ShoutCollection).filter(ShoutCollection.collection == collection.id).delete()

            # Удаляем коллекцию
            session.delete(collection)
            session.commit()
            return {"error": None}
    except Exception as e:
        return {"error": f"Ошибка удаления коллекции: {e!s}"}


@type_collection.field("created_by")
def resolve_collection_created_by(obj: Collection, *_: Any) -> Author:
    """Резолвер для поля created_by коллекции"""
    with local_session() as session:
        if hasattr(obj, "created_by_author") and obj.created_by_author:
            return obj.created_by_author

        author = session.query(Author).filter(Author.id == obj.created_by).first()
        if not author:
            from utils.logger import root_logger as logger

            logger.warning(f"Автор с ID {obj.created_by} не найден для коллекции {obj.id}")

        return author


@type_collection.field("amount")
def resolve_collection_amount(obj: Collection, *_: Any) -> int:
    """Резолвер для количества публикаций в коллекции"""
    with local_session() as session:
        count = session.query(ShoutCollection).filter(ShoutCollection.collection == obj.id).count()
        return count
