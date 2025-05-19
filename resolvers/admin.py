from math import ceil
from sqlalchemy import or_
from graphql.error import GraphQLError

from auth.decorators import admin_auth_required
from services.db import local_session
from services.schema import query
from auth.orm import Author, Role
from utils.logger import root_logger as logger


@query.field("adminGetUsers")
@admin_auth_required
async def admin_get_users(_, info, limit=10, offset=0, search=None):
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
                        Author.id.cast(str).ilike(search_term),
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
            result = {
                "users": [
                    {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "slug": user.slug,
                        "roles": [role.id for role in user.roles]
                        if hasattr(user, "roles") and user.roles
                        else [],
                        "created_at": user.created_at,
                        "last_seen": user.last_seen,
                        "muted": user.muted or False,
                        "is_active": not user.blocked if hasattr(user, "blocked") else True,
                    }
                    for user in users
                ],
                "total": total_count,
                "page": current_page,
                "perPage": per_page,
                "totalPages": total_pages,
            }

            return result
    except Exception as e:
        import traceback
        logger.error(f"Ошибка при получении списка пользователей: {str(e)}")
        logger.error(traceback.format_exc())
        raise GraphQLError(f"Не удалось получить список пользователей: {str(e)}")


@query.field("adminGetRoles")
@admin_auth_required
async def admin_get_roles(_, info):
    """
    Получает список всех ролей для админ-панели

    Args:
        info: Контекст GraphQL запроса

    Returns:
        Список ролей с их описаниями
    """
    try:
        with local_session() as session:
            # Получаем все роли из базы данных
            roles = session.query(Role).all()

            # Преобразуем их в формат для API
            result = [
                {
                    "id": role.id,
                    "name": role.name,
                    "description": f"Роль с правами: {', '.join(p.resource + ':' + p.operation for p in role.permissions)}"
                    if role.permissions
                    else "Роль без особых прав",
                }
                for role in roles
            ]

            return result
    except Exception as e:
        logger.error(f"Ошибка при получении списка ролей: {str(e)}")
        raise GraphQLError(f"Не удалось получить список ролей: {str(e)}")
