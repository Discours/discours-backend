# -*- coding: utf-8 -*-
import time
import traceback
from utils.logger import root_logger as logger

from graphql.type import GraphQLResolveInfo
# import asyncio # Убираем, так как резолвер будет синхронным

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from auth.decorators import admin_auth_required
from auth.email import send_auth_email
from auth.exceptions import InvalidToken, ObjectNotExist
from auth.identity import Identity, Password
from auth.jwtcodec import JWTCodec
from auth.tokenstorage import TokenStorage
from auth.orm import Author, Role
from services.db import local_session
from services.schema import mutation, query
from settings import (
    SESSION_TOKEN_HEADER,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_HTTPONLY,
)
from utils.generate_slug import generate_unique_slug
from graphql.error import GraphQLError
from math import ceil
from sqlalchemy import or_


@mutation.field("getSession")
@login_required
async def get_current_user(_, info):
    auth: AuthCredentials = info.context["request"].auth
    token = info.context["request"].headers.get(SESSION_TOKEN_HEADER)

    with local_session() as session:
        author = session.query(Author).where(Author.id == auth.author_id).one()
        author.last_seen = int(time.time())
        session.commit()

        return {"token": token, "author": author}


@mutation.field("confirmEmail")
async def confirm_email(_, info, token):
    """confirm owning email address"""
    try:
        logger.info("[auth] confirmEmail: Начало подтверждения email по токену.")
        payload = JWTCodec.decode(token)
        user_id = payload.user_id
        # Если TokenStorage.get асинхронный, это нужно будет переделать или вызывать синхронно
        # Для теста пока оставим, но это потенциальная точка отказа в синхронном резолвере
        await TokenStorage.get(f"{user_id}-{payload.username}-{token}")
        with local_session() as session:
            user = session.query(Author).where(Author.id == user_id).first()
            if not user:
                logger.warning(f"[auth] confirmEmail: Пользователь с ID {user_id} не найден.")
                return {"success": False, "error": "Пользователь не найден"}
            # Если TokenStorage.create_session асинхронный...
            session_token = await TokenStorage.create_session(user)
            user.email_verified = True
            user.last_seen = int(time.time())
            session.add(user)
            session.commit()
            logger.info(f"[auth] confirmEmail: Email для пользователя {user_id} успешно подтвержден.")
            return {"success": True, "token": session_token, "author": user, "error": None}
    except InvalidToken as e:
        logger.warning(f"[auth] confirmEmail: Невалидный токен - {e.message}")
        return {"success": False, "token": None, "author": None, "error": f"Невалидный токен: {e.message}"}
    except Exception as e:
        logger.error(f"[auth] confirmEmail: Общая ошибка - {str(e)}\n{traceback.format_exc()}")
        return {
            "success": False,
            "token": None,
            "author": None,
            "error": f"Ошибка подтверждения email: {str(e)}",
        }


def create_user(user_dict):
    user = Author(**user_dict)
    with local_session() as session:
        # Добавляем пользователя в БД
        session.add(user)
        session.flush()  # Получаем ID пользователя

        # Получаем или создаём стандартную роль "reader"
        reader_role = session.query(Role).filter(Role.id == "reader").first()
        if not reader_role:
            reader_role = Role(id="reader", name="Читатель")
            session.add(reader_role)
            session.flush()

        # Получаем основное сообщество
        from orm.community import Community

        main_community = session.query(Community).filter(Community.id == 1).first()
        if not main_community:
            main_community = Community(
                id=1,
                name="Discours",
                slug="discours",
                desc="Cообщество Discours",
                created_by=user.id,
            )
            session.add(main_community)
            session.flush()

        # Создаём связь автор-роль-сообщество
        from auth.orm import AuthorRole

        author_role = AuthorRole(author=user.id, role=reader_role.id, community=main_community.id)
        session.add(author_role)
        session.commit()
    return user


@mutation.field("registerUser")
async def register_by_email(_, _info, email: str, password: str = "", name: str = ""):
    email = email.lower()
    """creates new user account"""
    logger.info(f"[auth] registerUser: Попытка регистрации для {email}")
    with local_session() as session:
        user = session.query(Author).filter(Author.email == email).first()
    if user:
        logger.warning(f"[auth] registerUser: Пользователь {email} уже существует.")
        # raise Unauthorized("User already exist") # Это вызовет ошибку GraphQL, но не "cannot return null"
        return {"success": False, "token": None, "author": None, "error": "Пользователь уже существует"}

    slug = generate_unique_slug(name if name else email.split("@")[0])

    user_dict = {
        "email": email,
        "username": email,
        "name": name if name else email.split("@")[0],
        "slug": slug,
    }
    if password:
        user_dict["password"] = Password.encode(password)

    new_user = create_user(user_dict)
    # Предполагается, что auth_send_link вернет объект Author или вызовет исключение
    # Для AuthResult нам также нужен токен и статус.
    # После регистрации обычно либо сразу логинят, либо просто сообщают об успехе.
    # Сейчас auth_send_link используется, что не логично для AuthResult.
    # Вернем успешную регистрацию без токена, предполагая, что пользователь должен будет залогиниться или подтвердить email.

    # Попытка отправить ссылку для подтверждения email
    try:
        # Если auth_send_link асинхронный...
        await auth_send_link(_, _info, email)
        logger.info(
            f"[auth] registerUser: Пользователь {email} зарегистрирован, ссылка для подтверждения отправлена."
        )
        return {
            "success": True,
            "token": None,
            "author": new_user,
            "error": "Требуется подтверждение email.",
        }
    except Exception as e:
        logger.error(f"[auth] registerUser: Ошибка при отправке ссылки подтверждения для {email}: {str(e)}")
        return {
            "success": True,
            "token": None,
            "author": new_user,
            "error": f"Пользователь зарегистрирован, но произошла ошибка при отправке ссылки подтверждения: {str(e)}",
        }


@mutation.field("sendLink")
async def auth_send_link(_, _info, email, lang="ru", template="email_confirmation"):
    email = email.lower()
    """send link with confirm code to email"""
    with local_session() as session:
        user = session.query(Author).filter(Author.email == email).first()
        if not user:
            raise ObjectNotExist("User not found")
        else:
            # Если TokenStorage.create_onetime асинхронный...
            token = await TokenStorage.create_onetime(user)
            # Если send_auth_email асинхронный...
            await send_auth_email(user, token, lang, template)
            return user


@mutation.field("login")
async def login_mutation(_, info, email: str, password: str):
    """
    Авторизация пользователя с помощью email и пароля.

    Args:
        info: Контекст GraphQL запроса
        email: Email пользователя
        password: Пароль пользователя

    Returns:
        AuthResult с данными пользователя и токеном или сообщением об ошибке
    """
    logger.info(f"[auth] login: Попытка входа для {email}")

    # Гарантируем, что всегда возвращаем непустой объект AuthResult
    default_response = {"success": False, "token": None, "author": None, "error": "Неизвестная ошибка"}

    try:
        # Нормализуем email
        email = email.lower()

        # Получаем пользователя из базы
        with local_session() as session:
            author = session.query(Author).filter(Author.email == email).first()

            if not author:
                logger.warning(f"[auth] login: Пользователь {email} не найден")
                return {
                    "success": False,
                    "token": None,
                    "author": None,
                    "error": "Пользователь с таким email не найден",
                }

            # Логируем информацию о найденном авторе
            logger.info(
                f"[auth] login: Найден автор {email}, id={author.id}, имя={author.name}, пароль есть: {bool(author.password)}"
            )

            # Проверяем пароль
            logger.info(f"[auth] login: НАЧАЛО ПРОВЕРКИ ПАРОЛЯ для {email}")
            verify_result = Identity.password(author, password)
            logger.info(
                f"[auth] login: РЕЗУЛЬТАТ ПРОВЕРКИ ПАРОЛЯ: {verify_result if isinstance(verify_result, dict) else 'успешно'}"
            )

            if isinstance(verify_result, dict) and verify_result.get("error"):
                logger.warning(f"[auth] login: Неверный пароль для {email}: {verify_result.get('error')}")
                return {
                    "success": False,
                    "token": None,
                    "author": None,
                    "error": verify_result.get("error", "Ошибка авторизации"),
                }

            # Получаем правильный объект автора - результат verify_result
            valid_author = verify_result if not isinstance(verify_result, dict) else author

            # Создаем токен через правильную функцию вместо прямого кодирования
            try:
                # Убедимся, что у автора есть нужные поля для создания токена
                if (
                    not hasattr(valid_author, "id")
                    or not hasattr(valid_author, "username")
                    and not hasattr(valid_author, "email")
                ):
                    logger.error(
                        f"[auth] login: Объект автора не содержит необходимых атрибутов: {valid_author}"
                    )
                    return {
                        "success": False,
                        "token": None,
                        "author": None,
                        "error": "Внутренняя ошибка: некорректный объект автора",
                    }

                # Создаем сессионный токен
                logger.info(f"[auth] login: СОЗДАНИЕ ТОКЕНА для {email}, id={valid_author.id}")
                token = await TokenStorage.create_session(valid_author)
                logger.info(f"[auth] login: токен успешно создан, длина: {len(token) if token else 0}")

                # Обновляем время последнего входа
                valid_author.last_seen = int(time.time())
                session.commit()

                # Устанавливаем httponly cookie с помощью GraphQLExtensionsMiddleware
                try:
                    # Используем extensions для установки cookie
                    if hasattr(info.context, "extensions") and hasattr(
                        info.context.extensions, "set_cookie"
                    ):
                        logger.info("[auth] login: Устанавливаем httponly cookie через extensions")
                        info.context.extensions.set_cookie(
                            SESSION_COOKIE_NAME,
                            token,
                            httponly=SESSION_COOKIE_HTTPONLY,
                            secure=SESSION_COOKIE_SECURE,
                            samesite=SESSION_COOKIE_SAMESITE,
                            max_age=SESSION_COOKIE_MAX_AGE,
                        )
                    elif hasattr(info.context, "response") and hasattr(info.context.response, "set_cookie"):
                        logger.info("[auth] login: Устанавливаем httponly cookie через response")
                        info.context.response.set_cookie(
                            key=SESSION_COOKIE_NAME,
                            value=token,
                            httponly=SESSION_COOKIE_HTTPONLY,
                            secure=SESSION_COOKIE_SECURE,
                            samesite=SESSION_COOKIE_SAMESITE,
                            max_age=SESSION_COOKIE_MAX_AGE,
                        )
                    else:
                        logger.warning(
                            "[auth] login: Невозможно установить cookie - объекты extensions/response недоступны"
                        )
                except Exception as e:
                    # В случае ошибки при установке cookie просто логируем, но продолжаем авторизацию
                    logger.error(f"[auth] login: Ошибка при установке cookie: {str(e)}")
                    logger.debug(traceback.format_exc())

                # Возвращаем успешный результат
                logger.info(f"[auth] login: Успешный вход для {email}")
                result = {"success": True, "token": token, "author": valid_author, "error": None}
                logger.info(
                    f"[auth] login: Возвращаемый результат: {{success: {result['success']}, token_length: {len(token) if token else 0}}}"
                )
                return result
            except Exception as token_error:
                logger.error(f"[auth] login: Ошибка при создании токена: {str(token_error)}")
                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "token": None,
                    "author": None,
                    "error": f"Ошибка авторизации: {str(token_error)}",
                }

    except Exception as e:
        logger.error(f"[auth] login: Ошибка при авторизации {email}: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "token": None, "author": None, "error": str(e)}

    # Если по какой-то причине мы дошли до этой точки, вернем безопасный результат
    return default_response


@query.field("signOut")
@login_required
async def sign_out(_, info: GraphQLResolveInfo):
    token = info.context["request"].headers.get(SESSION_TOKEN_HEADER, "")
    # Если TokenStorage.revoke асинхронный...
    status = await TokenStorage.revoke(token)
    return status


@query.field("isEmailUsed")
async def is_email_used(_, _info, email):
    email = email.lower()
    with local_session() as session:
        user = session.query(Author).filter(Author.email == email).first()
    return user is not None


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
                        "roles": [role.role for role in user.roles]
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
