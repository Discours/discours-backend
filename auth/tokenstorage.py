import json
import secrets
import time
from typing import Any, Dict, Literal, Optional, Union

from auth.jwtcodec import JWTCodec
from auth.validations import AuthInput
from services.redis import redis
from utils.logger import root_logger as logger

# Типы токенов
TokenType = Literal["session", "verification", "oauth_access", "oauth_refresh"]

# TTL по умолчанию для разных типов токенов
DEFAULT_TTL = {
    "session": 30 * 24 * 60 * 60,  # 30 дней
    "verification": 3600,  # 1 час
    "oauth_access": 3600,  # 1 час
    "oauth_refresh": 86400 * 30,  # 30 дней
}


class TokenStorage:
    """
    Единый менеджер всех типов токенов в системе:
    - Токены сессий (session)
    - Токены подтверждения (verification)
    - OAuth токены (oauth_access, oauth_refresh)
    """

    @staticmethod
    def _make_token_key(token_type: TokenType, identifier: str, token: Optional[str] = None) -> str:
        """
        Создает унифицированный ключ для токена

        Args:
            token_type: Тип токена
            identifier: Идентификатор (user_id, user_id:provider, etc)
            token: Сам токен (для session и verification)

        Returns:
            str: Ключ токена
        """
        if token_type == "session":
            return f"session:{token}"
        if token_type == "verification":
            return f"verification_token:{token}"
        if token_type == "oauth_access":
            return f"oauth_access:{identifier}"
        if token_type == "oauth_refresh":
            return f"oauth_refresh:{identifier}"
        raise ValueError(f"Неизвестный тип токена: {token_type}")

    @staticmethod
    def _make_user_tokens_key(user_id: str, token_type: TokenType) -> str:
        """Создает ключ для списка токенов пользователя"""
        return f"user_tokens:{user_id}:{token_type}"

    @classmethod
    async def create_token(
        cls,
        token_type: TokenType,
        user_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
        token: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> str:
        """
        Универсальный метод создания токена любого типа

        Args:
            token_type: Тип токена
            user_id: ID пользователя
            data: Данные токена
            ttl: Время жизни (по умолчанию из DEFAULT_TTL)
            token: Существующий токен (для verification)
            provider: OAuth провайдер (для oauth токенов)

        Returns:
            str: Токен или ключ токена
        """
        if ttl is None:
            ttl = DEFAULT_TTL[token_type]

        # Подготавливаем данные токена
        token_data = {"user_id": user_id, "token_type": token_type, "created_at": int(time.time()), **data}

        if token_type == "session":
            # Генерируем новый токен сессии
            session_token = cls.generate_token()
            token_key = cls._make_token_key(token_type, user_id, session_token)

            # Сохраняем данные сессии
            for field, value in token_data.items():
                await redis.hset(token_key, field, str(value))
            await redis.expire(token_key, ttl)

            # Добавляем в список сессий пользователя
            user_tokens_key = cls._make_user_tokens_key(user_id, token_type)
            await redis.sadd(user_tokens_key, session_token)
            await redis.expire(user_tokens_key, ttl)

            logger.info(f"Создан токен сессии для пользователя {user_id}")
            return session_token

        if token_type == "verification":
            # Используем переданный токен или генерируем новый
            verification_token = token or secrets.token_urlsafe(32)
            token_key = cls._make_token_key(token_type, user_id, verification_token)

            # Отменяем предыдущие токены того же типа
            verification_type = data.get("verification_type", "unknown")
            await cls._cancel_verification_tokens(user_id, verification_type)

            # Сохраняем токен подтверждения
            await redis.serialize_and_set(token_key, token_data, ex=ttl)

            logger.info(f"Создан токен подтверждения {verification_type} для пользователя {user_id}")
            return verification_token

        if token_type in ["oauth_access", "oauth_refresh"]:
            if not provider:
                raise ValueError("OAuth токены требуют указания провайдера")

            identifier = f"{user_id}:{provider}"
            token_key = cls._make_token_key(token_type, identifier)

            # Добавляем провайдера в данные
            token_data["provider"] = provider

            # Сохраняем OAuth токен
            await redis.serialize_and_set(token_key, token_data, ex=ttl)

            logger.info(f"Создан {token_type} токен для пользователя {user_id}, провайдер {provider}")
            return token_key

        raise ValueError(f"Неподдерживаемый тип токена: {token_type}")

    @classmethod
    async def get_token_data(
        cls,
        token_type: TokenType,
        token_or_identifier: str,
        user_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Универсальный метод получения данных токена

        Args:
            token_type: Тип токена
            token_or_identifier: Токен или идентификатор
            user_id: ID пользователя (для OAuth)
            provider: OAuth провайдер

        Returns:
            Dict с данными токена или None
        """
        try:
            if token_type == "session":
                token_key = cls._make_token_key(token_type, "", token_or_identifier)
                token_data = await redis.hgetall(token_key)
                if token_data:
                    # Обновляем время последней активности
                    await redis.hset(token_key, "last_activity", str(int(time.time())))
                    return {k: v for k, v in token_data.items()}
                return None

            if token_type == "verification":
                token_key = cls._make_token_key(token_type, "", token_or_identifier)
                return await redis.get_and_deserialize(token_key)

            if token_type in ["oauth_access", "oauth_refresh"]:
                if not user_id or not provider:
                    raise ValueError("OAuth токены требуют user_id и provider")

                identifier = f"{user_id}:{provider}"
                token_key = cls._make_token_key(token_type, identifier)
                token_data = await redis.get_and_deserialize(token_key)

                if token_data:
                    # Добавляем информацию о TTL
                    ttl = await redis.execute("TTL", token_key)
                    if ttl > 0:
                        token_data["ttl_remaining"] = ttl
                return token_data

            return None

        except Exception as e:
            logger.error(f"Ошибка получения токена {token_type}: {e}")
            return None

    @classmethod
    async def validate_token(
        cls, token: str, token_type: Optional[TokenType] = None
    ) -> tuple[bool, Optional[dict[str, Any]]]:
        """
        Проверяет валидность токена

        Args:
            token: Токен для проверки
            token_type: Тип токена (если не указан - определяется автоматически)

        Returns:
            Tuple[bool, Dict]: (Валиден ли токен, данные токена)
        """
        try:
            # Для JWT токенов (сессии) - декодируем
            if not token_type or token_type == "session":
                payload = JWTCodec.decode(token)
                if payload:
                    user_id = payload.user_id
                    username = payload.username

                    # Проверяем в разных форматах для совместимости
                    old_token_key = f"{user_id}-{username}-{token}"
                    new_token_key = cls._make_token_key("session", user_id, token)

                    old_exists = await redis.exists(old_token_key)
                    new_exists = await redis.exists(new_token_key)

                    if old_exists or new_exists:
                        # Получаем данные из актуального хранилища
                        if new_exists:
                            token_data = await redis.hgetall(new_token_key)
                        else:
                            token_data = await redis.hgetall(old_token_key)
                            # Миграция в новый формат
                            if not new_exists:
                                for field, value in token_data.items():
                                    await redis.hset(new_token_key, field, value)
                                await redis.expire(new_token_key, DEFAULT_TTL["session"])

                        return True, {k: v for k, v in token_data.items()}

            # Для токенов подтверждения - прямая проверка
            if not token_type or token_type == "verification":
                token_key = cls._make_token_key("verification", "", token)
                token_data = await redis.get_and_deserialize(token_key)
                if token_data:
                    return True, token_data

            return False, None

        except Exception as e:
            logger.error(f"Ошибка валидации токена: {e}")
            return False, None

    @classmethod
    async def revoke_token(
        cls,
        token_type: TokenType,
        token_or_identifier: str,
        user_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> bool:
        """
        Универсальный метод отзыва токена

        Args:
            token_type: Тип токена
            token_or_identifier: Токен или идентификатор
            user_id: ID пользователя
            provider: OAuth провайдер

        Returns:
            bool: Успех операции
        """
        try:
            if token_type == "session":
                # Декодируем JWT для получения данных
                payload = JWTCodec.decode(token_or_identifier)
                if payload:
                    user_id = payload.user_id
                    username = payload.username

                    # Удаляем в обоих форматах
                    old_token_key = f"{user_id}-{username}-{token_or_identifier}"
                    new_token_key = cls._make_token_key(token_type, user_id, token_or_identifier)
                    user_tokens_key = cls._make_user_tokens_key(user_id, token_type)

                    result1 = await redis.delete(old_token_key)
                    result2 = await redis.delete(new_token_key)
                    result3 = await redis.srem(user_tokens_key, token_or_identifier)

                    return result1 > 0 or result2 > 0 or result3 > 0

            elif token_type == "verification":
                token_key = cls._make_token_key(token_type, "", token_or_identifier)
                result = await redis.delete(token_key)
                return result > 0

            elif token_type in ["oauth_access", "oauth_refresh"]:
                if not user_id or not provider:
                    raise ValueError("OAuth токены требуют user_id и provider")

                identifier = f"{user_id}:{provider}"
                token_key = cls._make_token_key(token_type, identifier)
                result = await redis.delete(token_key)
                return result > 0

            return False

        except Exception as e:
            logger.error(f"Ошибка отзыва токена {token_type}: {e}")
            return False

    @classmethod
    async def revoke_user_tokens(cls, user_id: str, token_type: Optional[TokenType] = None) -> int:
        """
        Отзывает все токены пользователя определенного типа или все

        Args:
            user_id: ID пользователя
            token_type: Тип токенов для отзыва (None = все типы)

        Returns:
            int: Количество отозванных токенов
        """
        count = 0

        try:
            types_to_revoke = (
                [token_type] if token_type else ["session", "verification", "oauth_access", "oauth_refresh"]
            )

            for t_type in types_to_revoke:
                if t_type == "session":
                    user_tokens_key = cls._make_user_tokens_key(user_id, t_type)
                    tokens = await redis.smembers(user_tokens_key)

                    for token in tokens:
                        token_str = token.decode("utf-8") if isinstance(token, bytes) else str(token)
                        success = await cls.revoke_token(t_type, token_str, user_id)
                        if success:
                            count += 1

                    await redis.delete(user_tokens_key)

                elif t_type == "verification":
                    # Ищем все токены подтверждения пользователя
                    pattern = "verification_token:*"
                    keys = await redis.keys(pattern)

                    for key in keys:
                        token_data = await redis.get_and_deserialize(key)
                        if token_data and token_data.get("user_id") == user_id:
                            await redis.delete(key)
                            count += 1

                elif t_type in ["oauth_access", "oauth_refresh"]:
                    # Ищем OAuth токены по паттерну
                    pattern = f"{t_type}:{user_id}:*"
                    keys = await redis.keys(pattern)

                    for key in keys:
                        await redis.delete(key)
                        count += 1

            logger.info(f"Отозвано {count} токенов для пользователя {user_id}")
            return count

        except Exception as e:
            logger.error(f"Ошибка отзыва токенов пользователя: {e}")
            return count

    @staticmethod
    async def _cancel_verification_tokens(user_id: str, verification_type: str) -> None:
        """Отменяет предыдущие токены подтверждения определенного типа"""
        try:
            pattern = "verification_token:*"
            keys = await redis.keys(pattern)

            for key in keys:
                token_data = await redis.get_and_deserialize(key)
                if (
                    token_data
                    and token_data.get("user_id") == user_id
                    and token_data.get("verification_type") == verification_type
                ):
                    await redis.delete(key)

        except Exception as e:
            logger.error(f"Ошибка отмены токенов подтверждения: {e}")

    # === УДОБНЫЕ МЕТОДЫ ДЛЯ СЕССИЙ ===

    @classmethod
    async def create_session(
        cls,
        user_id: str,
        auth_data: Optional[dict] = None,
        username: Optional[str] = None,
        device_info: Optional[dict] = None,
    ) -> str:
        """Создает токен сессии"""
        session_data = {}

        if auth_data:
            session_data["auth_data"] = json.dumps(auth_data)
        if username:
            session_data["username"] = username
        if device_info:
            session_data["device_info"] = json.dumps(device_info)

        return await cls.create_token("session", user_id, session_data)

    @classmethod
    async def get_session_data(cls, token: str) -> Optional[Dict[str, Any]]:
        """Получает данные сессии"""
        valid, data = await cls.validate_token(token, "session")
        return data if valid else None

    # === УДОБНЫЕ МЕТОДЫ ДЛЯ ТОКЕНОВ ПОДТВЕРЖДЕНИЯ ===

    @classmethod
    async def create_verification_token(
        cls,
        user_id: str,
        verification_type: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> str:
        """Создает токен подтверждения"""
        token_data = {"verification_type": verification_type, **data}

        # TTL по типу подтверждения
        if ttl is None:
            verification_ttls = {
                "email_change": 3600,  # 1 час
                "phone_change": 600,  # 10 минут
                "password_reset": 1800,  # 30 минут
            }
            ttl = verification_ttls.get(verification_type, 3600)

        return await cls.create_token("verification", user_id, token_data, ttl)

    @classmethod
    async def confirm_verification_token(cls, token_str: str) -> Optional[Dict[str, Any]]:
        """Подтверждает и использует токен подтверждения (одноразовый)"""
        token_data = await cls.get_token_data("verification", token_str)
        if token_data:
            # Удаляем токен после использования
            await cls.revoke_token("verification", token_str)
            return token_data
        return None

    # === УДОБНЫЕ МЕТОДЫ ДЛЯ OAUTH ТОКЕНОВ ===

    @classmethod
    async def store_oauth_tokens(
        cls,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Сохраняет OAuth токены"""
        try:
            # Сохраняем access token
            access_data = {
                "token": access_token,
                "provider": provider,
                "expires_in": expires_in,
                **(additional_data or {}),
            }

            access_ttl = expires_in if expires_in else DEFAULT_TTL["oauth_access"]
            await cls.create_token("oauth_access", user_id, access_data, access_ttl, provider=provider)

            # Сохраняем refresh token если есть
            if refresh_token:
                refresh_data = {
                    "token": refresh_token,
                    "provider": provider,
                }
                await cls.create_token("oauth_refresh", user_id, refresh_data, provider=provider)

            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения OAuth токенов: {e}")
            return False

    @classmethod
    async def get_oauth_token(cls, user_id: int, provider: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Получает OAuth токен"""
        oauth_type = f"oauth_{token_type}"
        if oauth_type in ["oauth_access", "oauth_refresh"]:
            return await cls.get_token_data(oauth_type, "", user_id, provider)  # type: ignore[arg-type]
        return None

    @classmethod
    async def revoke_oauth_tokens(cls, user_id: str, provider: str) -> bool:
        """Удаляет все OAuth токены для провайдера"""
        try:
            result1 = await cls.revoke_token("oauth_access", "", user_id, provider)
            result2 = await cls.revoke_token("oauth_refresh", "", user_id, provider)
            return result1 or result2
        except Exception as e:
            logger.error(f"Ошибка удаления OAuth токенов: {e}")
            return False

    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===

    @staticmethod
    def generate_token() -> str:
        """Генерирует криптографически стойкий токен"""
        return secrets.token_urlsafe(32)

    @staticmethod
    async def cleanup_expired_tokens() -> int:
        """Очищает истекшие токены (Redis делает это автоматически)"""
        # Redis автоматически удаляет истекшие ключи
        # Здесь можем очистить связанные структуры данных
        try:
            user_session_keys = await redis.keys("user_tokens:*:session")
            cleaned_count = 0

            for user_tokens_key in user_session_keys:
                tokens = await redis.smembers(user_tokens_key)
                active_tokens = []

                for token in tokens:
                    token_str = token.decode("utf-8") if isinstance(token, bytes) else str(token)
                    session_key = f"session:{token_str}"
                    exists = await redis.exists(session_key)
                    if exists:
                        active_tokens.append(token_str)
                    else:
                        cleaned_count += 1

                # Обновляем список активных токенов
                if active_tokens:
                    await redis.delete(user_tokens_key)
                    for token in active_tokens:
                        await redis.sadd(user_tokens_key, token)
                else:
                    await redis.delete(user_tokens_key)

            if cleaned_count > 0:
                logger.info(f"Очищено {cleaned_count} ссылок на истекшие токены")

            return cleaned_count

        except Exception as e:
            logger.error(f"Ошибка очистки токенов: {e}")
            return 0

    # === ОБРАТНАЯ СОВМЕСТИМОСТЬ ===

    @staticmethod
    async def get(token_key: str) -> Optional[str]:
        """Обратная совместимость - получение токена по ключу"""
        result = await redis.get(token_key)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return result

    @staticmethod
    async def save_token(token_key: str, token_data: Dict[str, Any], life_span: int = 3600) -> bool:
        """Обратная совместимость - сохранение токена"""
        try:
            return await redis.serialize_and_set(token_key, token_data, ex=life_span)
        except Exception as e:
            logger.error(f"Ошибка сохранения токена {token_key}: {e}")
            return False

    @staticmethod
    async def get_token(token_key: str) -> Optional[Dict[str, Any]]:
        """Обратная совместимость - получение данных токена"""
        try:
            return await redis.get_and_deserialize(token_key)
        except Exception as e:
            logger.error(f"Ошибка получения токена {token_key}: {e}")
            return None

    @staticmethod
    async def delete_token(token_key: str) -> bool:
        """Обратная совместимость - удаление токена"""
        try:
            result = await redis.delete(token_key)
            return result > 0
        except Exception as e:
            logger.error(f"Ошибка удаления токена {token_key}: {e}")
            return False

    # Остальные методы для обратной совместимости...
    async def exists(self, token_key: str) -> bool:
        """Совместимость - проверка существования"""
        return bool(await redis.exists(token_key))

    async def invalidate_token(self, token: str) -> bool:
        """Совместимость - инвалидация токена"""
        return await self.revoke_token("session", token)

    async def invalidate_all_tokens(self, user_id: str) -> int:
        """Совместимость - инвалидация всех токенов"""
        return await self.revoke_user_tokens(user_id)

    def generate_session_token(self) -> str:
        """Совместимость - генерация токена сессии"""
        return self.generate_token()

    async def get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Совместимость - получение сессии"""
        return await self.get_session_data(session_token)

    async def revoke_session(self, session_token: str) -> bool:
        """Совместимость - отзыв сессии"""
        return await self.revoke_token("session", session_token)

    async def revoke_all_user_sessions(self, user_id: Union[int, str]) -> bool:
        """Совместимость - отзыв всех сессий"""
        count = await self.revoke_user_tokens(str(user_id), "session")
        return count > 0

    async def get_user_sessions(self, user_id: Union[int, str]) -> list[Dict[str, Any]]:
        """Совместимость - получение сессий пользователя"""
        try:
            user_tokens_key = f"user_tokens:{user_id}:session"
            tokens = await redis.smembers(user_tokens_key)

            sessions = []
            for token in tokens:
                token_str = token.decode("utf-8") if isinstance(token, bytes) else str(token)
                session_data = await self.get_session_data(token_str)
                if session_data:
                    session_data["token"] = token_str
                    sessions.append(session_data)

            return sessions

        except Exception as e:
            logger.error(f"Ошибка получения сессий пользователя: {e}")
            return []

    async def revoke_all_tokens_for_user(self, user: AuthInput) -> bool:
        """Совместимость - отзыв всех токенов пользователя"""
        user_id = getattr(user, "id", 0) or 0
        count = await self.revoke_user_tokens(str(user_id))
        return count > 0

    async def get_one_time_token_value(self, token_key: str) -> Optional[str]:
        """Совместимость - одноразовые токены"""
        token_data = await self.get_token(token_key)
        if token_data and token_data.get("valid"):
            return "TRUE"
        return None

    async def save_one_time_token(self, user: AuthInput, one_time_token: str, life_span: int = 300) -> bool:
        """Совместимость - сохранение одноразового токена"""
        user_id = getattr(user, "id", 0) or 0
        token_key = f"{user_id}-{user.username}-{one_time_token}"
        token_data = {"valid": True, "user_id": user_id, "username": user.username}
        return await self.save_token(token_key, token_data, life_span)

    async def extend_token_lifetime(self, token_key: str, additional_seconds: int = 3600) -> bool:
        """Совместимость - продление времени жизни"""
        token_data = await self.get_token(token_key)
        if not token_data:
            return False
        return await self.save_token(token_key, token_data, additional_seconds)

    async def cleanup_expired_sessions(self) -> None:
        """Совместимость - очистка сессий"""
        await self.cleanup_expired_tokens()
