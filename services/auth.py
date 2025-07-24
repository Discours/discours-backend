"""
Сервис аутентификации с бизнес-логикой для регистрации,
входа и управления сессиями и декорраторами для GraphQL.
"""

import json
import secrets
import time
from functools import wraps
from typing import Any, Callable, Optional

from starlette.requests import Request

from auth.email import send_auth_email
from auth.exceptions import InvalidPassword, InvalidToken, ObjectNotExist
from auth.identity import Identity, Password
from auth.internal import verify_internal_auth
from auth.jwtcodec import JWTCodec
from auth.orm import Author
from auth.tokens.storage import TokenStorage
from cache.cache import get_cached_author_by_id
from orm.community import Community, CommunityAuthor, CommunityFollower
from services.db import local_session
from services.redis import redis
from settings import (
    ADMIN_EMAILS,
    SESSION_COOKIE_NAME,
    SESSION_TOKEN_HEADER,
)
from utils.generate_slug import generate_unique_slug
from utils.logger import root_logger as logger

# Список разрешенных заголовков
ALLOWED_HEADERS = ["Authorization", "Content-Type"]


class AuthService:
    """Сервис аутентификации с бизнес-логикой"""

    async def check_auth(self, req: Request) -> tuple[int, list[str], bool]:
        """
        Проверка авторизации пользователя.

        Проверяет токен и получает данные из локальной БД.
        """
        logger.debug("[check_auth] Проверка авторизации...")

        # Получаем заголовок авторизации
        token = None

        # Если req is None (в тестах), возвращаем пустые данные
        if not req:
            logger.debug("[check_auth] Запрос отсутствует (тестовое окружение)")
            return 0, [], False

        # Проверяем заголовок с учетом регистра
        headers_dict = dict(req.headers.items())
        logger.debug(f"[check_auth] Все заголовки: {headers_dict}")

        # Ищем заголовок Authorization независимо от регистра
        for header_name, header_value in headers_dict.items():
            if header_name.lower() == SESSION_TOKEN_HEADER.lower():
                token = header_value
                logger.debug(f"[check_auth] Найден заголовок {header_name}: {token[:10]}...")
                break

        if not token:
            logger.debug("[check_auth] Токен не найден в заголовках")
            return 0, [], False

        # Очищаем токен от префикса Bearer если он есть
        if token.startswith("Bearer "):
            token = token.split("Bearer ")[-1].strip()

        # Проверяем авторизацию внутренним механизмом
        logger.debug("[check_auth] Вызов verify_internal_auth...")
        user_id, user_roles, is_admin = await verify_internal_auth(token)
        logger.debug(
            f"[check_auth] Результат verify_internal_auth: user_id={user_id}, roles={user_roles}, is_admin={is_admin}"
        )

        # Если в ролях нет админа, но есть ID - проверяем через новую систему RBAC
        if user_id and not is_admin:
            try:
                # Преобразуем user_id в число
                try:
                    if isinstance(user_id, str):
                        user_id_int = int(user_id.strip())
                    else:
                        user_id_int = int(user_id)
                except (ValueError, TypeError):
                    logger.error(f"Невозможно преобразовать user_id {user_id} в число")
                    return 0, [], False

                # Получаем роли через новую систему CommunityAuthor
                from orm.community import get_user_roles_in_community

                user_roles_in_community = get_user_roles_in_community(user_id_int, community_id=1)
                logger.debug(f"[check_auth] Роли из CommunityAuthor: {user_roles_in_community}")

                # Обновляем роли из новой системы
                user_roles = user_roles_in_community
                is_admin = any(role in ["admin", "super"] for role in user_roles_in_community)

                # Проверяем админские права через email если нет роли админа
                if not is_admin:
                    with local_session() as session:
                        author = session.query(Author).filter(Author.id == user_id_int).first()
                        if author and author.email in ADMIN_EMAILS.split(","):
                            is_admin = True
                            logger.debug(
                                f"[check_auth] Пользователь {author.email} определен как админ через ADMIN_EMAILS"
                            )

            except Exception as e:
                logger.error(f"Ошибка при проверке прав администратора: {e}")

        return user_id, user_roles, is_admin

    async def add_user_role(self, user_id: str, roles: Optional[list[str]] = None) -> Optional[str]:
        """
        Добавление ролей пользователю в локальной БД через CommunityAuthor.
        """
        if not roles:
            roles = ["author", "reader"]

        logger.info(f"Adding roles {roles} to user {user_id}")

        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Невозможно преобразовать user_id {user_id} в число")
            return None

        from orm.community import assign_role_to_user, get_user_roles_in_community

        # Проверяем существующие роли
        existing_roles = get_user_roles_in_community(user_id_int, community_id=1)
        logger.debug(f"Существующие роли пользователя {user_id}: {existing_roles}")

        # Добавляем новые роли через новую систему RBAC
        for role_name in roles:
            if role_name not in existing_roles:
                success = assign_role_to_user(user_id_int, role_name, community_id=1)
                if success:
                    logger.debug(f"Роль {role_name} добавлена пользователю {user_id}")
                else:
                    logger.warning(f"Не удалось добавить роль {role_name} пользователю {user_id}")
            else:
                logger.debug(f"Роль {role_name} уже есть у пользователя {user_id}")

        return user_id

    def create_user(self, user_dict: dict[str, Any], community_id: int | None = None) -> Author:
        """Создает нового пользователя с дефолтными ролями"""
        # Нормализуем email
        if "email" in user_dict:
            user_dict["email"] = user_dict["email"].lower()

        # Проверяем уникальность email
        with local_session() as session:
            existing_user = session.query(Author).filter(Author.email == user_dict["email"]).first()
            if existing_user:
                # Если пользователь с таким email уже существует, возвращаем его
                logger.warning(f"Пользователь с email {user_dict['email']} уже существует")
                return existing_user

        # Генерируем уникальный slug
        base_slug = user_dict.get("slug", generate_unique_slug(user_dict.get("name", user_dict.get("email", "user"))))

        # Проверяем уникальность slug
        with local_session() as session:
            # Добавляем суффикс, если slug уже существует
            counter = 1
            unique_slug = base_slug
            while session.query(Author).filter(Author.slug == unique_slug).first():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1

            user_dict["slug"] = unique_slug

        user = Author(**user_dict)
        target_community_id = int(community_id) if community_id is not None else 1

        with local_session() as session:
            session.add(user)
            session.flush()  # Получаем ID пользователя

            # Получаем сообщество для назначения ролей
            logger.debug(f"Ищем сообщество с ID {target_community_id}")
            community = session.query(Community).filter(Community.id == target_community_id).first()

            # Отладочная информация
            all_communities = session.query(Community).all()
            logger.debug(f"Все сообщества в базе: {[c.id for c in all_communities]}")

            if not community:
                logger.warning(f"Сообщество {target_community_id} не найдено, используем ID=1")
                target_community_id = 1
                community = session.query(Community).filter(Community.id == target_community_id).first()

            if community:
                default_roles = community.get_default_roles() or ["reader", "author"]

                # Создаем CommunityAuthor с ролями
                community_author = CommunityAuthor(
                    community_id=target_community_id,
                    author_id=user.id,
                    roles=",".join(default_roles),
                )
                session.add(community_author)

                # Создаем подписку на сообщество
                follower = CommunityFollower(community=target_community_id, follower=int(user.id))
                session.add(follower)

                logger.info(
                    f"Пользователь {user.id} создан с ролями {default_roles} в сообществе {target_community_id}"
                )
            else:
                # Если сообщество не найдено, вызываем исключение
                raise ValueError("Сообщество не найдено")

            session.commit()
            return user

    async def get_session(self, token: str) -> dict[str, Any]:
        """Получает информацию о текущей сессии по токену"""
        try:
            # Проверяем токен
            payload = JWTCodec.decode(token)
            if not payload:
                return {"success": False, "token": None, "author": None, "error": "Невалидный токен"}

            token_verification = await TokenStorage.verify_session(token)
            if not token_verification:
                return {"success": False, "token": None, "author": None, "error": "Токен истек"}

            user_id = payload.user_id

            # Получаем автора
            author = await get_cached_author_by_id(int(user_id), lambda x: x)
            if not author:
                return {"success": False, "token": None, "author": None, "error": "Пользователь не найден"}

            return {"success": True, "token": token, "author": author, "error": None}

        except Exception as e:
            logger.error(f"Ошибка получения сессии: {e}")
            return {"success": False, "token": None, "author": None, "error": str(e)}

    async def register_user(self, email: str, password: str = "", name: str = "") -> dict[str, Any]:
        """Регистрирует нового пользователя"""
        email = email.lower()
        logger.info(f"Попытка регистрации для {email}")

        with local_session() as session:
            user = session.query(Author).filter(Author.email == email).first()
            if user:
                logger.warning(f"Пользователь {email} уже существует")
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

        new_user = self.create_user(user_dict)

        try:
            await self.send_verification_link(email)
            logger.info(f"Пользователь {email} зарегистрирован, ссылка отправлена")
            return {
                "success": True,
                "token": None,
                "author": new_user,
                "error": "Требуется подтверждение email.",
            }
        except Exception as e:
            logger.error(f"Ошибка отправки ссылки для {email}: {e}")
            return {
                "success": True,
                "token": None,
                "author": new_user,
                "error": f"Пользователь зарегистрирован, но ошибка отправки ссылки: {e}",
            }

    async def send_verification_link(self, email: str, lang: str = "ru", template: str = "confirm") -> Author:
        """Отправляет ссылку подтверждения на email"""
        email = email.lower()
        with local_session() as session:
            user = session.query(Author).filter(Author.email == email).first()
            if not user:
                raise ObjectNotExist("User not found")

            try:
                from auth.tokens.verification import VerificationTokenManager

                verification_manager = VerificationTokenManager()
                token = await verification_manager.create_verification_token(
                    str(user.id), "email_confirmation", {"email": user.email, "template": template}
                )
            except (AttributeError, ImportError):
                token = await TokenStorage.create_session(
                    user_id=str(user.id),
                    username=str(user.username or user.email or user.slug or ""),
                    device_info={"email": user.email} if hasattr(user, "email") else None,
                )

            await send_auth_email(user, token, lang, template)
            return user

    async def confirm_email(self, token: str) -> dict[str, Any]:
        """Подтверждает email по токену"""
        try:
            logger.info("Начало подтверждения email по токену")
            payload = JWTCodec.decode(token)
            if not payload:
                logger.warning("Невалидный токен")
                return {"success": False, "token": None, "author": None, "error": "Невалидный токен"}

            token_verification = await TokenStorage.verify_session(token)
            if not token_verification:
                logger.warning("Токен не найден в системе или истек")
                return {"success": False, "token": None, "author": None, "error": "Токен не найден или истек"}

            user_id = payload.user_id
            username = payload.username

            with local_session() as session:
                user = session.query(Author).where(Author.id == user_id).first()
                if not user:
                    logger.warning(f"Пользователь с ID {user_id} не найден")
                    return {"success": False, "token": None, "author": None, "error": "Пользователь не найден"}

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

                logger.info(f"Email для пользователя {user_id} подтвержден")
                return {"success": True, "token": session_token, "author": user, "error": None}

        except InvalidToken as e:
            logger.warning(f"Невалидный токен - {e.message}")
            return {"success": False, "token": None, "author": None, "error": f"Невалидный токен: {e.message}"}
        except Exception as e:
            logger.error(f"Ошибка подтверждения email: {e}")
            return {"success": False, "token": None, "author": None, "error": f"Ошибка подтверждения email: {e}"}

    async def login(self, email: str, password: str, request=None) -> dict[str, Any]:
        """Авторизация пользователя"""
        email = email.lower()
        logger.info(f"Попытка входа для {email}")

        try:
            with local_session() as session:
                author = session.query(Author).filter(Author.email == email).first()
                if not author:
                    logger.warning(f"Пользователь {email} не найден")
                    return {"success": False, "token": None, "author": None, "error": "Пользователь не найден"}

                # Проверяем роли через новую систему CommunityAuthor
                from orm.community import get_user_roles_in_community

                user_roles = get_user_roles_in_community(int(author.id), community_id=1)
                has_reader_role = "reader" in user_roles

                logger.debug(f"Роли пользователя {email}: {user_roles}")

                if not has_reader_role and author.email not in ADMIN_EMAILS.split(","):
                    logger.warning(f"У пользователя {email} нет роли 'reader'. Текущие роли: {user_roles}")
                    return {
                        "success": False,
                        "token": None,
                        "author": None,
                        "error": "Нет прав для входа. Требуется роль 'reader'.",
                    }

                # Проверяем пароль
                try:
                    valid_author = Identity.password(author, password)
                except (InvalidPassword, Exception) as e:
                    logger.warning(f"Неверный пароль для {email}: {e}")
                    return {"success": False, "token": None, "author": None, "error": str(e)}

                # Создаем токен
                username = str(valid_author.username or valid_author.email or valid_author.slug or "")
                token = await TokenStorage.create_session(
                    user_id=str(valid_author.id),
                    username=username,
                    device_info={"email": valid_author.email} if hasattr(valid_author, "email") else None,
                )

                # Обновляем время входа
                valid_author.last_seen = int(time.time())
                session.commit()

                # Устанавливаем cookie если есть request
                if request and token:
                    self._set_auth_cookie(request, token)

                try:
                    author_dict = valid_author.dict(True)
                except Exception:
                    author_dict = {
                        "id": valid_author.id,
                        "email": valid_author.email,
                        "name": getattr(valid_author, "name", ""),
                        "slug": getattr(valid_author, "slug", ""),
                        "username": getattr(valid_author, "username", ""),
                    }

                logger.info(f"Успешный вход для {email}")
                return {"success": True, "token": token, "author": author_dict, "error": None}

        except Exception as e:
            logger.error(f"Ошибка входа для {email}: {e}")
            return {"success": False, "token": None, "author": None, "error": f"Ошибка авторизации: {e}"}

    def _set_auth_cookie(self, request, token: str) -> bool:
        """Устанавливает cookie аутентификации"""
        try:
            if hasattr(request, "cookies"):
                request.cookies[SESSION_COOKIE_NAME] = token
                return True
        except Exception as e:
            logger.error(f"Ошибка установки cookie: {e}")
        return False

    async def logout(self, user_id: str, token: str = None) -> dict[str, Any]:
        """Выход из системы"""
        try:
            if token:
                await TokenStorage.revoke_session(token)
            logger.info(f"Пользователь {user_id} вышел из системы")
            return {"success": True, "message": "Успешный выход"}
        except Exception as e:
            logger.error(f"Ошибка выхода для {user_id}: {e}")
            return {"success": False, "message": f"Ошибка выхода: {e}"}

    async def refresh_token(self, user_id: str, old_token: str, device_info: dict = None) -> dict[str, Any]:
        """Обновление токена"""
        try:
            new_token = await TokenStorage.refresh_session(int(user_id), old_token, device_info or {})
            if not new_token:
                return {"success": False, "token": None, "author": None, "error": "Не удалось обновить токен"}

            # Получаем данные пользователя
            with local_session() as session:
                author = session.query(Author).filter(Author.id == int(user_id)).first()
                if not author:
                    return {"success": False, "token": None, "author": None, "error": "Пользователь не найден"}

                try:
                    author_dict = author.dict(True)
                except Exception:
                    author_dict = {
                        "id": author.id,
                        "email": author.email,
                        "name": getattr(author, "name", ""),
                        "slug": getattr(author, "slug", ""),
                    }

            return {"success": True, "token": new_token, "author": author_dict, "error": None}

        except Exception as e:
            logger.error(f"Ошибка обновления токена для {user_id}: {e}")
            return {"success": False, "token": None, "author": None, "error": str(e)}

    async def request_password_reset(self, email: str, lang: str = "ru") -> dict[str, Any]:
        """Запрос сброса пароля"""
        try:
            email = email.lower()
            logger.info(f"Запрос сброса пароля для {email}")

            with local_session() as session:
                author = session.query(Author).filter(Author.email == email).first()
                if not author:
                    logger.warning(f"Пользователь {email} не найден")
                    return {"success": True}  # Для безопасности

                try:
                    from auth.tokens.verification import VerificationTokenManager

                    verification_manager = VerificationTokenManager()
                    token = await verification_manager.create_verification_token(
                        str(author.id), "password_reset", {"email": author.email}
                    )
                except (AttributeError, ImportError):
                    token = await TokenStorage.create_session(
                        user_id=str(author.id),
                        username=str(author.username or author.email or author.slug or ""),
                        device_info={"email": author.email} if hasattr(author, "email") else None,
                    )

                await send_auth_email(author, token, lang, "password_reset")
                logger.info(f"Письмо сброса пароля отправлено для {email}")

            return {"success": True}

        except Exception as e:
            logger.error(f"Ошибка запроса сброса пароля для {email}: {e}")
            return {"success": False}

    def is_email_used(self, email: str) -> bool:
        """Проверяет, используется ли email"""
        email = email.lower()
        with local_session() as session:
            user = session.query(Author).filter(Author.email == email).first()
        return user is not None

    async def update_security(
        self, user_id: int, old_password: str, new_password: str = None, email: str = None
    ) -> dict[str, Any]:
        """Обновление пароля и email"""
        try:
            with local_session() as session:
                author = session.query(Author).filter(Author.id == user_id).first()
                if not author:
                    return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

                if not author.verify_password(old_password):
                    return {"success": False, "error": "incorrect old password", "author": None}

                if email and email != author.email:
                    existing_user = session.query(Author).filter(Author.email == email).first()
                    if existing_user:
                        return {"success": False, "error": "email already exists", "author": None}

                changes_made = []

                if new_password:
                    author.set_password(new_password)
                    changes_made.append("password")

                if email and email != author.email:
                    # Создаем запрос на смену email через Redis
                    token = secrets.token_urlsafe(32)
                    email_change_data = {
                        "user_id": user_id,
                        "old_email": author.email,
                        "new_email": email,
                        "token": token,
                        "expires_at": int(time.time()) + 3600,  # 1 час
                    }

                    redis_key = f"email_change:{user_id}"
                    await redis.execute("SET", redis_key, json.dumps(email_change_data))
                    await redis.execute("EXPIRE", redis_key, 3600)

                    changes_made.append("email_pending")
                    logger.info(f"Email смена инициирована для пользователя {user_id}")

                session.commit()
                logger.info(f"Безопасность обновлена для {user_id}: {changes_made}")

                return {"success": True, "error": None, "author": author}

        except Exception as e:
            logger.error(f"Ошибка обновления безопасности для {user_id}: {e}")
            return {"success": False, "error": str(e), "author": None}

    async def confirm_email_change(self, user_id: int, token: str) -> dict[str, Any]:
        """Подтверждение смены email по токену"""
        try:
            # Получаем данные смены email из Redis
            redis_key = f"email_change:{user_id}"
            cached_data = await redis.execute("GET", redis_key)

            if not cached_data:
                return {"success": False, "error": "NO_PENDING_EMAIL", "author": None}

            try:
                email_change_data = json.loads(cached_data)
            except json.JSONDecodeError:
                return {"success": False, "error": "INVALID_TOKEN", "author": None}

            # Проверяем токен
            if email_change_data.get("token") != token:
                return {"success": False, "error": "INVALID_TOKEN", "author": None}

            # Проверяем срок действия
            if email_change_data.get("expires_at", 0) < int(time.time()):
                await redis.execute("DEL", redis_key)
                return {"success": False, "error": "TOKEN_EXPIRED", "author": None}

            new_email = email_change_data.get("new_email")
            if not new_email:
                return {"success": False, "error": "INVALID_TOKEN", "author": None}

            with local_session() as session:
                author = session.query(Author).filter(Author.id == user_id).first()
                if not author:
                    return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

                # Проверяем, что новый email не занят
                existing_user = session.query(Author).filter(Author.email == new_email).first()
                if existing_user and existing_user.id != author.id:
                    await redis.execute("DEL", redis_key)
                    return {"success": False, "error": "email already exists", "author": None}

                # Применяем смену email
                author.email = new_email
                author.email_verified = True
                author.updated_at = int(time.time())

                session.add(author)
                session.commit()

                # Удаляем данные из Redis
                await redis.execute("DEL", redis_key)

                logger.info(f"Email изменен для пользователя {user_id}")
                return {"success": True, "error": None, "author": author}

        except Exception as e:
            logger.error(f"Ошибка подтверждения смены email: {e}")
            return {"success": False, "error": str(e), "author": None}

    async def cancel_email_change(self, user_id: int) -> dict[str, Any]:
        """Отмена смены email"""
        try:
            redis_key = f"email_change:{user_id}"
            cached_data = await redis.execute("GET", redis_key)

            if not cached_data:
                return {"success": False, "error": "NO_PENDING_EMAIL", "author": None}

            # Удаляем данные из Redis
            await redis.execute("DEL", redis_key)

            # Получаем текущие данные пользователя
            with local_session() as session:
                author = session.query(Author).filter(Author.id == user_id).first()
                if not author:
                    return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

                logger.info(f"Смена email отменена для пользователя {user_id}")
                return {"success": True, "error": None, "author": author}

        except Exception as e:
            logger.error(f"Ошибка отмены смены email: {e}")
            return {"success": False, "error": str(e), "author": None}

    async def ensure_user_has_reader_role(self, user_id: int) -> bool:
        """
        Убеждается, что у пользователя есть роль 'reader'.
        Если её нет - добавляет автоматически.

        Args:
            user_id: ID пользователя

        Returns:
            True если роль была добавлена или уже существует
        """
        from orm.community import assign_role_to_user, get_user_roles_in_community

        existing_roles = get_user_roles_in_community(user_id, community_id=1)

        if "reader" not in existing_roles:
            logger.warning(f"У пользователя {user_id} нет роли 'reader'. Добавляем автоматически.")
            success = assign_role_to_user(user_id, "reader", community_id=1)
            if success:
                logger.info(f"Роль 'reader' добавлена пользователю {user_id}")
                return True
            logger.error(f"Не удалось добавить роль 'reader' пользователю {user_id}")
            return False

        return True

    async def fix_all_users_reader_role(self) -> dict[str, int]:
        """
        Проверяет всех пользователей и добавляет роль 'reader' тем, у кого её нет.

        Returns:
            Статистика операции: {"checked": int, "fixed": int, "errors": int}
        """
        stats = {"checked": 0, "fixed": 0, "errors": 0}

        with local_session() as session:
            # Получаем всех пользователей
            all_authors = session.query(Author).all()

            for author in all_authors:
                stats["checked"] += 1

                try:
                    had_reader = await self.ensure_user_has_reader_role(int(author.id))
                    if not had_reader:
                        stats["fixed"] += 1

                except Exception as e:
                    logger.error(f"Ошибка при исправлении ролей для пользователя {author.id}: {e}")
                    stats["errors"] += 1

        logger.info(f"Исправление ролей завершено: {stats}")
        return stats

    def login_required(self, f: Callable) -> Callable:
        """Декоратор для проверки авторизации пользователя. Требуется наличие роли 'reader'."""

        @wraps(f)
        async def decorated_function(*args: Any, **kwargs: Any) -> Any:
            from graphql.error import GraphQLError

            info = args[1]
            req = info.context.get("request")

            logger.debug(
                f"[login_required] Проверка авторизации для запроса: {req.method if req else 'unknown'} {req.url.path if req and hasattr(req, 'url') else 'unknown'}"
            )

            # Извлекаем токен из заголовков
            token = None
            if req:
                headers_dict = dict(req.headers.items())
                for header_name, header_value in headers_dict.items():
                    if header_name.lower() == SESSION_TOKEN_HEADER.lower():
                        token = header_value
                        break

                if token and token.startswith("Bearer "):
                    token = token.split("Bearer ")[-1].strip()

            # Для тестового режима
            if not req and info.context.get("author") and info.context.get("roles"):
                logger.debug("[login_required] Тестовый режим")
                user_id = info.context["author"]["id"]
                user_roles = info.context["roles"]
                is_admin = info.context.get("is_admin", False)
                if not token:
                    token = info.context.get("token")
            else:
                # Обычный режим
                user_id, user_roles, is_admin = await self.check_auth(req)

            if not user_id:
                msg = "Требуется авторизация"
                raise GraphQLError(msg)

            # Проверяем роль reader
            if "reader" not in user_roles and not is_admin:
                msg = "У вас нет необходимых прав для доступа"
                raise GraphQLError(msg)

            logger.info(f"Авторизован пользователь {user_id} с ролями: {user_roles}")
            info.context["roles"] = user_roles
            info.context["is_admin"] = is_admin

            if token:
                info.context["token"] = token

            # Получаем автора если его нет в контексте
            if not info.context.get("author") or not isinstance(info.context["author"], dict):
                author = await get_cached_author_by_id(int(user_id), lambda x: x)
                if not author:
                    logger.error(f"Профиль автора не найден для пользователя {user_id}")
                info.context["author"] = author

            return await f(*args, **kwargs)

        return decorated_function

    def login_accepted(self, f: Callable) -> Callable:
        """Декоратор для добавления данных авторизации в контекст."""

        @wraps(f)
        async def decorated_function(*args: Any, **kwargs: Any) -> Any:
            info = args[1]
            req = info.context.get("request")

            logger.debug("login_accepted: Проверка авторизации пользователя.")
            user_id, user_roles, is_admin = await self.check_auth(req)

            if user_id and user_roles:
                logger.info(f"login_accepted: Пользователь авторизован: {user_id} с ролями {user_roles}")
                info.context["roles"] = user_roles
                info.context["is_admin"] = is_admin

                author = await get_cached_author_by_id(int(user_id), lambda x: x)
                if author:
                    is_owner = True
                    info.context["author"] = author.dict(is_owner or is_admin)
                else:
                    logger.error(f"login_accepted: Профиль автора не найден для пользователя {user_id}")
            else:
                logger.debug("login_accepted: Пользователь не авторизован")
                info.context["roles"] = None
                info.context["author"] = None
                info.context["is_admin"] = False

            return await f(*args, **kwargs)

        return decorated_function


# Синглтон сервиса
auth_service = AuthService()

# Экспортируем функции для обратной совместимости
check_auth = auth_service.check_auth
add_user_role = auth_service.add_user_role
login_required = auth_service.login_required
login_accepted = auth_service.login_accepted
