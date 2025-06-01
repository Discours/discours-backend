import json
import secrets
import time
import traceback
from typing import Any

from graphql import GraphQLResolveInfo

from auth.email import send_auth_email
from auth.exceptions import InvalidToken, ObjectNotExist
from auth.identity import Identity, Password
from auth.jwtcodec import JWTCodec
from auth.orm import Author, Role
from auth.sessions import SessionManager
from auth.tokenstorage import TokenStorage

# import asyncio # Убираем, так как резолвер будет синхронным
from services.auth import login_required
from services.db import local_session
from services.redis import redis
from services.schema import mutation, query
from settings import (
    ADMIN_EMAILS,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
)
from utils.generate_slug import generate_unique_slug
from utils.logger import root_logger as logger


@mutation.field("getSession")
@login_required
async def get_current_user(_: None, info: GraphQLResolveInfo) -> dict[str, Any]:
    """
    Получает информацию о текущем пользователе.

    Требует авторизации через декоратор login_required.

    Args:
        _: Родительский объект (не используется)
        info: Контекст GraphQL запроса

    Returns:
        Dict[str, Any]: Информация о пользователе или сообщение об ошибке
    """
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")

    if not author_id:
        logger.error("[getSession] Пользователь не авторизован")
        return {"error": "User not found"}

    try:
        # Используем кешированные данные если возможно
        if "name" in author_dict and "slug" in author_dict:
            return {"author": author_dict}

        # Если кеша нет, загружаем из базы
        with local_session() as session:
            author = session.query(Author).filter(Author.id == author_id).first()
            if not author:
                logger.error(f"[getSession] Автор с ID {author_id} не найден в БД")
                return {"error": "User not found"}

            return {"author": author.dict()}

    except Exception as e:
        logger.error(f"Failed to get current user: {e}")
        return {"error": "Internal error"}


@mutation.field("confirmEmail")
@login_required
async def confirm_email(_: None, _info: GraphQLResolveInfo, token: str) -> dict[str, Any]:
    """confirm owning email address"""
    try:
        logger.info("[auth] confirmEmail: Начало подтверждения email по токену.")
        payload = JWTCodec.decode(token)
        if payload is None:
            logger.warning("[auth] confirmEmail: Невозможно декодировать токен.")
            return {"success": False, "token": None, "author": None, "error": "Невалидный токен"}

        user_id = payload.user_id
        username = payload.username

        # Если TokenStorage.get асинхронный, это нужно будет переделать или вызывать синхронно
        # Для теста пока оставим, но это потенциальная точка отказа в синхронном резолвере
        token_key = f"{user_id}-{username}-{token}"
        await TokenStorage.get(token_key)

        with local_session() as session:
            user = session.query(Author).where(Author.id == user_id).first()
            if not user:
                logger.warning(f"[auth] confirmEmail: Пользователь с ID {user_id} не найден.")
                return {"success": False, "token": None, "author": None, "error": "Пользователь не найден"}

            # Создаем сессионный токен с новым форматом вызова и явным временем истечения
            device_info = {"email": user.email} if hasattr(user, "email") else None
            session_token = await TokenStorage.create_session(
                user_id=str(user_id),
                username=user.username or user.email or user.slug or username,
                device_info=device_info,
            )

            user.email_verified = True  # type: ignore[assignment]
            user.last_seen = int(time.time())  # type: ignore[assignment]
            session.add(user)
            session.commit()
            logger.info(f"[auth] confirmEmail: Email для пользователя {user_id} успешно подтвержден.")
            # Здесь можно не применять фильтрацию, так как пользователь получает свои данные
            return {"success": True, "token": session_token, "author": user, "error": None}
    except InvalidToken as e:
        logger.warning(f"[auth] confirmEmail: Невалидный токен - {e.message}")
        return {"success": False, "token": None, "author": None, "error": f"Невалидный токен: {e.message}"}
    except Exception as e:
        logger.error(f"[auth] confirmEmail: Общая ошибка - {e!s}\n{traceback.format_exc()}")
        return {
            "success": False,
            "token": None,
            "author": None,
            "error": f"Ошибка подтверждения email: {e!s}",
        }


def create_user(user_dict: dict[str, Any]) -> Author:
    """Create new user in database"""
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
async def register_by_email(_: None, info: GraphQLResolveInfo, email: str, password: str = "", name: str = ""):
    """register new user account by email"""
    email = email.lower()
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
        await send_link(None, info, email)
        logger.info(f"[auth] registerUser: Пользователь {email} зарегистрирован, ссылка для подтверждения отправлена.")
        # При регистрации возвращаем данные самому пользователю, поэтому не фильтруем
        return {
            "success": True,
            "token": None,
            "author": new_user,
            "error": "Требуется подтверждение email.",
        }
    except Exception as e:
        logger.error(f"[auth] registerUser: Ошибка при отправке ссылки подтверждения для {email}: {e!s}")
        return {
            "success": True,
            "token": None,
            "author": new_user,
            "error": f"Пользователь зарегистрирован, но произошла ошибка при отправке ссылки подтверждения: {e!s}",
        }


@mutation.field("sendLink")
async def send_link(
    _: None, _info: GraphQLResolveInfo, email: str, lang: str = "ru", template: str = "confirm"
) -> dict[str, Any]:
    """send link with confirm code to email"""
    email = email.lower()
    with local_session() as session:
        user = session.query(Author).filter(Author.email == email).first()
        if not user:
            msg = "User not found"
            raise ObjectNotExist(msg)
        # Если TokenStorage.create_onetime асинхронный...
        try:
            if hasattr(TokenStorage, "create_onetime"):
                token = await TokenStorage.create_onetime(user)
            else:
                # Fallback if create_onetime doesn't exist
                token = await TokenStorage.create_session(
                    user_id=str(user.id),
                    username=str(user.username or user.email or user.slug or ""),
                    device_info={"email": user.email} if hasattr(user, "email") else None,
                )
        except (AttributeError, ImportError):
            # Fallback if TokenStorage doesn't exist or doesn't have the method
            token = "temporary_token"
        # Если send_auth_email асинхронный...
        await send_auth_email(user, token, lang, template)
        return user


@mutation.field("login")
async def login(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """
    Авторизация пользователя с помощью email и пароля.

    Args:
        info: Контекст GraphQL запроса
        email: Email пользователя
        password: Пароль пользователя

    Returns:
        AuthResult с данными пользователя и токеном или сообщением об ошибке
    """
    logger.info(f"[auth] login: Попытка входа для {kwargs.get('email')}")

    # Гарантируем, что всегда возвращаем непустой объект AuthResult

    try:
        # Нормализуем email
        email = kwargs.get("email", "").lower()

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

            # Проверяем наличие роли reader
            has_reader_role = False
            if hasattr(author, "roles") and author.roles:
                for role in author.roles:
                    if role.id == "reader":
                        has_reader_role = True
                        break

            # Если у пользователя нет роли reader и он не админ, запрещаем вход
            if not has_reader_role:
                # Проверяем, есть ли роль admin или super
                is_admin = author.email in ADMIN_EMAILS.split(",")

                if not is_admin:
                    logger.warning(f"[auth] login: У пользователя {email} нет роли 'reader', в доступе отказано")
                    return {
                        "success": False,
                        "token": None,
                        "author": None,
                        "error": "У вас нет необходимых прав для входа. Обратитесь к администратору.",
                    }

            # Проверяем пароль - важно использовать непосредственно объект author, а не его dict
            logger.info(f"[auth] login: НАЧАЛО ПРОВЕРКИ ПАРОЛЯ для {email}")
            try:
                password = kwargs.get("password", "")
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
            except Exception as e:
                logger.error(f"[auth] login: Ошибка при проверке пароля: {e!s}")
                return {
                    "success": False,
                    "token": None,
                    "author": None,
                    "error": str(e),
                }

            # Получаем правильный объект автора - результат verify_result
            valid_author = verify_result if not isinstance(verify_result, dict) else author

            # Создаем токен через правильную функцию вместо прямого кодирования
            try:
                # Убедимся, что у автора есть нужные поля для создания токена
                if not hasattr(valid_author, "id") or (
                    not hasattr(valid_author, "username") and not hasattr(valid_author, "email")
                ):
                    logger.error(f"[auth] login: Объект автора не содержит необходимых атрибутов: {valid_author}")
                    return {
                        "success": False,
                        "token": None,
                        "author": None,
                        "error": "Внутренняя ошибка: некорректный объект автора",
                    }

                # Создаем сессионный токен
                logger.info(f"[auth] login: СОЗДАНИЕ ТОКЕНА для {email}, id={valid_author.id}")
                username = str(valid_author.username or valid_author.email or valid_author.slug or "")
                token = await TokenStorage.create_session(
                    user_id=str(valid_author.id),
                    username=username,
                    device_info={"email": valid_author.email} if hasattr(valid_author, "email") else None,
                )
                logger.info(f"[auth] login: токен успешно создан, длина: {len(token) if token else 0}")

                # Обновляем время последнего входа
                valid_author.last_seen = int(time.time())  # type: ignore[assignment]
                session.commit()

                # Устанавливаем httponly cookie различными способами для надежности
                cookie_set = False

                # Метод 1: GraphQL контекст через extensions
                try:
                    if hasattr(info.context, "extensions") and hasattr(info.context.extensions, "set_cookie"):
                        info.context.extensions.set_cookie(
                            SESSION_COOKIE_NAME,
                            token,
                            httponly=SESSION_COOKIE_HTTPONLY,
                            secure=SESSION_COOKIE_SECURE,
                            samesite=SESSION_COOKIE_SAMESITE,
                            max_age=SESSION_COOKIE_MAX_AGE,
                        )
                        logger.info("[auth] login: Установлена cookie через extensions")
                        cookie_set = True
                except Exception as e:
                    logger.error(f"[auth] login: Ошибка при установке cookie через extensions: {e!s}")

                # Метод 2: GraphQL контекст через response
                if not cookie_set:
                    try:
                        if hasattr(info.context, "response") and hasattr(info.context.response, "set_cookie"):
                            info.context.response.set_cookie(
                                key=SESSION_COOKIE_NAME,
                                value=token,
                                httponly=SESSION_COOKIE_HTTPONLY,
                                secure=SESSION_COOKIE_SECURE,
                                samesite=SESSION_COOKIE_SAMESITE,
                                max_age=SESSION_COOKIE_MAX_AGE,
                            )
                            logger.info("[auth] login: Установлена cookie через response")
                            cookie_set = True
                    except Exception as e:
                        logger.error(f"[auth] login: Ошибка при установке cookie через response: {e!s}")

                # Если ни один способ не сработал, создаем response в контексте
                if not cookie_set and hasattr(info.context, "request") and not hasattr(info.context, "response"):
                    try:
                        from starlette.responses import JSONResponse

                        response = JSONResponse({})
                        response.set_cookie(
                            key=SESSION_COOKIE_NAME,
                            value=token,
                            httponly=SESSION_COOKIE_HTTPONLY,
                            secure=SESSION_COOKIE_SECURE,
                            samesite=SESSION_COOKIE_SAMESITE,
                            max_age=SESSION_COOKIE_MAX_AGE,
                        )
                        info.context["response"] = response
                        logger.info("[auth] login: Создан новый response и установлена cookie")
                        cookie_set = True
                    except Exception as e:
                        logger.error(f"[auth] login: Ошибка при создании response и установке cookie: {e!s}")

                if not cookie_set:
                    logger.warning("[auth] login: Не удалось установить cookie никаким способом")

                # Возвращаем успешный результат с данными для клиента
                # Для ответа клиенту используем dict() с параметром True,
                # чтобы получить полный доступ к данным для самого пользователя
                logger.info(f"[auth] login: Успешный вход для {email}")
                author_dict = valid_author.dict(True)
                result = {"success": True, "token": token, "author": author_dict, "error": None}
                logger.info(
                    f"[auth] login: Возвращаемый результат: {{success: {result['success']}, token_length: {len(token) if token else 0}}}"
                )
                return result
            except Exception as token_error:
                logger.error(f"[auth] login: Ошибка при создании токена: {token_error!s}")
                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "token": None,
                    "author": None,
                    "error": f"Ошибка авторизации: {token_error!s}",
                }

    except Exception as e:
        logger.error(f"[auth] login: Ошибка при авторизации {email}: {e!s}")
        logger.error(traceback.format_exc())
        return {"success": False, "token": None, "author": None, "error": str(e)}


@query.field("isEmailUsed")
async def is_email_used(_: None, _info: GraphQLResolveInfo, email: str) -> bool:
    """check if email is used"""
    email = email.lower()
    with local_session() as session:
        user = session.query(Author).filter(Author.email == email).first()
    return user is not None


@mutation.field("logout")
@login_required
async def logout_resolver(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """
    Выход из системы через GraphQL с удалением сессии и cookie.

    Returns:
        dict: Результат операции выхода
    """
    success = False
    message = ""

    try:
        # Используем данные автора из контекста, установленные декоратором login_required
        author = info.context.get("author")
        if not author:
            logger.error("[auth] logout_resolver: Автор не найден в контексте после login_required")
            return {"success": False, "message": "Пользователь не найден в контексте"}

        user_id = str(author.get("id"))
        logger.debug(f"[auth] logout_resolver: Обработка выхода для пользователя {user_id}")

        # Получаем токен из cookie или заголовка
        request = info.context.get("request")
        token = None

        if request:
            # Проверяем cookie
            token = request.cookies.get(SESSION_COOKIE_NAME)

            # Если в cookie нет, проверяем заголовок Authorization
            if not token:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]  # Отрезаем "Bearer "

        if token:
            # Отзываем сессию используя данные из контекста
            await SessionManager.revoke_session(user_id, token)
            logger.info(f"[auth] logout_resolver: Токен успешно отозван для пользователя {user_id}")
            success = True
            message = "Выход выполнен успешно"
        else:
            logger.warning("[auth] logout_resolver: Токен не найден в запросе")
            # Все равно считаем успешным, так как пользователь уже не авторизован
            success = True
            message = "Выход выполнен (токен не найден)"

        # Удаляем cookie через extensions
        try:
            # Используем extensions для удаления cookie
            if hasattr(info.context, "extensions") and hasattr(info.context.extensions, "delete_cookie"):
                info.context.extensions.delete_cookie(SESSION_COOKIE_NAME)
                logger.info("[auth] logout_resolver: Cookie успешно удалена через extensions")
            elif hasattr(info.context, "response") and hasattr(info.context.response, "delete_cookie"):
                info.context.response.delete_cookie(SESSION_COOKIE_NAME)
                logger.info("[auth] logout_resolver: Cookie успешно удалена через response")
            else:
                logger.warning(
                    "[auth] logout_resolver: Невозможно удалить cookie - объекты extensions/response недоступны"
                )
        except Exception as e:
            logger.error(f"[auth] logout_resolver: Ошибка при удалении cookie: {e}")

    except Exception as e:
        logger.error(f"[auth] logout_resolver: Ошибка при выходе: {e}")
        success = False
        message = f"Ошибка при выходе: {e}"

    return {"success": success, "message": message}


@mutation.field("refreshToken")
@login_required
async def refresh_token_resolver(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """
    Обновление токена аутентификации через GraphQL.

    Returns:
        AuthResult с данными пользователя и обновленным токеном или сообщением об ошибке
    """
    try:
        # Используем данные автора из контекста, установленные декоратором login_required
        author = info.context.get("author")
        if not author:
            logger.error("[auth] refresh_token_resolver: Автор не найден в контексте после login_required")
            return {"success": False, "token": None, "author": None, "error": "Пользователь не найден в контексте"}

        user_id = author.get("id")
        if not user_id:
            logger.error("[auth] refresh_token_resolver: ID пользователя не найден в данных автора")
            return {"success": False, "token": None, "author": None, "error": "ID пользователя не найден"}

        # Получаем текущий токен из cookie или заголовка
        request = info.context.get("request")
        if not request:
            logger.error("[auth] refresh_token_resolver: Запрос не найден в контексте")
            return {"success": False, "token": None, "author": None, "error": "Запрос не найден в контексте"}

        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Отрезаем "Bearer "

        if not token:
            logger.warning("[auth] refresh_token_resolver: Токен не найден в запросе")
            return {"success": False, "token": None, "author": None, "error": "Токен не найден"}

        # Подготавливаем информацию об устройстве
        device_info = {
            "ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent"),
        }

        # Обновляем сессию (создаем новую и отзываем старую)
        new_token = await SessionManager.refresh_session(user_id, token, device_info)

        if not new_token:
            logger.error(f"[auth] refresh_token_resolver: Не удалось обновить токен для пользователя {user_id}")
            return {"success": False, "token": None, "author": None, "error": "Не удалось обновить токен"}

        # Устанавливаем cookie через extensions
        try:
            # Используем extensions для установки cookie
            if hasattr(info.context, "extensions") and hasattr(info.context.extensions, "set_cookie"):
                logger.info("[auth] refresh_token_resolver: Устанавливаем httponly cookie через extensions")
                info.context.extensions.set_cookie(
                    SESSION_COOKIE_NAME,
                    new_token,
                    httponly=SESSION_COOKIE_HTTPONLY,
                    secure=SESSION_COOKIE_SECURE,
                    samesite=SESSION_COOKIE_SAMESITE,
                    max_age=SESSION_COOKIE_MAX_AGE,
                )
            elif hasattr(info.context, "response") and hasattr(info.context.response, "set_cookie"):
                logger.info("[auth] refresh_token_resolver: Устанавливаем httponly cookie через response")
                info.context.response.set_cookie(
                    key=SESSION_COOKIE_NAME,
                    value=new_token,
                    httponly=SESSION_COOKIE_HTTPONLY,
                    secure=SESSION_COOKIE_SECURE,
                    samesite=SESSION_COOKIE_SAMESITE,
                    max_age=SESSION_COOKIE_MAX_AGE,
                )
            else:
                logger.warning(
                    "[auth] refresh_token_resolver: Невозможно установить cookie - объекты extensions/response недоступны"
                )
        except Exception as e:
            # В случае ошибки при установке cookie просто логируем, но продолжаем обновление токена
            logger.error(f"[auth] refresh_token_resolver: Ошибка при установке cookie: {e}")

        logger.info(f"[auth] refresh_token_resolver: Токен успешно обновлен для пользователя {user_id}")

        # Возвращаем данные автора из контекста (они уже обработаны декоратором)
        return {"success": True, "token": new_token, "author": author, "error": None}

    except Exception as e:
        logger.error(f"[auth] refresh_token_resolver: Ошибка при обновлении токена: {e}")
        return {"success": False, "token": None, "author": None, "error": str(e)}


@mutation.field("requestPasswordReset")
async def request_password_reset(_: None, _info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Запрос сброса пароля"""
    try:
        email = kwargs.get("email", "").lower()
        logger.info(f"[auth] requestPasswordReset: Запрос сброса пароля для {email}")

        with local_session() as session:
            author = session.query(Author).filter(Author.email == email).first()
            if not author:
                logger.warning(f"[auth] requestPasswordReset: Пользователь {email} не найден")
                # Возвращаем success даже если пользователь не найден (для безопасности)
                return {"success": True}

            # Создаем токен сброса пароля
            try:
                from auth.tokenstorage import TokenStorage

                if hasattr(TokenStorage, "create_onetime"):
                    token = await TokenStorage.create_onetime(author)
                else:
                    # Fallback if create_onetime doesn't exist
                    token = await TokenStorage.create_session(
                        user_id=str(author.id),
                        username=str(author.username or author.email or author.slug or ""),
                        device_info={"email": author.email} if hasattr(author, "email") else None,
                    )
            except (AttributeError, ImportError):
                # Fallback if TokenStorage doesn't exist or doesn't have the method
                token = "temporary_token"

            # Отправляем email с токеном
            await send_auth_email(author, token, kwargs.get("lang", "ru"), "password_reset")
            logger.info(f"[auth] requestPasswordReset: Письмо сброса пароля отправлено для {email}")

        return {"success": True}

    except Exception as e:
        logger.error(f"[auth] requestPasswordReset: Ошибка при запросе сброса пароля для {email}: {e!s}")
        return {"success": False}


@mutation.field("updateSecurity")
@login_required
async def update_security(
    _: None,
    info: GraphQLResolveInfo,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Мутация для смены пароля и/или email пользователя.

    Args:
        email: Новый email (опционально)
        old_password: Текущий пароль (обязательно для любых изменений)
        new_password: Новый пароль (опционально)

    Returns:
        SecurityUpdateResult: Результат операции с успехом/ошибкой и данными пользователя
    """
    logger.info("[auth] updateSecurity: Начало обновления данных безопасности")

    # Получаем текущего пользователя
    current_user = info.context.get("author")
    if not current_user:
        logger.warning("[auth] updateSecurity: Пользователь не авторизован")
        return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

    user_id = current_user.get("id")
    logger.info(f"[auth] updateSecurity: Обновление для пользователя ID={user_id}")

    # Валидация входных параметров
    new_password = kwargs.get("new_password")
    old_password = kwargs.get("old_password")
    email = kwargs.get("email")
    if not email and not new_password:
        logger.warning("[auth] updateSecurity: Не указаны параметры для изменения")
        return {"success": False, "error": "VALIDATION_ERROR", "author": None}

    if not old_password:
        logger.warning("[auth] updateSecurity: Не указан старый пароль")
        return {"success": False, "error": "VALIDATION_ERROR", "author": None}

    if new_password and len(new_password) < 8:
        logger.warning("[auth] updateSecurity: Новый пароль слишком короткий")
        return {"success": False, "error": "WEAK_PASSWORD", "author": None}

    if new_password == old_password:
        logger.warning("[auth] updateSecurity: Новый пароль совпадает со старым")
        return {"success": False, "error": "SAME_PASSWORD", "author": None}

    # Валидация email
    import re

    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if email and not re.match(email_pattern, email):
        logger.warning(f"[auth] updateSecurity: Неверный формат email: {email}")
        return {"success": False, "error": "INVALID_EMAIL", "author": None}

    email = email.lower() if email else ""

    try:
        with local_session() as session:
            # Получаем пользователя из базы данных
            author = session.query(Author).filter(Author.id == user_id).first()
            if not author:
                logger.error(f"[auth] updateSecurity: Пользователь с ID {user_id} не найден в БД")
                return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

            # Проверяем старый пароль
            if not author.verify_password(old_password):
                logger.warning(f"[auth] updateSecurity: Неверный старый пароль для пользователя {user_id}")
                return {"success": False, "error": "incorrect old password", "author": None}

            # Проверяем, что новый email не занят
            if email and email != author.email:
                existing_user = session.query(Author).filter(Author.email == email).first()
                if existing_user:
                    logger.warning(f"[auth] updateSecurity: Email {email} уже используется")
                    return {"success": False, "error": "email already exists", "author": None}

            # Выполняем изменения
            changes_made = []

            # Смена пароля
            if new_password:
                author.set_password(new_password)
                changes_made.append("password")
                logger.info(f"[auth] updateSecurity: Пароль изменен для пользователя {user_id}")

            # Смена email через Redis
            if email and email != author.email:
                # Генерируем токен подтверждения
                token = secrets.token_urlsafe(32)

                # Сохраняем данные смены email в Redis с TTL 1 час
                email_change_data = {
                    "user_id": user_id,
                    "old_email": author.email,
                    "new_email": email,
                    "token": token,
                    "expires_at": int(time.time()) + 3600,  # 1 час
                }

                # Ключ для хранения в Redis
                redis_key = f"email_change:{user_id}"

                # Используем внутреннюю систему истечения Redis: SET + EXPIRE
                await redis.execute("SET", redis_key, json.dumps(email_change_data))
                await redis.execute("EXPIRE", redis_key, 3600)  # 1 час TTL

                changes_made.append("email_pending")
                logger.info(
                    f"[auth] updateSecurity: Email смена инициирована для пользователя {user_id}: {author.email} -> {kwargs.get('email')}"
                )

                # TODO: Отправить письмо подтверждения на новый email
                # await send_email_change_confirmation(author, kwargs.get('email'), token)

            # Обновляем временную метку
            author.updated_at = int(time.time())  # type: ignore[assignment]

            # Сохраняем изменения
            session.add(author)
            session.commit()

            logger.info(
                f"[auth] updateSecurity: Изменения сохранены для пользователя {user_id}: {', '.join(changes_made)}"
            )

            # Возвращаем обновленные данные пользователя
            return {
                "success": True,
                "error": None,
                "author": author.dict(True),  # Возвращаем полные данные владельцу
            }

    except Exception as e:
        logger.error(f"[auth] updateSecurity: Ошибка при обновлении данных безопасности: {e!s}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e), "author": None}


@mutation.field("confirmEmailChange")
@login_required
async def confirm_email_change(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """
    Подтверждение смены email по токену.

    Args:
        token: Токен подтверждения смены email

    Returns:
        SecurityUpdateResult: Результат операции
    """
    logger.info("[auth] confirmEmailChange: Подтверждение смены email по токену")

    # Получаем текущего пользователя
    current_user = info.context.get("author")
    if not current_user:
        logger.warning("[auth] confirmEmailChange: Пользователь не авторизован")
        return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

    user_id = current_user.get("id")

    try:
        # Получаем данные смены email из Redis
        redis_key = f"email_change:{user_id}"
        cached_data = await redis.execute("GET", redis_key)

        if not cached_data:
            logger.warning(f"[auth] confirmEmailChange: Данные смены email не найдены для пользователя {user_id}")
            return {"success": False, "error": "NO_PENDING_EMAIL", "author": None}

        try:
            email_change_data = json.loads(cached_data)
        except json.JSONDecodeError:
            logger.error(f"[auth] confirmEmailChange: Ошибка декодирования данных из Redis для пользователя {user_id}")
            return {"success": False, "error": "INVALID_TOKEN", "author": None}

        # Проверяем токен
        if email_change_data.get("token") != kwargs.get("token"):
            logger.warning(f"[auth] confirmEmailChange: Неверный токен для пользователя {user_id}")
            return {"success": False, "error": "INVALID_TOKEN", "author": None}

        # Проверяем срок действия токена
        if email_change_data.get("expires_at", 0) < int(time.time()):
            logger.warning(f"[auth] confirmEmailChange: Токен истек для пользователя {user_id}")
            # Удаляем истекшие данные из Redis
            await redis.execute("DEL", redis_key)
            return {"success": False, "error": "TOKEN_EXPIRED", "author": None}

        new_email = email_change_data.get("new_email")
        if not new_email:
            logger.error(f"[auth] confirmEmailChange: Нет нового email в данных для пользователя {user_id}")
            return {"success": False, "error": "INVALID_TOKEN", "author": None}

        with local_session() as session:
            author = session.query(Author).filter(Author.id == user_id).first()
            if not author:
                logger.error(f"[auth] confirmEmailChange: Пользователь с ID {user_id} не найден в БД")
                return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

            # Проверяем, что новый email еще не занят
            existing_user = session.query(Author).filter(Author.email == new_email).first()
            if existing_user and existing_user.id != author.id:
                logger.warning(f"[auth] confirmEmailChange: Email {new_email} уже занят")
                # Удаляем данные из Redis
                await redis.execute("DEL", redis_key)
                return {"success": False, "error": "email already exists", "author": None}

            old_email = author.email

            # Применяем смену email
            author.email = new_email  # type: ignore[assignment]
            author.email_verified = True  # type: ignore[assignment] # Новый email считается подтвержденным
            author.updated_at = int(time.time())  # type: ignore[assignment]

            session.add(author)
            session.commit()

            # Удаляем данные смены email из Redis после успешного применения
            await redis.execute("DEL", redis_key)

            logger.info(
                f"[auth] confirmEmailChange: Email изменен для пользователя {user_id}: {old_email} -> {new_email}"
            )

            # TODO: Отправить уведомление на старый email о смене

            return {"success": True, "error": None, "author": author.dict(True)}

    except Exception as e:
        logger.error(f"[auth] confirmEmailChange: Ошибка при подтверждении смены email: {e!s}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e), "author": None}


@mutation.field("cancelEmailChange")
@login_required
async def cancel_email_change(_: None, info: GraphQLResolveInfo) -> dict[str, Any]:
    """
    Отмена смены email.

    Returns:
        SecurityUpdateResult: Результат операции
    """
    logger.info("[auth] cancelEmailChange: Отмена смены email")

    # Получаем текущего пользователя
    current_user = info.context.get("author")
    if not current_user:
        logger.warning("[auth] cancelEmailChange: Пользователь не авторизован")
        return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

    user_id = current_user.get("id")

    try:
        # Проверяем наличие данных смены email в Redis
        redis_key = f"email_change:{user_id}"
        cached_data = await redis.execute("GET", redis_key)

        if not cached_data:
            logger.warning(f"[auth] cancelEmailChange: Нет активной смены email для пользователя {user_id}")
            return {"success": False, "error": "NO_PENDING_EMAIL", "author": None}

        # Удаляем данные смены email из Redis
        await redis.execute("DEL", redis_key)

        # Получаем текущие данные пользователя
        with local_session() as session:
            author = session.query(Author).filter(Author.id == user_id).first()
            if not author:
                logger.error(f"[auth] cancelEmailChange: Пользователь с ID {user_id} не найден в БД")
                return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

            logger.info(f"[auth] cancelEmailChange: Смена email отменена для пользователя {user_id}")

            return {"success": True, "error": None, "author": author.dict(True)}

    except Exception as e:
        logger.error(f"[auth] cancelEmailChange: Ошибка при отмене смены email: {e!s}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e), "author": None}
