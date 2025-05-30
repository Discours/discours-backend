# -*- coding: utf-8 -*-
import time
import traceback

from graphql.type import GraphQLResolveInfo

from auth.credentials import AuthCredentials
from auth.email import send_auth_email
from auth.exceptions import InvalidToken, ObjectNotExist
from auth.identity import Identity, Password
from auth.internal import verify_internal_auth
from auth.jwtcodec import JWTCodec
from auth.orm import Author, Role
from auth.sessions import SessionManager
from auth.tokenstorage import TokenStorage

# import asyncio # Убираем, так как резолвер будет синхронным
from services.auth import login_required
from services.db import local_session
from services.schema import mutation, query
from settings import (
    ADMIN_EMAILS,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_TOKEN_HEADER,
)
from utils.generate_slug import generate_unique_slug
from utils.logger import root_logger as logger


@mutation.field("getSession")
@login_required
async def get_current_user(_, info):
    """
    Получает информацию о текущем пользователе.

    Требует авторизации через декоратор login_required.

    Args:
        _: Родительский объект (не используется)
        info: Контекст GraphQL запроса

    Returns:
        dict: Объект с токеном и данными автора с добавленной статистикой
    """
    # Получаем данные авторизации из контекста запроса
    author_id = info.context.get("author", {}).get("id")
    if not author_id:
        logger.error("[getSession] Пользователь не авторизован")
        from graphql.error import GraphQLError

        raise GraphQLError("Требуется авторизация")

    # Получаем токен из заголовка
    req = info.context.get("request")
    token = req.headers.get(SESSION_TOKEN_HEADER)
    if token and token.startswith("Bearer "):
        token = token.split("Bearer ")[-1].strip()

    # Получаем данные автора
    author = info.context.get("author")

    # Если автор не найден в контексте, пробуем получить из БД с добавлением статистики
    if not author:
        logger.debug(f"[getSession] Автор не найден в контексте для пользователя {author_id}, получаем из БД")

        try:
            # Используем функцию get_with_stat для получения автора со статистикой
            from sqlalchemy import select

            from resolvers.stat import get_with_stat

            q = select(Author).where(Author.id == author_id)
            authors_with_stat = get_with_stat(q)

            if authors_with_stat and len(authors_with_stat) > 0:
                author = authors_with_stat[0]

                # Обновляем last_seen отдельной транзакцией
                with local_session() as session:
                    author_db = session.query(Author).filter(Author.id == author_id).first()
                    if author_db:
                        author_db.last_seen = int(time.time())
                        session.commit()
            else:
                logger.error(f"[getSession] Автор с ID {author_id} не найден в БД")
                from graphql.error import GraphQLError

                raise GraphQLError("Пользователь не найден")

        except Exception as e:
            logger.error(f"[getSession] Ошибка при получении автора из БД: {e}", exc_info=True)
            from graphql.error import GraphQLError

            raise GraphQLError("Ошибка при получении данных пользователя")
    else:
        # Если автор уже есть в контексте, добавляем статистику
        try:
            from sqlalchemy import select

            from resolvers.stat import get_with_stat

            q = select(Author).where(Author.id == author_id)
            authors_with_stat = get_with_stat(q)

            if authors_with_stat and len(authors_with_stat) > 0:
                # Обновляем только статистику
                # Проверяем, является ли author объектом или словарем
                if isinstance(author, dict):
                    author["stat"] = authors_with_stat[0].stat
                else:
                    author.stat = authors_with_stat[0].stat
        except Exception as e:
            logger.warning(f"[getSession] Не удалось добавить статистику к автору: {e}")

    # Возвращаем данные сессии
    logger.info(f"[getSession] Успешно получена сессия для пользователя {author_id}")
    return {"token": token or "", "author": author}


@mutation.field("confirmEmail")
async def confirm_email(_, info, token):
    """confirm owning email address"""
    try:
        logger.info("[auth] confirmEmail: Начало подтверждения email по токену.")
        payload = JWTCodec.decode(token)
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

            user.email_verified = True
            user.last_seen = int(time.time())
            session.add(user)
            session.commit()
            logger.info(f"[auth] confirmEmail: Email для пользователя {user_id} успешно подтвержден.")
            # Здесь можно не применять фильтрацию, так как пользователь получает свои данные
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
    """create new user account"""
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
        await send_link(_, _info, email)
        logger.info(f"[auth] registerUser: Пользователь {email} зарегистрирован, ссылка для подтверждения отправлена.")
        # При регистрации возвращаем данные самому пользователю, поэтому не фильтруем
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
async def send_link(_, _info, email, lang="ru", template="email_confirmation"):
    """send link with confirm code to email"""
    email = email.lower()
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
async def login(_, info, email: str, password: str):
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
                logger.error(f"[auth] login: Ошибка при проверке пароля: {str(e)}")
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
                if (
                    not hasattr(valid_author, "id")
                    or not hasattr(valid_author, "username")
                    and not hasattr(valid_author, "email")
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
                token = await TokenStorage.create_session(
                    user_id=str(valid_author.id),
                    username=valid_author.username or valid_author.email or valid_author.slug or "",
                    device_info={"email": valid_author.email} if hasattr(valid_author, "email") else None,
                )
                logger.info(f"[auth] login: токен успешно создан, длина: {len(token) if token else 0}")

                # Обновляем время последнего входа
                valid_author.last_seen = int(time.time())
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
                        logger.info(f"[auth] login: Установлена cookie через extensions")
                        cookie_set = True
                except Exception as e:
                    logger.error(f"[auth] login: Ошибка при установке cookie через extensions: {str(e)}")

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
                            logger.info(f"[auth] login: Установлена cookie через response")
                            cookie_set = True
                    except Exception as e:
                        logger.error(f"[auth] login: Ошибка при установке cookie через response: {str(e)}")

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
                        logger.info(f"[auth] login: Создан новый response и установлена cookie")
                        cookie_set = True
                    except Exception as e:
                        logger.error(f"[auth] login: Ошибка при создании response и установке cookie: {str(e)}")

                if not cookie_set:
                    logger.warning(f"[auth] login: Не удалось установить cookie никаким способом")

                # Возвращаем успешный результат с данными для клиента
                # Для ответа клиенту используем dict() с параметром access=True,
                # чтобы получить полный доступ к данным для самого пользователя
                logger.info(f"[auth] login: Успешный вход для {email}")
                author_dict = valid_author.dict(access=True)
                result = {"success": True, "token": token, "author": author_dict, "error": None}
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


@query.field("isEmailUsed")
async def is_email_used(_, _info, email):
    """check if email is used"""
    email = email.lower()
    with local_session() as session:
        user = session.query(Author).filter(Author.email == email).first()
    return user is not None


@mutation.field("logout")
async def logout_resolver(_, info: GraphQLResolveInfo):
    """
    Выход из системы через GraphQL с удалением сессии и cookie.

    Returns:
        dict: Результат операции выхода
    """
    # Получаем токен из cookie или заголовка
    request = info.context["request"]
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        # Проверяем заголовок авторизации
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Отрезаем "Bearer "

    success = False
    message = ""

    # Если токен найден, отзываем его
    if token:
        try:
            # Декодируем токен для получения user_id
            user_id, _ = await verify_internal_auth(token)
            if user_id:
                # Отзываем сессию
                await SessionManager.revoke_session(user_id, token)
                logger.info(f"[auth] logout_resolver: Токен успешно отозван для пользователя {user_id}")
                success = True
                message = "Выход выполнен успешно"
            else:
                logger.warning("[auth] logout_resolver: Не удалось получить user_id из токена")
                message = "Не удалось обработать токен"
        except Exception as e:
            logger.error(f"[auth] logout_resolver: Ошибка при отзыве токена: {e}")
            message = f"Ошибка при выходе: {str(e)}"
    else:
        message = "Токен не найден"
        success = True  # Если токена нет, то пользователь уже вышел из системы

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
            logger.warning("[auth] logout_resolver: Невозможно удалить cookie - объекты extensions/response недоступны")
    except Exception as e:
        logger.error(f"[auth] logout_resolver: Ошибка при удалении cookie: {str(e)}")
        logger.debug(traceback.format_exc())

    return {"success": success, "message": message}


@mutation.field("refreshToken")
async def refresh_token_resolver(_, info: GraphQLResolveInfo):
    """
    Обновление токена аутентификации через GraphQL.

    Returns:
        AuthResult с данными пользователя и обновленным токеном или сообщением об ошибке
    """
    request = info.context["request"]

    # Получаем текущий токен из cookie или заголовка
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Отрезаем "Bearer "

    if not token:
        logger.warning("[auth] refresh_token_resolver: Токен не найден в запросе")
        return {"success": False, "token": None, "author": None, "error": "Токен не найден"}

    try:
        # Получаем информацию о пользователе из токена
        user_id, _ = await verify_internal_auth(token)
        if not user_id:
            logger.warning("[auth] refresh_token_resolver: Недействительный токен")
            return {"success": False, "token": None, "author": None, "error": "Недействительный токен"}

        # Получаем пользователя из базы данных
        with local_session() as session:
            author = session.query(Author).filter(Author.id == user_id).first()

            if not author:
                logger.warning(f"[auth] refresh_token_resolver: Пользователь с ID {user_id} не найден")
                return {"success": False, "token": None, "author": None, "error": "Пользователь не найден"}

            # Обновляем сессию (создаем новую и отзываем старую)
            device_info = {"ip": request.client.host, "user_agent": request.headers.get("user-agent")}
            new_token = await SessionManager.refresh_session(user_id, token, device_info)

            if not new_token:
                logger.error("[auth] refresh_token_resolver: Не удалось обновить токен")
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
                logger.error(f"[auth] refresh_token_resolver: Ошибка при установке cookie: {str(e)}")
                logger.debug(traceback.format_exc())

            logger.info(f"[auth] refresh_token_resolver: Токен успешно обновлен для пользователя {user_id}")
            return {"success": True, "token": new_token, "author": author, "error": None}

    except Exception as e:
        logger.error(f"[auth] refresh_token_resolver: Ошибка при обновлении токена: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "token": None, "author": None, "error": str(e)}
