from math import ceil
from sqlalchemy import or_, cast, String
from graphql.error import GraphQLError

from auth.decorators import admin_auth_required
from services.db import local_session
from services.schema import query, mutation
from auth.orm import Author, Role, AuthorRole
from services.env import EnvManager, EnvVariable
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
                        "last_seen": user.last_seen
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


@query.field("getEnvVariables")
@admin_auth_required
async def get_env_variables(_, info):
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
        sections = env_manager.get_all_variables()
        
        # Преобразуем к формату GraphQL API
        result = [
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
                ]
            }
            for section in sections
        ]
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении переменных окружения: {str(e)}")
        raise GraphQLError(f"Не удалось получить переменные окружения: {str(e)}")


@mutation.field("updateEnvVariable")
@admin_auth_required
async def update_env_variable(_, info, key, value):
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
        result = env_manager.update_variable(key, value)
        
        if result:
            logger.info(f"Переменная окружения '{key}' успешно обновлена")
        else:
            logger.error(f"Не удалось обновить переменную окружения '{key}'")
            
        return result
    except Exception as e:
        logger.error(f"Ошибка при обновлении переменной окружения: {str(e)}")
        return False


@mutation.field("updateEnvVariables")
@admin_auth_required
async def update_env_variables(_, info, variables):
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
            EnvVariable(
                key=var.get("key", ""),
                value=var.get("value", ""),
                type=var.get("type", "string")
            )
            for var in variables
        ]
        
        # Обновляем переменные
        result = env_manager.update_variables(env_variables)
        
        if result:
            logger.info(f"Переменные окружения успешно обновлены ({len(variables)} шт.)")
        else:
            logger.error(f"Не удалось обновить переменные окружения")
            
        return result
    except Exception as e:
        logger.error(f"Ошибка при массовом обновлении переменных окружения: {str(e)}")
        return False


@mutation.field("adminUpdateUser")
@admin_auth_required
async def admin_update_user(_, info, user):
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
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Получаем ID сообщества по умолчанию
            default_community_id = 1  # Используем значение по умолчанию из модели AuthorRole
            
            try:
                # Очищаем текущие роли пользователя через ORM
                session.query(AuthorRole).filter(AuthorRole.author == user_id).delete()
                session.flush()
                
                # Получаем все существующие роли, которые указаны для обновления
                role_objects = session.query(Role).filter(Role.id.in_(roles)).all()
                
                # Проверяем, все ли запрошенные роли найдены
                found_role_ids = [role.id for role in role_objects]
                missing_roles = set(roles) - set(found_role_ids)
                
                if missing_roles:
                    warning_msg = f"Некоторые роли не найдены в базе: {', '.join(missing_roles)}"
                    logger.warning(warning_msg)
                
                # Создаем новые записи в таблице author_role с указанием community
                for role in role_objects:
                    # Используем ORM для создания новых записей
                    author_role = AuthorRole(
                        community=default_community_id,
                        author=user_id,
                        role=role.id
                    )
                    session.add(author_role)
                
                # Сохраняем изменения в базе данных
                session.commit()
                
                # Проверяем, добавлена ли пользователю роль reader
                has_reader = 'reader' in [role.id for role in role_objects]
                if not has_reader:
                    logger.warning(f"Пользователю {author.email or author.id} не назначена роль 'reader'. Доступ в систему будет ограничен.")
                
                logger.info(f"Роли пользователя {author.email or author.id} обновлены: {', '.join(found_role_ids)}")
                
                return {
                    "success": True
                }
            except Exception as e:
                # Обработка вложенных исключений
                session.rollback()
                error_msg = f"Ошибка при изменении ролей: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
    except Exception as e:
        import traceback
        error_msg = f"Ошибка при обновлении ролей пользователя: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": error_msg
        }
