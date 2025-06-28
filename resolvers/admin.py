from math import ceil
from typing import Any

from graphql import GraphQLResolveInfo
from graphql.error import GraphQLError
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func, select

from auth.decorators import admin_auth_required
from auth.orm import Author, AuthorRole, Role
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
            total_pages = ceil(total_count / per_page)
            current_page = (offset // per_page) + 1 if per_page > 0 else 1

            # Применяем пагинацию
            users = query.order_by(Author.id).offset(offset).limit(limit).all()

            # Преобразуем в формат для API
            return {
                "users": [
                    {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "slug": user.slug,
                        "roles": [role.id for role in user.roles] if hasattr(user, "roles") and user.roles else [],
                        "created_at": user.created_at,
                        "last_seen": user.last_seen,
                    }
                    for user in users
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
async def admin_get_roles(_: None, info: GraphQLResolveInfo) -> dict[str, Any]:
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
            roles_list = [
                {
                    "id": role.id,
                    "name": role.name,
                    "description": f"Роль с правами: {', '.join(p.resource + ':' + p.operation for p in role.permissions)}"
                    if role.permissions
                    else "Роль без особых прав",
                }
                for role in roles
            ]

            return {"roles": roles_list}

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
    Обновляет роли пользователя

    Args:
        info: Контекст GraphQL запроса
        user: Данные для обновления пользователя (содержит id и roles)

    Returns:
        Boolean: результат операции или объект с ошибкой
    """
    try:
        user_id = user.get("id")
        roles = user.get("roles", [])

        if not roles:
            logger.warning(f"Пользователю {user_id} не назначено ни одной роли. Доступ в систему будет заблокирован.")

        with local_session() as session:
            # Получаем пользователя из базы данных
            author = session.query(Author).filter(Author.id == user_id).first()

            if not author:
                error_msg = f"Пользователь с ID {user_id} не найден"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

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

                logger.info(f"Роли пользователя {author.email or author.id} обновлены: {', '.join(found_role_ids)}")

                return {"success": True}
            except Exception as e:
                # Обработка вложенных исключений
                session.rollback()
                error_msg = f"Ошибка при изменении ролей: {e!s}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
    except Exception as e:
        import traceback

        error_msg = f"Ошибка при обновлении ролей пользователя: {e!s}"
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
            total_pages = ceil(total_count / per_page)
            current_page = (offset // per_page) + 1 if per_page > 0 else 1

            # Применяем пагинацию и сортировку (новые сверху)
            q = q.order_by(Shout.created_at.desc())

            # Используем существующую функцию для получения публикаций с данными
            if status == "all":
                # Для статуса "all" используем простой запрос без статистики
                q = q.limit(limit).offset(offset)
                shouts_result = session.execute(q).all()
                shouts_data = []

                for row in shouts_result:
                    shout = row[0] if isinstance(row, tuple) else row
                    # Обрабатываем поле media
                    media_data = []
                    if shout.media:
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
                        "id": shout.id,
                        "title": shout.title,
                        "slug": shout.slug,
                        "body": shout.body,
                        "lead": shout.lead,
                        "subtitle": shout.subtitle,
                        "layout": shout.layout,
                        "lang": shout.lang,
                        "cover": shout.cover,
                        "cover_caption": shout.cover_caption,
                        "media": media_data,
                        "seo": shout.seo,
                        "created_at": shout.created_at,
                        "updated_at": shout.updated_at,
                        "published_at": shout.published_at,
                        "featured_at": shout.featured_at,
                        "deleted_at": shout.deleted_at,
                        "created_by": {
                            "id": shout.created_by,
                            "email": "unknown",  # Заполним при необходимости
                            "name": "unknown",
                        },
                        "updated_by": None,  # Заполним при необходимости
                        "deleted_by": None,  # Заполним при необходимости
                        "community": {
                            "id": shout.community,
                            "name": "unknown",  # Заполним при необходимости
                        },
                        "authors": [
                            {"id": author.id, "email": author.email, "name": author.name, "slug": author.slug}
                            for author in (shout.authors or [])
                        ],
                        "topics": [
                            {"id": topic.id, "title": topic.title, "slug": topic.slug} for topic in (shout.topics or [])
                        ],
                        "version_of": shout.version_of,
                        "draft": shout.draft,
                        "stat": None,  # Заполним при необходимости
                    }
                    shouts_data.append(shout_dict)
            else:
                # Используем существующую функцию для получения публикаций со статистикой
                shouts_data = get_shouts_with_links(info, q, limit, offset)

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
            shout.deleted_at = None
            shout.deleted_by = None

            session.commit()

            logger.info(f"Публикация {shout.title or shout.id} восстановлена администратором")
            return {"success": True}

    except Exception as e:
        error_msg = f"Ошибка при восстановлении публикации: {e!s}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
