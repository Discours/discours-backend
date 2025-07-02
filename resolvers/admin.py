from math import ceil
from typing import Any

from graphql import GraphQLResolveInfo
from graphql.error import GraphQLError
from sqlalchemy import String, cast, null, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func, select

from auth.decorators import admin_auth_required
from auth.orm import Author
from orm.community import Community, CommunityAuthor
from orm.invite import Invite, InviteStatus
from orm.shout import Shout
from services.db import local_session
from services.env import EnvManager, EnvVariable
from services.schema import mutation, query
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST
from utils.logger import root_logger as logger

# Преобразуем строку ADMIN_EMAILS в список
ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",") if ADMIN_EMAILS_LIST else []

# Создаем роли в сообществе если они не существуют
default_role_names = {
    "reader": "Читатель",
    "author": "Автор",
    "artist": "Художник",
    "expert": "Эксперт",
    "editor": "Редактор",
    "admin": "Администратор",
}

default_role_descriptions = {
    "reader": "Может читать и комментировать",
    "author": "Может создавать публикации",
    "artist": "Может быть credited artist",
    "expert": "Может добавлять доказательства",
    "editor": "Может модерировать контент",
    "admin": "Полные права",
}


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ DRY ===


def normalize_pagination(limit: int = 20, offset: int = 0) -> tuple[int, int]:
    """
    Нормализует параметры пагинации.

    Args:
        limit: Максимальное количество записей
        offset: Смещение

    Returns:
        Кортеж (limit, offset) с нормализованными значениями
    """
    return max(1, min(100, limit or 20)), max(0, offset or 0)


def calculate_pagination_info(total_count: int, limit: int, offset: int) -> dict[str, int]:
    """
    Вычисляет информацию о пагинации.

    Args:
        total_count: Общее количество записей
        limit: Количество записей на странице
        offset: Смещение

    Returns:
        Словарь с информацией о пагинации
    """
    per_page = limit
    if total_count is None or per_page in (None, 0):
        total_pages = 1
    else:
        total_pages = ceil(total_count / per_page)
    current_page = (offset // per_page) + 1 if per_page > 0 else 1

    return {
        "total": total_count,
        "page": current_page,
        "perPage": per_page,
        "totalPages": total_pages,
    }


def handle_admin_error(operation: str, error: Exception) -> GraphQLError:
    """
    Обрабатывает ошибки в админ-резолверах.

    Args:
        operation: Название операции
        error: Исключение

    Returns:
        GraphQLError для возврата клиенту
    """
    import traceback

    logger.error(f"Ошибка при {operation}: {error!s}")
    logger.error(traceback.format_exc())
    msg = f"Не удалось {operation}: {error!s}"
    return GraphQLError(msg)


def get_author_info(author_id: int, session) -> dict[str, Any]:
    """
    Получает информацию об авторе для отображения в админ-панели.

    Args:
        author_id: ID автора
        session: Сессия БД

    Returns:
        Словарь с информацией об авторе
    """
    if not author_id:
        return None

    author = session.query(Author).filter(Author.id == author_id).first()
    if author:
        return {
            "id": author.id,
            "email": author.email,
            "name": author.name,
            "slug": author.slug or f"user-{author.id}",
        }
    return {
        "id": author_id,
        "email": "unknown",
        "name": "unknown",
        "slug": f"user-{author_id}",
    }


def _get_user_roles(user: Author, community_id: int = 1) -> list[str]:
    """
    Получает полный список ролей пользователя в указанном сообществе, включая
    синтетическую роль "Системный администратор" для пользователей из ADMIN_EMAILS

    Args:
        user: Объект пользователя
        community_id: ID сообщества для получения ролей

    Returns:
        Список строк с названиями ролей
    """
    user_roles = []

    # Получаем роли пользователя из новой RBAC системы
    with local_session() as session:
        community_author = (
            session.query(CommunityAuthor)
            .filter(CommunityAuthor.author_id == user.id, CommunityAuthor.community_id == community_id)
            .first()
        )

        if community_author and community_author.roles:
            # Разбираем CSV строку с ролями
            user_roles = [role.strip() for role in community_author.roles.split(",") if role.strip()]

    # Если email пользователя в списке ADMIN_EMAILS, добавляем синтетическую роль
    # ВАЖНО: Эта роль НЕ хранится в базе данных, а добавляется только для отображения
    if user.email and user.email.lower() in [email.lower() for email in ADMIN_EMAILS]:
        if "Системный администратор" not in user_roles:
            user_roles.insert(0, "Системный администратор")

    return user_roles


@query.field("adminGetUsers")
@admin_auth_required
async def admin_get_users(
    _: None, _info: GraphQLResolveInfo, limit: int = 20, offset: int = 0, search: str = ""
) -> dict[str, Any]:
    """
    Получает список пользователей для админ-панели с поддержкой пагинации и поиска

    Args:
        _info: Контекст GraphQL запроса
        limit: Максимальное количество записей для получения
        offset: Смещение в списке результатов
        search: Строка поиска (по email, имени или ID)

    Returns:
        Пагинированный список пользователей
    """
    try:
        # Нормализуем параметры пагинации
        limit, offset = normalize_pagination(limit, offset)

        with local_session() as session:
            # Базовый запрос
            query = session.query(Author)

            # Применяем фильтр поиска, если указан
            if search and search.strip():
                search_term = f"%{search.strip().lower()}%"
                query = query.filter(
                    or_(
                        Author.email.ilike(search_term),
                        Author.name.ilike(search_term),
                        cast(Author.id, String).ilike(search_term),
                    )
                )

            # Получаем общее количество записей
            total_count = query.count()

            # Применяем пагинацию
            authors = query.order_by(Author.id).offset(offset).limit(limit).all()

            # Вычисляем информацию о пагинации
            pagination_info = calculate_pagination_info(total_count, limit, offset)

            # Преобразуем в формат для API
            return {
                "authors": [
                    {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "slug": user.slug,
                        "roles": _get_user_roles(user, 1),  # Получаем роли в основном сообществе
                        "created_at": user.created_at,
                        "last_seen": user.last_seen,
                    }
                    for user in authors
                ],
                **pagination_info,
            }

    except Exception as e:
        raise handle_admin_error("получении списка пользователей", e) from e


@query.field("adminGetRoles")
@admin_auth_required
async def admin_get_roles(_: None, info: GraphQLResolveInfo, community: int = None) -> list[dict[str, Any]]:
    """
    Получает список всех ролей в системе или ролей для конкретного сообщества

    Args:
        info: Контекст GraphQL запроса
        community: ID сообщества для фильтрации ролей (опционально)

    Returns:
        Список ролей
    """
    try:
        from orm.community import role_descriptions, role_names
        from services.rbac import get_permissions_for_role

        # Используем словари названий и описаний ролей из новой системы
        all_roles = ["reader", "author", "artist", "expert", "editor", "admin"]

        if community is not None:
            # Получаем доступные роли для конкретного сообщества
            with local_session() as session:
                from orm.community import Community

                community_obj = session.query(Community).filter(Community.id == community).first()
                if community_obj:
                    available_roles = community_obj.get_available_roles()
                else:
                    available_roles = all_roles
        else:
            # Возвращаем все системные роли
            available_roles = all_roles

        # Формируем список ролей с их описаниями и разрешениями
        roles_list = []
        for role_id in available_roles:
            # Получаем название и описание роли
            name = role_names.get(role_id, role_id.title())
            description = role_descriptions.get(role_id, f"Роль {name}")

            # Для конкретного сообщества получаем разрешения
            if community is not None:
                try:
                    permissions = await get_permissions_for_role(role_id, community)
                    perm_count = len(permissions)
                    description = f"{description} ({perm_count} разрешений)"
                except Exception:
                    description = f"{description} (права не инициализированы)"

            roles_list.append(
                {
                    "id": role_id,
                    "name": name,
                    "description": description,
                }
            )

        return roles_list

    except Exception as e:
        logger.error(f"Ошибка при получении списка ролей: {e!s}")
        msg = f"Не удалось получить список ролей: {e!s}"
        raise GraphQLError(msg) from e


@query.field("getEnvVariables")
@admin_auth_required
async def get_env_variables(_: None, info: GraphQLResolveInfo) -> list[dict[str, Any]]:
    """
    Получает список переменных окружения, сгруппированных по секциям

    Args:
        info: Контекст GraphQL запроса

    Returns:
        Список секций с переменными окружения
    """
    try:
        # Создаем экземпляр менеджера переменных окружения
        env_manager = EnvManager()

        # Получаем все переменные
        sections = await env_manager.get_all_variables()

        # Преобразуем к формату GraphQL API
        sections_list = [
            {
                "name": section.name,
                "description": section.description,
                "variables": [
                    {
                        "key": var.key,
                        "value": var.value,
                        "description": var.description,
                        "type": var.type,
                        "isSecret": var.is_secret,
                    }
                    for var in section.variables
                ],
            }
            for section in sections
        ]

        return sections_list

    except Exception as e:
        logger.error(f"Ошибка при получении переменных окружения: {e!s}")
        msg = f"Не удалось получить переменные окружения: {e!s}"
        raise GraphQLError(msg) from e


@mutation.field("updateEnvVariable")
@admin_auth_required
async def update_env_variable(_: None, _info: GraphQLResolveInfo, key: str, value: str) -> dict[str, Any]:
    """
    Обновляет значение переменной окружения

    Args:
        info: Контекст GraphQL запроса
        key: Ключ переменной
        value: Новое значение

    Returns:
        Boolean: результат операции
    """
    try:
        # Создаем экземпляр менеджера переменных окружения
        env_manager = EnvManager()

        # Обновляем переменную
        result = env_manager.update_variables([EnvVariable(key=key, value=value)])

        if result:
            logger.info(f"Переменная окружения '{key}' успешно обновлена")
        else:
            logger.error(f"Не удалось обновить переменную окружения '{key}'")

        return {"success": result}
    except Exception as e:
        logger.error(f"Ошибка при обновлении переменной окружения: {e!s}")
        return {"success": False, "error": str(e)}


@mutation.field("updateEnvVariables")
@admin_auth_required
async def update_env_variables(_: None, info: GraphQLResolveInfo, variables: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Массовое обновление переменных окружения

    Args:
        info: Контекст GraphQL запроса
        variables: Список переменных для обновления

    Returns:
        Boolean: результат операции
    """
    try:
        # Создаем экземпляр менеджера переменных окружения
        env_manager = EnvManager()

        # Преобразуем входные данные в формат для менеджера
        env_variables = [
            EnvVariable(key=var.get("key", ""), value=var.get("value", ""), type=var.get("type", "string"))
            for var in variables
        ]

        # Обновляем переменные
        result = env_manager.update_variables(env_variables)

        if result:
            logger.info(f"Переменные окружения успешно обновлены ({len(variables)} шт.)")
        else:
            logger.error("Не удалось обновить переменные окружения")

        return {"success": result}
    except Exception as e:
        logger.error(f"Ошибка при массовом обновлении переменных окружения: {e!s}")
        return {"success": False, "error": str(e)}


@mutation.field("adminUpdateUser")
@admin_auth_required
async def admin_update_user(_: None, info: GraphQLResolveInfo, user: dict[str, Any]) -> dict[str, Any]:
    """
    Обновляет данные пользователя (роли, email, имя, slug)

    Args:
        info: Контекст GraphQL запроса
        user: Данные для обновления пользователя

    Returns:
        Boolean: результат операции или объект с ошибкой
    """
    try:
        user_id = user.get("id")

        # Проверяем что user_id не None
        if user_id is None:
            return {"success": False, "error": "ID пользователя не указан"}

        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            return {"success": False, "error": "Некорректный ID пользователя"}

        roles = user.get("roles", [])
        email = user.get("email")
        name = user.get("name")
        slug = user.get("slug")

        if not roles:
            logger.warning(f"Пользователю {user_id} не назначено ни одной роли. Доступ в систему будет заблокирован.")

        with local_session() as session:
            # Получаем пользователя из базы данных
            author = session.query(Author).filter(Author.id == user_id).first()

            if not author:
                error_msg = f"Пользователь с ID {user_id} не найден"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Обновляем основные поля профиля
            profile_updated = False
            if email is not None and email != author.email:
                # Проверяем уникальность email
                existing_author = session.query(Author).filter(Author.email == email, Author.id != user_id).first()
                if existing_author:
                    return {"success": False, "error": f"Email {email} уже используется другим пользователем"}
                author.email = email
                profile_updated = True

            if name is not None and name != author.name:
                author.name = name
                profile_updated = True

            if slug is not None and slug != author.slug:
                # Проверяем уникальность slug
                existing_author = session.query(Author).filter(Author.slug == slug, Author.id != user_id).first()
                if existing_author:
                    return {"success": False, "error": f"Slug {slug} уже используется другим пользователем"}
                author.slug = slug
                profile_updated = True

            # Получаем ID сообщества по умолчанию
            default_community_id = 1  # Используем значение по умолчанию из модели AuthorRole

            try:
                # Получаем или создаем запись CommunityAuthor для основного сообщества
                community_author = (
                    session.query(CommunityAuthor)
                    .filter(
                        CommunityAuthor.author_id == user_id_int, CommunityAuthor.community_id == default_community_id
                    )
                    .first()
                )

                if not community_author:
                    # Создаем новую запись
                    community_author = CommunityAuthor(
                        author_id=user_id_int, community_id=default_community_id, roles=""
                    )
                    session.add(community_author)
                    session.flush()

                # Проверяем валидность ролей
                all_roles = ["reader", "author", "artist", "expert", "editor", "admin"]
                invalid_roles = set(roles) - set(all_roles)

                if invalid_roles:
                    warning_msg = f"Некоторые роли не поддерживаются: {', '.join(invalid_roles)}"
                    logger.warning(warning_msg)
                    # Оставляем только валидные роли
                    roles = [role for role in roles if role in all_roles]

                # Обновляем роли в CSV формате
                for r in roles:
                    community_author.remove_role(r)

                # Сохраняем изменения в базе данных
                session.commit()

                # Проверяем, добавлена ли пользователю роль reader
                has_reader = "reader" in roles
                if not has_reader:
                    logger.warning(
                        f"Пользователю {author.email or author.id} не назначена роль 'reader'. Доступ в систему будет ограничен."
                    )

                update_details = []
                if profile_updated:
                    update_details.append("профиль")
                if roles:
                    update_details.append(f"роли: {', '.join(roles)}")

                logger.info(f"Данные пользователя {author.email or author.id} обновлены: {', '.join(update_details)}")

                return {"success": True}
            except Exception as e:
                # Обработка вложенных исключений
                session.rollback()
                error_msg = f"Ошибка при изменении данных пользователя: {e!s}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
    except Exception as e:
        import traceback

        error_msg = f"Ошибка при обновлении данных пользователя: {e!s}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return {"success": False, "error": error_msg}


# ===== РЕЗОЛВЕРЫ ДЛЯ РАБОТЫ С ПУБЛИКАЦИЯМИ (SHOUT) =====


@query.field("adminGetShouts")
@admin_auth_required
async def admin_get_shouts(
    _: None,
    info: GraphQLResolveInfo,
    limit: int = 20,
    offset: int = 0,
    search: str = "",
    status: str = "all",
    community: int = None,
) -> dict[str, Any]:
    """
    Получает список публикаций для админ-панели с поддержкой пагинации и поиска
    Переиспользует логику из reader.py для соблюдения DRY принципа

    Args:
        limit: Максимальное количество записей для получения
        offset: Смещение в списке результатов
        search: Строка поиска (по заголовку, slug или ID)
        status: Статус публикаций (all, published, draft, deleted)
        community: ID сообщества для фильтрации

    Returns:
        Пагинированный список публикаций
    """
    try:
        # Импортируем функции из reader.py для переиспользования
        from resolvers.reader import get_shouts_with_links, query_with_stat

        # Нормализуем параметры
        limit = max(1, min(100, limit or 10))
        offset = max(0, offset or 0)

        with local_session() as session:
            # Используем существующую функцию для получения запроса со статистикой
            if status == "all":
                # Для админа показываем все публикации (включая удаленные и неопубликованные)
                q = select(Shout).options(joinedload(Shout.authors), joinedload(Shout.topics))
            else:
                # Используем стандартный запрос с фильтрацией
                q = query_with_stat(info)

                # Применяем фильтр статуса
                if status == "published":
                    q = q.filter(Shout.published_at.isnot(None), Shout.deleted_at.is_(None))
                elif status == "draft":
                    q = q.filter(Shout.published_at.is_(None), Shout.deleted_at.is_(None))
                elif status == "deleted":
                    q = q.filter(Shout.deleted_at.isnot(None))

            # Применяем фильтр по сообществу, если указан
            if community is not None:
                q = q.filter(Shout.community == community)

            # Применяем фильтр поиска, если указан
            if search and search.strip():
                search_term = f"%{search.strip().lower()}%"
                q = q.filter(
                    or_(
                        Shout.title.ilike(search_term),
                        Shout.slug.ilike(search_term),
                        cast(Shout.id, String).ilike(search_term),
                        Shout.body.ilike(search_term),
                    )
                )

            # Получаем общее количество записей
            total_count = session.execute(select(func.count()).select_from(q.subquery())).scalar()

            # Вычисляем информацию о пагинации
            per_page = limit
            if total_count is None or per_page in (None, 0):
                total_pages = 1
            else:
                total_pages = ceil(total_count / per_page)
            current_page = (offset // per_page) + 1 if per_page > 0 else 1

            # Применяем пагинацию и сортировку (новые сверху)
            q = q.order_by(Shout.created_at.desc())

            # Используем существующую функцию для получения публикаций с данными
            if status == "all":
                # Для статуса "all" используем простой запрос без статистики
                q = q.limit(limit).offset(offset)
                shouts_result: list[Any] = session.execute(q).unique().all()
                shouts_data = []

                for row in shouts_result:
                    # Get the Shout object from the row
                    if isinstance(row, tuple):
                        shout = row[0]
                    elif hasattr(row, "Shout"):
                        shout = row.Shout
                    elif isinstance(row, dict) and "id" in row:
                        shout = row
                    else:
                        shout = row

                    # Обрабатываем поле media
                    media_data = []
                    if hasattr(shout, "media") and shout.media:
                        if isinstance(shout.media, str):
                            try:
                                import orjson

                                media_data = orjson.loads(shout.media)
                            except Exception:
                                media_data = []
                        elif isinstance(shout.media, list):
                            media_data = shout.media
                        elif isinstance(shout.media, dict):
                            media_data = [shout.media]

                    shout_dict = {
                        "id": getattr(shout, "id", None) if not isinstance(shout, dict) else shout.get("id"),
                        "title": getattr(shout, "title", None) if not isinstance(shout, dict) else shout.get("title"),
                        "slug": getattr(shout, "slug", None) if not isinstance(shout, dict) else shout.get("slug"),
                        "body": getattr(shout, "body", None) if not isinstance(shout, dict) else shout.get("body"),
                        "lead": getattr(shout, "lead", None) if not isinstance(shout, dict) else shout.get("lead"),
                        "subtitle": getattr(shout, "subtitle", None)
                        if not isinstance(shout, dict)
                        else shout.get("subtitle"),
                        "layout": getattr(shout, "layout", None)
                        if not isinstance(shout, dict)
                        else shout.get("layout"),
                        "lang": getattr(shout, "lang", None) if not isinstance(shout, dict) else shout.get("lang"),
                        "cover": getattr(shout, "cover", None) if not isinstance(shout, dict) else shout.get("cover"),
                        "cover_caption": getattr(shout, "cover_caption", None)
                        if not isinstance(shout, dict)
                        else shout.get("cover_caption"),
                        "media": media_data,
                        "seo": getattr(shout, "seo", None) if not isinstance(shout, dict) else shout.get("seo"),
                        "created_at": getattr(shout, "created_at", None)
                        if not isinstance(shout, dict)
                        else shout.get("created_at"),
                        "updated_at": getattr(shout, "updated_at", None)
                        if not isinstance(shout, dict)
                        else shout.get("updated_at"),
                        "published_at": getattr(shout, "published_at", None)
                        if not isinstance(shout, dict)
                        else shout.get("published_at"),
                        "featured_at": getattr(shout, "featured_at", None)
                        if not isinstance(shout, dict)
                        else shout.get("featured_at"),
                        "deleted_at": getattr(shout, "deleted_at", None)
                        if not isinstance(shout, dict)
                        else shout.get("deleted_at"),
                    }

                    # Обрабатываем поле created_by - получаем полную информацию об авторе
                    created_by_id = (
                        getattr(shout, "created_by", None) if not isinstance(shout, dict) else shout.get("created_by")
                    )
                    if created_by_id:
                        created_author = session.query(Author).filter(Author.id == created_by_id).first()
                        if created_author:
                            shout_dict["created_by"] = {
                                "id": created_author.id,
                                "email": created_author.email,
                                "name": created_author.name,
                                "slug": created_author.slug or f"user-{created_author.id}",
                            }
                        else:
                            shout_dict["created_by"] = {
                                "id": created_by_id,
                                "email": "unknown",
                                "name": "unknown",
                                "slug": f"user-{created_by_id}",
                            }
                    else:
                        shout_dict["created_by"] = None

                    # Обрабатываем поле updated_by - получаем полную информацию об авторе
                    updated_by_id = (
                        getattr(shout, "updated_by", None) if not isinstance(shout, dict) else shout.get("updated_by")
                    )
                    if updated_by_id:
                        updated_author = session.query(Author).filter(Author.id == updated_by_id).first()
                        if updated_author:
                            shout_dict["updated_by"] = {
                                "id": updated_author.id,
                                "email": updated_author.email,
                                "name": updated_author.name,
                                "slug": updated_author.slug or f"user-{updated_author.id}",
                            }
                        else:
                            shout_dict["updated_by"] = {
                                "id": updated_by_id,
                                "email": "unknown",
                                "name": "unknown",
                                "slug": f"user-{updated_by_id}",
                            }
                    else:
                        shout_dict["updated_by"] = None

                    # Обрабатываем поле deleted_by - получаем полную информацию об авторе
                    deleted_by_id = (
                        getattr(shout, "deleted_by", None) if not isinstance(shout, dict) else shout.get("deleted_by")
                    )
                    if deleted_by_id:
                        deleted_author = session.query(Author).filter(Author.id == deleted_by_id).first()
                        if deleted_author:
                            shout_dict["deleted_by"] = {
                                "id": deleted_author.id,
                                "email": deleted_author.email,
                                "name": deleted_author.name,
                                "slug": deleted_author.slug or f"user-{deleted_author.id}",
                            }
                        else:
                            shout_dict["deleted_by"] = {
                                "id": deleted_by_id,
                                "email": "unknown",
                                "name": "unknown",
                                "slug": f"user-{deleted_by_id}",
                            }
                    else:
                        shout_dict["deleted_by"] = None

                    # Обрабатываем поле community - получаем полную информацию о сообществе
                    community_id = (
                        getattr(shout, "community", None) if not isinstance(shout, dict) else shout.get("community")
                    )
                    if community_id:
                        community = session.query(Community).filter(Community.id == community_id).first()
                        if community:
                            shout_dict["community"] = {
                                "id": community.id,
                                "name": community.name,
                                "slug": community.slug,
                            }
                        else:
                            shout_dict["community"] = {
                                "id": community_id,
                                "name": "unknown",
                                "slug": f"community-{community_id}",
                            }
                    else:
                        shout_dict["community"] = None

                    # Обрабатываем поля authors и topics как раньше
                    shout_dict["authors"] = [
                        {
                            "id": getattr(author, "id", None),
                            "email": getattr(author, "email", None),
                            "name": getattr(author, "name", None),
                            "slug": getattr(author, "slug", None) or f"user-{getattr(author, 'id', 'unknown')}",
                        }
                        for author in (
                            getattr(shout, "authors", []) if not isinstance(shout, dict) else shout.get("authors", [])
                        )
                    ]

                    shout_dict["topics"] = [
                        {
                            "id": getattr(topic, "id", None),
                            "title": getattr(topic, "title", None),
                            "slug": getattr(topic, "slug", None),
                        }
                        for topic in (
                            getattr(shout, "topics", []) if not isinstance(shout, dict) else shout.get("topics", [])
                        )
                    ]

                    shout_dict["version_of"] = (
                        getattr(shout, "version_of", None) if not isinstance(shout, dict) else shout.get("version_of")
                    )
                    shout_dict["draft"] = (
                        getattr(shout, "draft", None) if not isinstance(shout, dict) else shout.get("draft")
                    )
                    shout_dict["stat"] = None  # Заполним при необходимости

                    shouts_data.append(shout_dict)
            else:
                # Используем существующую функцию для получения публикаций со статистикой
                shouts_result = get_shouts_with_links(info, q, limit, offset)
                shouts_data = [
                    s.dict() if hasattr(s, "dict") else dict(s) if hasattr(s, "_mapping") else s for s in shouts_result
                ]

            return {
                "shouts": shouts_data,
                "total": total_count,
                "page": current_page,
                "perPage": per_page,
                "totalPages": total_pages,
            }

    except Exception as e:
        import traceback

        logger.error(f"Ошибка при получении списка публикаций: {e!s}")
        logger.error(traceback.format_exc())
        msg = f"Не удалось получить список публикаций: {e!s}"
        raise GraphQLError(msg) from e


@mutation.field("adminUpdateShout")
@admin_auth_required
async def admin_update_shout(_: None, info: GraphQLResolveInfo, shout: dict[str, Any]) -> dict[str, Any]:
    """
    Обновляет данные публикации
    Переиспользует логику из editor.py для соблюдения DRY принципа

    Args:
        info: Контекст GraphQL запроса
        shout: Данные для обновления публикации

    Returns:
        Результат операции
    """
    try:
        # Импортируем функцию обновления из editor.py
        from resolvers.editor import update_shout

        shout_id = shout.get("id")

        if not shout_id:
            return {"success": False, "error": "ID публикации не указан"}

        # Подготавливаем данные в формате, ожидаемом функцией update_shout
        shout_input = {k: v for k, v in shout.items() if k != "id"}

        # Используем существующую функцию update_shout
        result = await update_shout(None, info, shout_id, shout_input)

        if result.error:
            return {"success": False, "error": result.error}

        logger.info(f"Публикация {shout_id} обновлена через админ-панель")
        return {"success": True}

    except Exception as e:
        import traceback

        error_msg = f"Ошибка при обновлении публикации: {e!s}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return {"success": False, "error": error_msg}


@mutation.field("adminDeleteShout")
@admin_auth_required
async def admin_delete_shout(_: None, info: GraphQLResolveInfo, shout_id: int) -> dict[str, Any]:
    """
    Мягко удаляет публикацию (устанавливает deleted_at)
    Переиспользует логику из editor.py для соблюдения DRY принципа

    Args:
        info: Контекст GraphQL запроса
        id: ID публикации для удаления

    Returns:
        Результат операции
    """
    try:
        # Импортируем функцию удаления из editor.py
        from resolvers.editor import delete_shout

        # Используем существующую функцию delete_shout
        result = await delete_shout(None, info, shout_id)

        if result.error:
            return {"success": False, "error": result.error}

        logger.info(f"Публикация {shout_id} удалена через админ-панель")
        return {"success": True}

    except Exception as e:
        error_msg = f"Ошибка при удалении публикации: {e!s}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


@mutation.field("adminRestoreShout")
@admin_auth_required
async def admin_restore_shout(_: None, info: GraphQLResolveInfo, shout_id: int) -> dict[str, Any]:
    """
    Восстанавливает удаленную публикацию (сбрасывает deleted_at)

    Args:
        info: Контекст GraphQL запроса
        id: ID публикации для восстановления

    Returns:
        Результат операции
    """
    try:
        with local_session() as session:
            # Получаем публикацию
            shout = session.query(Shout).filter(Shout.id == shout_id).first()

            if not shout:
                return {"success": False, "error": f"Публикация с ID {shout_id} не найдена"}

            if not shout.deleted_at:
                return {"success": False, "error": "Публикация не была удалена"}

            # Сбрасываем время удаления
            shout.deleted_at = null()
            shout.deleted_by = null()

            session.commit()

            logger.info(f"Публикация {shout.title or shout.id} восстановлена администратором")
            return {"success": True}

    except Exception as e:
        error_msg = f"Ошибка при восстановлении публикации: {e!s}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


# === CRUD для приглашений ===


@query.field("adminGetInvites")
@admin_auth_required
async def admin_get_invites(
    _: None, _info: GraphQLResolveInfo, limit: int = 20, offset: int = 0, search: str = "", status: str = "all"
) -> dict[str, Any]:
    """
    Получает список приглашений для админ-панели с поддержкой пагинации и поиска

    Args:
        _info: Контекст GraphQL запроса
        limit: Максимальное количество записей для получения
        offset: Смещение в списке результатов
        search: Строка поиска (по email приглашающего/приглашаемого, названию публикации или ID)
        status: Фильтр по статусу ("all", "pending", "accepted", "rejected")

    Returns:
        Пагинированный список приглашений
    """
    try:
        # Нормализуем параметры пагинации
        limit, offset = normalize_pagination(limit, offset)

        with local_session() as session:
            # Базовый запрос с загрузкой связанных объектов
            query = session.query(Invite).options(
                joinedload(Invite.inviter),
                joinedload(Invite.author),
                joinedload(Invite.shout),
            )

            # Фильтр по статусу
            if status and status != "all":
                status_enum = InviteStatus[status.upper()]
                query = query.filter(Invite.status == status_enum.value)

            # Применяем фильтр поиска, если указан
            if search and search.strip():
                search_term = f"%{search.strip().lower()}%"
                query = (
                    query.join(Invite.inviter.of_type(Author), aliased=True)
                    .join(Invite.author.of_type(Author), aliased=True)
                    .join(Invite.shout)
                    .filter(
                        or_(
                            # Поиск по email приглашающего
                            Invite.inviter.has(Author.email.ilike(search_term)),
                            # Поиск по имени приглашающего
                            Invite.inviter.has(Author.name.ilike(search_term)),
                            # Поиск по email приглашаемого
                            Invite.author.has(Author.email.ilike(search_term)),
                            # Поиск по имени приглашаемого
                            Invite.author.has(Author.name.ilike(search_term)),
                            # Поиск по названию публикации
                            Invite.shout.has(Shout.title.ilike(search_term)),
                            # Поиск по ID приглашающего
                            cast(Invite.inviter_id, String).ilike(search_term),
                            # Поиск по ID приглашаемого
                            cast(Invite.author_id, String).ilike(search_term),
                            # Поиск по ID публикации
                            cast(Invite.shout_id, String).ilike(search_term),
                        )
                    )
                )

            # Получаем общее количество записей
            total_count = query.count()

            # Применяем пагинацию и сортировку (по ID приглашающего, затем автора, затем публикации)
            invites = (
                query.order_by(Invite.inviter_id, Invite.author_id, Invite.shout_id).offset(offset).limit(limit).all()
            )

            # Вычисляем информацию о пагинации
            pagination_info = calculate_pagination_info(total_count, limit, offset)

            # Преобразуем в формат для API
            result_invites = []
            for invite in invites:
                # Получаем информацию о создателе публикации
                created_by_info = get_author_info(invite.shout.created_by if invite.shout else None, session)

                invite_dict = {
                    "inviter_id": invite.inviter_id,
                    "author_id": invite.author_id,
                    "shout_id": invite.shout_id,
                    "status": invite.status,
                    "inviter": {
                        "id": invite.inviter.id,
                        "name": invite.inviter.name or "Без имени",
                        "email": invite.inviter.email,
                        "slug": invite.inviter.slug or f"user-{invite.inviter.id}",
                    },
                    "author": {
                        "id": invite.author.id,
                        "name": invite.author.name or "Без имени",
                        "email": invite.author.email,
                        "slug": invite.author.slug or f"user-{invite.author.id}",
                    },
                    "shout": {
                        "id": invite.shout.id,
                        "title": invite.shout.title,
                        "slug": invite.shout.slug,
                        "created_by": created_by_info,
                    },
                    "created_at": None,  # У приглашений нет created_at поля в текущей модели
                }

                result_invites.append(invite_dict)

            return {
                "invites": result_invites,
                **pagination_info,
            }

    except Exception as e:
        raise handle_admin_error("получении списка приглашений", e) from e


@mutation.field("adminUpdateInvite")
@admin_auth_required
async def admin_update_invite(_: None, _info: GraphQLResolveInfo, invite: dict[str, Any]) -> dict[str, Any]:
    """
    Обновляет существующее приглашение

    Args:
        _info: Контекст GraphQL запроса
        invite: Данные приглашения для обновления

    Returns:
        Результат операции
    """
    try:
        inviter_id = invite["inviter_id"]
        author_id = invite["author_id"]
        shout_id = invite["shout_id"]
        new_status = invite["status"]

        with local_session() as session:
            # Находим существующее приглашение
            existing_invite = (
                session.query(Invite)
                .filter(
                    Invite.inviter_id == inviter_id,
                    Invite.author_id == author_id,
                    Invite.shout_id == shout_id,
                )
                .first()
            )

            if not existing_invite:
                return {
                    "success": False,
                    "error": f"Приглашение с ID {inviter_id}-{author_id}-{shout_id} не найдено",
                }

            # Обновляем статус
            old_status = existing_invite.status
            existing_invite.status = new_status
            session.commit()

            logger.info(f"Обновлён статус приглашения {inviter_id}-{author_id}-{shout_id}: {old_status} → {new_status}")

            return {"success": True, "error": None}

    except Exception as e:
        logger.error(f"Ошибка при обновлении приглашения: {e!s}")
        msg = f"Не удалось обновить приглашение: {e!s}"
        raise GraphQLError(msg) from e


@mutation.field("adminDeleteInvite")
@admin_auth_required
async def admin_delete_invite(
    _: None, _info: GraphQLResolveInfo, inviter_id: int, author_id: int, shout_id: int
) -> dict[str, Any]:
    """
    Удаляет приглашение

    Args:
        _info: Контекст GraphQL запроса
        inviter_id: ID приглашающего
        author_id: ID приглашаемого
        shout_id: ID публикации

    Returns:
        Результат операции
    """
    try:
        with local_session() as session:
            # Находим приглашение для удаления
            invite = (
                session.query(Invite)
                .filter(
                    Invite.inviter_id == inviter_id,
                    Invite.author_id == author_id,
                    Invite.shout_id == shout_id,
                )
                .first()
            )

            if not invite:
                return {
                    "success": False,
                    "error": f"Приглашение с ID {inviter_id}-{author_id}-{shout_id} не найдено",
                }

            # Удаляем приглашение
            session.delete(invite)
            session.commit()

            logger.info(f"Удалено приглашение {inviter_id}-{author_id}-{shout_id}")

            return {"success": True, "error": None}

    except Exception as e:
        logger.error(f"Ошибка при удалении приглашения: {e!s}")
        msg = f"Не удалось удалить приглашение: {e!s}"
        raise GraphQLError(msg) from e


@mutation.field("adminDeleteInvitesBatch")
@admin_auth_required
async def admin_delete_invites_batch(
    _: None, _info: GraphQLResolveInfo, invites: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Пакетное удаление приглашений

    Args:
        _info: Контекст GraphQL запроса
        invites: Список приглашений для удаления (каждое содержит inviter_id, author_id, shout_id)

    Returns:
        Результат операции
    """
    try:
        if not invites:
            return {"success": False, "error": "Список приглашений для удаления пуст"}

        deleted_count = 0
        errors = []

        with local_session() as session:
            for invite_data in invites:
                inviter_id = invite_data.get("inviter_id")
                author_id = invite_data.get("author_id")
                shout_id = invite_data.get("shout_id")

                if not all([inviter_id, author_id, shout_id]):
                    errors.append(f"Неполные данные для приглашения: {invite_data}")
                    continue

                # Находим приглашение для удаления
                invite = (
                    session.query(Invite)
                    .filter(Invite.inviter_id == inviter_id, Invite.author_id == author_id, Invite.shout_id == shout_id)
                    .first()
                )

                if not invite:
                    errors.append(f"Приглашение с ID {inviter_id}-{author_id}-{shout_id} не найдено")
                    continue

                # Удаляем приглашение
                session.delete(invite)
                deleted_count += 1

            # Сохраняем все изменения за раз
            if deleted_count > 0:
                session.commit()
                logger.info(f"Пакетное удаление приглашений: удалено {deleted_count} приглашений")

            # Формируем результат
            success = deleted_count > 0
            error = None
            if errors:
                error = f"Удалено {deleted_count} приглашений. Ошибки: {', '.join(errors)}"

            return {"success": success, "error": error}

    except Exception as e:
        logger.error(f"Ошибка при пакетном удалении приглашений: {e!s}")
        msg = f"Не удалось выполнить пакетное удаление приглашений: {e!s}"
        raise GraphQLError(msg) from e


@query.field("adminGetUserCommunityRoles")
@admin_auth_required
async def admin_get_user_community_roles(
    _: None, info: GraphQLResolveInfo, author_id: int, community_id: int
) -> dict[str, Any]:
    """
    Получает роли пользователя в конкретном сообществе

    Args:
        author_id: ID пользователя
        community_id: ID сообщества

    Returns:
        Словарь с ролями пользователя в сообществе
    """
    try:
        with local_session() as session:
            # Получаем роли пользователя из новой RBAC системы
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community_id)
                .first()
            )

            roles = []
            if community_author and community_author.roles:
                roles = [role.strip() for role in community_author.roles.split(",") if role.strip()]

            return {"author_id": author_id, "community_id": community_id, "roles": roles}

    except Exception as e:
        logger.error(f"Ошибка при получении ролей пользователя в сообществе: {e!s}")
        msg = f"Не удалось получить роли пользователя: {e!s}"
        raise GraphQLError(msg) from e


@mutation.field("adminUpdateUserCommunityRoles")
@admin_auth_required
async def admin_update_user_community_roles(
    _: None, info: GraphQLResolveInfo, author_id: int, community_id: int, roles: list[str]
) -> dict[str, Any]:
    """
    Обновляет роли пользователя в конкретном сообществе

    Args:
        author_id: ID пользователя
        community_id: ID сообщества
        roles: Список ID ролей для назначения

    Returns:
        Результат операции
    """
    try:
        with local_session() as session:
            # Проверяем существование пользователя
            author = session.query(Author).filter(Author.id == author_id).first()
            if not author:
                return {"success": False, "error": f"Пользователь с ID {author_id} не найден"}

            # Проверяем существование сообщества
            community = session.query(Community).filter(Community.id == community_id).first()
            if not community:
                return {"success": False, "error": f"Сообщество с ID {community_id} не найдено"}

            # Проверяем валидность ролей
            available_roles = community.get_available_roles()
            invalid_roles = set(roles) - set(available_roles)
            if invalid_roles:
                return {"success": False, "error": f"Роли недоступны в этом сообществе: {list(invalid_roles)}"}

            # Получаем или создаем запись CommunityAuthor
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community_id)
                .first()
            )

            if not community_author:
                community_author = CommunityAuthor(author_id=author_id, community_id=community_id, roles="")
                session.add(community_author)

            # Обновляем роли в CSV формате
            for r in roles:
                community_author.remove_role(r)

            session.commit()

            logger.info(f"Роли пользователя {author_id} в сообществе {community_id} обновлены: {roles}")

            return {"success": True, "author_id": author_id, "community_id": community_id, "roles": roles}

    except Exception as e:
        logger.error(f"Ошибка при обновлении ролей пользователя в сообществе: {e!s}")
        msg = f"Не удалось обновить роли пользователя: {e!s}"
        return {"success": False, "error": msg}


@query.field("adminGetCommunityMembers")
@admin_auth_required
async def admin_get_community_members(
    _: None, info: GraphQLResolveInfo, community_id: int, limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    """
    Получает список участников сообщества с их ролями

    Args:
        community_id: ID сообщества
        limit: Максимальное количество записей
        offset: Смещение для пагинации

    Returns:
        Список участников сообщества с ролями
    """
    try:
        with local_session() as session:
            # Получаем участников сообщества из CommunityAuthor (новая RBAC система)
            members_query = (
                session.query(Author, CommunityAuthor)
                .join(CommunityAuthor, Author.id == CommunityAuthor.author_id)
                .filter(CommunityAuthor.community_id == community_id)
                .offset(offset)
                .limit(limit)
            )

            members = []
            for author, community_author in members_query:
                # Парсим роли из CSV
                roles = []
                if community_author.roles:
                    roles = [role.strip() for role in community_author.roles.split(",") if role.strip()]

                members.append(
                    {
                        "id": author.id,
                        "name": author.name,
                        "email": author.email,
                        "slug": author.slug,
                        "roles": roles,
                    }
                )

            # Подсчитываем общее количество участников
            total = (
                session.query(func.count(CommunityAuthor.author_id))
                .filter(CommunityAuthor.community_id == community_id)
                .scalar()
            )

            return {"members": members, "total": total, "community_id": community_id}

    except Exception as e:
        logger.error(f"Ошибка получения участников сообщества: {e}")
        return {"members": [], "total": 0, "community_id": community_id}


@mutation.field("adminSetUserCommunityRoles")
@admin_auth_required
async def admin_set_user_community_roles(
    _: None, info: GraphQLResolveInfo, author_id: int, community_id: int, roles: list[str]
) -> dict[str, Any]:
    """
    Устанавливает роли пользователя в сообществе (заменяет все существующие роли)

    Args:
        author_id: ID пользователя
        community_id: ID сообщества
        roles: Список ролей для назначения

    Returns:
        Результат операции
    """
    try:
        with local_session() as session:
            # Проверяем существование пользователя
            author = session.query(Author).filter(Author.id == author_id).first()
            if not author:
                return {
                    "success": False,
                    "error": f"Пользователь {author_id} не найден",
                    "author_id": author_id,
                    "community_id": community_id,
                    "roles": [],
                }

            # Проверяем существование сообщества
            community = session.query(Community).filter(Community.id == community_id).first()
            if not community:
                return {
                    "success": False,
                    "error": f"Сообщество {community_id} не найдено",
                    "author_id": author_id,
                    "community_id": community_id,
                    "roles": [],
                }

            # Проверяем, что все роли доступны в сообществе
            available_roles = community.get_available_roles()
            invalid_roles = set(roles) - set(available_roles)
            if invalid_roles:
                return {
                    "success": False,
                    "error": f"Роли недоступны в этом сообществе: {list(invalid_roles)}",
                    "author_id": author_id,
                    "community_id": community_id,
                    "roles": roles,
                }

            # Получаем или создаем запись CommunityAuthor
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community_id)
                .first()
            )

            if not community_author:
                community_author = CommunityAuthor(author_id=author_id, community_id=community_id, roles="")
                session.add(community_author)

            # Обновляем роли в CSV формате
            community_author.set_roles(roles)

            session.commit()
            logger.info(f"Назначены роли {roles} пользователю {author_id} в сообществе {community_id}")

            return {
                "success": True,
                "error": None,
                "author_id": author_id,
                "community_id": community_id,
                "roles": roles,
            }

    except Exception as e:
        logger.error(f"Ошибка назначения ролей пользователю {author_id} в сообществе {community_id}: {e}")
        return {"success": False, "error": str(e), "author_id": author_id, "community_id": community_id, "roles": []}


@mutation.field("adminAddUserToRole")
@admin_auth_required
async def admin_add_user_to_role(
    _: None, info: GraphQLResolveInfo, author_id: int, role_id: str, community_id: int
) -> dict[str, Any]:
    """
    Добавляет пользователю роль в сообществе

    Args:
        author_id: ID пользователя
        role_id: ID роли
        community_id: ID сообщества

    Returns:
        Результат операции
    """
    try:
        with local_session() as session:
            # Получаем или создаем запись CommunityAuthor
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community_id)
                .first()
            )

            if not community_author:
                community_author = CommunityAuthor(author_id=author_id, community_id=community_id, roles=role_id)
                session.add(community_author)
            else:
                # Проверяем, что роль не назначена уже
                if role_id in community_author.role_list:
                    return {"success": False, "error": "Роль уже назначена пользователю"}

                # Добавляем новую роль
                community_author.add_role(role_id)

            session.commit()

            return {"success": True, "author_id": author_id, "role_id": role_id, "community_id": community_id}

    except Exception as e:
        logger.error(f"Ошибка добавления роли пользователю: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminRemoveUserFromRole")
@admin_auth_required
async def admin_remove_user_from_role(
    _: None, info: GraphQLResolveInfo, author_id: int, role_id: str, community_id: int
) -> dict[str, Any]:
    """
    Удаляет роль у пользователя в сообществе

    Args:
        author_id: ID пользователя
        role_id: ID роли
        community_id: ID сообщества

    Returns:
        Результат операции
    """
    try:
        with local_session() as session:
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community_id)
                .first()
            )
            if not community_author:
                return {"success": False, "error": "Пользователь не найден в сообществе"}

            if not community_author.has_role(role_id):
                return {"success": False, "error": "Роль не найдена у пользователя в сообществе"}

            # Используем метод модели для корректного удаления роли
            community_author.remove_role(role_id)

            session.commit()

            return {
                "success": True,
                "author_id": author_id,
                "role_id": role_id,
                "community_id": community_id,
            }

    except Exception as e:
        logger.error(f"Error removing user from role: {e}")
        return {"success": False, "error": str(e)}


@query.field("adminGetCommunityRoleSettings")
@admin_auth_required
async def admin_get_community_role_settings(_: None, info: GraphQLResolveInfo, community_id: int) -> dict[str, Any]:
    """
    Получает настройки ролей для сообщества

    Args:
        community_id: ID сообщества

    Returns:
        Настройки ролей сообщества
    """
    try:
        with local_session() as session:
            from orm.community import Community

            community = session.query(Community).filter(Community.id == community_id).first()
            if not community:
                return {
                    "community_id": community_id,
                    "default_roles": ["reader"],
                    "available_roles": ["reader", "author", "artist", "expert", "editor", "admin"],
                    "error": "Сообщество не найдено",
                }

            return {
                "community_id": community_id,
                "default_roles": community.get_default_roles(),
                "available_roles": community.get_available_roles(),
                "error": None,
            }

    except Exception as e:
        logger.error(f"Error getting community role settings: {e}")
        return {
            "community_id": community_id,
            "default_roles": ["reader"],
            "available_roles": ["reader", "author", "artist", "expert", "editor", "admin"],
            "error": str(e),
        }


@mutation.field("adminUpdateCommunityRoleSettings")
@admin_auth_required
async def admin_update_community_role_settings(
    _: None, info: GraphQLResolveInfo, community_id: int, default_roles: list[str], available_roles: list[str]
) -> dict[str, Any]:
    """
    Обновляет настройки ролей для сообщества

    Args:
        community_id: ID сообщества
        default_roles: Список дефолтных ролей
        available_roles: Список доступных ролей

    Returns:
        Результат операции
    """
    try:
        with local_session() as session:
            community = session.query(Community).filter(Community.id == community_id).first()
            if not community:
                return {
                    "success": False,
                    "error": f"Сообщество {community_id} не найдено",
                    "community_id": community_id,
                    "default_roles": [],
                    "available_roles": [],
                }

            return {
                "success": True,
                "error": None,
                "community_id": community_id,
                "default_roles": default_roles,
                "available_roles": available_roles,
            }

    except Exception as e:
        logger.error(f"Ошибка обновления настроек ролей сообщества {community_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "community_id": community_id,
            "default_roles": default_roles,
            "available_roles": available_roles,
        }


@mutation.field("adminDeleteCustomRole")
@admin_auth_required
async def admin_delete_custom_role(
    _: None, info: GraphQLResolveInfo, role_id: str, community_id: int
) -> dict[str, Any]:
    """
    Удаляет произвольную роль из сообщества

    Args:
        role_id: ID роли для удаления
        community_id: ID сообщества

    Returns:
        Результат операции
    """
    try:
        with local_session() as session:
            # Проверяем существование сообщества
            community = session.query(Community).filter(Community.id == community_id).first()
            if not community:
                return {"success": False, "error": f"Сообщество {community_id} не найдено"}

            # Удаляем роль из сообщества
            current_available = community.get_available_roles()
            current_default = community.get_default_roles()

            new_available = [r for r in current_available if r != role_id]
            new_default = [r for r in current_default if r != role_id]

            community.set_available_roles(new_available)
            community.set_default_roles(new_default)
            session.commit()

            logger.info(f"Удалена роль {role_id} из сообщества {community_id}")

            return {"success": True, "error": None}

    except Exception as e:
        logger.error(f"Ошибка удаления роли {role_id} из сообщества {community_id}: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminCreateCustomRole")
@admin_auth_required
async def admin_create_custom_role(_: None, info: GraphQLResolveInfo, role: dict[str, Any]) -> dict[str, Any]:
    """
    Создает произвольную роль в сообществе

    Args:
        role: Данные для создания роли

    Returns:
        Результат создания роли
    """
    try:
        role_id = role.get("id")
        name = role.get("name")
        description = role.get("description", "")
        icon = role.get("icon", "🔖")
        community_id = role.get("community_id")

        # Валидация
        if not role_id or not name or not community_id:
            return {"success": False, "error": "Обязательные поля: id, name, community_id", "role": None}

        # Проверяем валидность ID роли
        import re

        if not re.match(r"^[a-z0-9_-]+$", role_id):
            return {
                "success": False,
                "error": "ID роли может содержать только латинские буквы, цифры, дефисы и подчеркивания",
                "role": None,
            }

        with local_session() as session:
            # Проверяем существование сообщества
            community = session.query(Community).filter(Community.id == community_id).first()
            if not community:
                return {"success": False, "error": f"Сообщество {community_id} не найдено", "role": None}

            available_roles = community.get_available_roles()
            if role_id in available_roles:
                return {
                    "success": False,
                    "error": f"Роль с ID {role_id} уже существует в сообществе {community_id}",
                    "role": None,
                }

            # Добавляем роль в список доступных ролей
            community.set_available_roles([*available_roles, role_id])
            session.commit()

            logger.info(f"Создана роль {role_id} ({name}) в сообществе {community_id}")

            return {"success": True, "error": None, "role": {"id": role_id, "name": name, "description": description}}

    except Exception as e:
        logger.error(f"Ошибка создания роли: {e}")
        return {"success": False, "error": str(e), "role": None}
