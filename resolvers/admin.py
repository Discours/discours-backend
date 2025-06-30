from math import ceil
from typing import Any

from graphql import GraphQLResolveInfo
from graphql.error import GraphQLError
from sqlalchemy import String, cast, null, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func, select

from auth.decorators import admin_auth_required
from auth.orm import Author, AuthorRole, Role
from orm.invite import Invite, InviteStatus
from orm.shout import Shout
from services.db import local_session
from services.env import EnvManager, EnvVariable
from services.schema import mutation, query
from utils.logger import root_logger as logger


@query.field("adminGetUsers")
@admin_auth_required
async def admin_get_users(
    _: None, _info: GraphQLResolveInfo, limit: int = 10, offset: int = 0, search: str = ""
) -> dict[str, Any]:
    """
    Получает список пользователей для админ-панели с поддержкой пагинации и поиска

    Args:
        info: Контекст GraphQL запроса
        limit: Максимальное количество записей для получения
        offset: Смещение в списке результатов
        search: Строка поиска (по email, имени или ID)

    Returns:
        Пагинированный список пользователей
    """
    try:
        # Нормализуем параметры
        limit = max(1, min(100, limit or 10))  # Ограничиваем количество записей от 1 до 100
        offset = max(0, offset or 0)  # Смещение не может быть отрицательным

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

            # Вычисляем информацию о пагинации
            per_page = limit
            if total_count is None or per_page in (None, 0):
                total_pages = 1
            else:
                total_pages = ceil(total_count / per_page)
            current_page = (offset // per_page) + 1 if per_page > 0 else 1

            # Применяем пагинацию
            authors = query.order_by(Author.id).offset(offset).limit(limit).all()

            # Преобразуем в формат для API
            return {
                "authors": [
                    {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "slug": user.slug,
                        "roles": [role.id for role in user.roles] if hasattr(user, "roles") and user.roles else [],
                        "created_at": user.created_at,
                        "last_seen": user.last_seen,
                    }
                    for user in authors
                ],
                "total": total_count,
                "page": current_page,
                "perPage": per_page,
                "totalPages": total_pages,
            }

    except Exception as e:
        import traceback

        logger.error(f"Ошибка при получении списка пользователей: {e!s}")
        logger.error(traceback.format_exc())
        msg = f"Не удалось получить список пользователей: {e!s}"
        raise GraphQLError(msg) from e


@query.field("adminGetRoles")
@admin_auth_required
async def admin_get_roles(_: None, info: GraphQLResolveInfo) -> list[dict[str, Any]]:
    """
    Получает список всех ролей в системе

    Args:
        info: Контекст GraphQL запроса

    Returns:
        Список ролей
    """
    try:
        with local_session() as session:
            # Загружаем роли с их разрешениями
            roles = session.query(Role).options(joinedload(Role.permissions)).all()

            # Преобразуем их в формат для API
            return [
                {
                    "id": role.id,
                    "name": role.name,
                    "description": f"Роль с правами: {', '.join(p.resource + ':' + p.operation for p in role.permissions)}"
                    if role.permissions
                    else "Роль без особых прав",
                }
                for role in roles
            ]

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
                # Очищаем текущие роли пользователя через ORM
                session.query(AuthorRole).filter(AuthorRole.author == user_id).delete()
                session.flush()

                # Получаем все существующие роли, которые указаны для обновления
                role_objects = session.query(Role).filter(Role.id.in_(roles)).all()

                # Проверяем, все ли запрошенные роли найдены
                found_role_ids = [str(role.id) for role in role_objects]
                missing_roles = set(roles) - set(found_role_ids)

                if missing_roles:
                    warning_msg = f"Некоторые роли не найдены в базе: {', '.join(missing_roles)}"
                    logger.warning(warning_msg)

                # Создаем новые записи в таблице author_role с указанием community
                for role in role_objects:
                    # Используем ORM для создания новых записей
                    author_role = AuthorRole(community=default_community_id, author=user_id, role=role.id)
                    session.add(author_role)

                # Сохраняем изменения в базе данных
                session.commit()

                # Проверяем, добавлена ли пользователю роль reader
                has_reader = "reader" in [str(role.id) for role in role_objects]
                if not has_reader:
                    logger.warning(
                        f"Пользователю {author.email or author.id} не назначена роль 'reader'. Доступ в систему будет ограничен."
                    )

                update_details = []
                if profile_updated:
                    update_details.append("профиль")
                if roles:
                    update_details.append(f"роли: {', '.join(found_role_ids)}")

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
    _: None, info: GraphQLResolveInfo, limit: int = 10, offset: int = 0, search: str = "", status: str = "all"
) -> dict[str, Any]:
    """
    Получает список публикаций для админ-панели с поддержкой пагинации и поиска
    Переиспользует логику из reader.py для соблюдения DRY принципа

    Args:
        limit: Максимальное количество записей для получения
        offset: Смещение в списке результатов
        search: Строка поиска (по заголовку, slug или ID)
        status: Статус публикаций (all, published, draft, deleted)

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
                        "created_by": {
                            "id": getattr(shout, "created_by", None)
                            if not isinstance(shout, dict)
                            else shout.get("created_by"),
                            "email": "unknown",  # Заполним при необходимости
                            "name": "unknown",
                        },
                        "updated_by": None,  # Заполним при необходимости
                        "deleted_by": None,  # Заполним при необходимости
                        "community": {
                            "id": getattr(shout, "community", None)
                            if not isinstance(shout, dict)
                            else shout.get("community"),
                            "name": "unknown",  # Заполним при необходимости
                        },
                        "authors": [
                            {
                                "id": getattr(author, "id", None),
                                "email": getattr(author, "email", None),
                                "name": getattr(author, "name", None),
                                "slug": getattr(author, "slug", None),
                            }
                            for author in (
                                getattr(shout, "authors", [])
                                if not isinstance(shout, dict)
                                else shout.get("authors", [])
                            )
                        ],
                        "topics": [
                            {
                                "id": getattr(topic, "id", None),
                                "title": getattr(topic, "title", None),
                                "slug": getattr(topic, "slug", None),
                            }
                            for topic in (
                                getattr(shout, "topics", []) if not isinstance(shout, dict) else shout.get("topics", [])
                            )
                        ],
                        "version_of": getattr(shout, "version_of", None)
                        if not isinstance(shout, dict)
                        else shout.get("version_of"),
                        "draft": getattr(shout, "draft", None) if not isinstance(shout, dict) else shout.get("draft"),
                        "stat": None,  # Заполним при необходимости
                    }
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
    _: None, _info: GraphQLResolveInfo, limit: int = 10, offset: int = 0, search: str = "", status: str = "all"
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
        # Нормализуем параметры
        limit = max(1, min(100, limit or 10))
        offset = max(0, offset or 0)

        with local_session() as session:
            # Базовый запрос с загрузкой связанных объектов
            query = session.query(Invite).options(
                joinedload(Invite.inviter),
                joinedload(Invite.author),
                joinedload(Invite.shout).joinedload(Shout.created_by_author),
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

            # Вычисляем информацию о пагинации
            per_page = limit
            if total_count is None or per_page in (None, 0):
                total_pages = 1
            else:
                total_pages = ceil(total_count / per_page)
            current_page = (offset // per_page) + 1 if per_page > 0 else 1

            # Применяем пагинацию и сортировку (по ID приглашающего, затем автора, затем публикации)
            invites = (
                query.order_by(Invite.inviter_id, Invite.author_id, Invite.shout_id).offset(offset).limit(limit).all()
            )

            # Преобразуем в формат для API
            return {
                "invites": [
                    {
                        "inviter_id": invite.inviter_id,
                        "author_id": invite.author_id,
                        "shout_id": invite.shout_id,
                        "status": invite.status,
                        "inviter": {
                            "id": invite.inviter.id,
                            "name": invite.inviter.name or "Без имени",
                            "email": invite.inviter.email,
                            "slug": invite.inviter.slug
                            or f"user-{invite.inviter.id}",  # Добавляем значение по умолчанию
                        },
                        "author": {
                            "id": invite.author.id,
                            "name": invite.author.name or "Без имени",
                            "email": invite.author.email,
                            "slug": invite.author.slug or f"user-{invite.author.id}",  # Добавляем значение по умолчанию
                        },
                        "shout": {
                            "id": invite.shout.id,
                            "title": invite.shout.title,
                            "slug": invite.shout.slug,
                            "created_by": {
                                "id": invite.shout.created_by_author.id,
                                "name": invite.shout.created_by_author.name or "Без имени",
                                "email": invite.shout.created_by_author.email,
                                "slug": invite.shout.created_by_author.slug
                                or f"user-{invite.shout.created_by_author.id}",  # Добавляем значение по умолчанию
                            },
                        },
                        "created_at": None,  # У приглашений нет created_at поля в текущей модели
                    }
                    for invite in invites
                ],
                "total": total_count,
                "page": current_page,
                "perPage": per_page,
                "totalPages": total_pages,
            }

    except Exception as e:
        import traceback

        logger.error(f"Ошибка при получении списка приглашений: {e!s}")
        logger.error(traceback.format_exc())
        msg = f"Не удалось получить список приглашений: {e!s}"
        raise GraphQLError(msg) from e


@mutation.field("adminCreateInvite")
@admin_auth_required
async def admin_create_invite(_: None, _info: GraphQLResolveInfo, invite: dict[str, Any]) -> dict[str, Any]:
    """
    Создает новое приглашение

    Args:
        _info: Контекст GraphQL запроса
        invite: Данные приглашения

    Returns:
        Результат операции
    """
    try:
        inviter_id = invite["inviter_id"]
        author_id = invite["author_id"]
        shout_id = invite["shout_id"]
        status = invite["status"]

        with local_session() as session:
            # Проверяем существование всех связанных объектов
            inviter = session.query(Author).filter(Author.id == inviter_id).first()
            if not inviter:
                return {"success": False, "error": f"Приглашающий автор с ID {inviter_id} не найден"}

            author = session.query(Author).filter(Author.id == author_id).first()
            if not author:
                return {"success": False, "error": f"Приглашаемый автор с ID {author_id} не найден"}

            shout = session.query(Shout).filter(Shout.id == shout_id).first()
            if not shout:
                return {"success": False, "error": f"Публикация с ID {shout_id} не найдена"}

            # Проверяем, не существует ли уже такое приглашение
            existing_invite = (
                session.query(Invite)
                .filter(
                    Invite.inviter_id == inviter_id,
                    Invite.author_id == author_id,
                    Invite.shout_id == shout_id,
                )
                .first()
            )

            if existing_invite:
                return {
                    "success": False,
                    "error": f"Приглашение от {inviter.name} для {author.name} на публикацию '{shout.title}' уже существует",
                }

            # Создаем новое приглашение
            new_invite = Invite(
                inviter_id=inviter_id,
                author_id=author_id,
                shout_id=shout_id,
                status=status,
            )

            session.add(new_invite)
            session.commit()

            logger.info(f"Создано приглашение: {inviter.name} приглашает {author.name} к публикации '{shout.title}'")

            return {"success": True, "error": None}

    except Exception as e:
        logger.error(f"Ошибка при создании приглашения: {e!s}")
        msg = f"Не удалось создать приглашение: {e!s}"
        raise GraphQLError(msg) from e


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
                    .filter(
                        Invite.inviter_id == inviter_id,
                        Invite.author_id == author_id,
                        Invite.shout_id == shout_id,
                    )
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
                logger.info(f"Пакетное удаление: удалено {deleted_count} приглашений")

        if errors:
            error_message = f"Удалено {deleted_count} из {len(invites)} приглашений. Ошибки: {', '.join(errors)}"
            return {"success": deleted_count > 0, "error": error_message}

        return {"success": True, "error": None}

    except Exception as e:
        logger.error(f"Ошибка при пакетном удалении приглашений: {e!s}")
        msg = f"Не удалось удалить приглашения: {e!s}"
        raise GraphQLError(msg) from e
