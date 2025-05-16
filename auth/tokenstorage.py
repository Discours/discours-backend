from datetime import datetime, timedelta, timezone
import json
from typing import Dict, Any, Optional

from auth.jwtcodec import JWTCodec
from auth.validations import AuthInput
from services.redis import redis
from settings import ONETIME_TOKEN_LIFE_SPAN, SESSION_TOKEN_LIFE_SPAN
from utils.logger import root_logger as logger


class TokenStorage:
    """
    Хранилище токенов в Redis.
    Обеспечивает создание, проверку и отзыв токенов.
    """

    @staticmethod
    async def get(token_key: str) -> Optional[str]:
        """
        Получает токен из хранилища.

        Args:
            token_key: Ключ токена

        Returns:
            str или None, если токен не найден
        """
        logger.debug(f"[tokenstorage.get] Запрос токена: {token_key}")
        return await redis.get(token_key)

    @staticmethod
    async def exists(token_key: str) -> bool:
        """
        Проверяет наличие токена в хранилище.

        Args:
            token_key: Ключ токена

        Returns:
            bool: True, если токен существует
        """
        return bool(await redis.execute("EXISTS", token_key))

    @staticmethod
    async def save_token(token_key: str, data: Dict[str, Any], life_span: int) -> bool:
        """
        Сохраняет токен в хранилище с указанным временем жизни.

        Args:
            token_key: Ключ токена
            data: Данные токена
            life_span: Время жизни токена в секундах

        Returns:
            bool: True, если токен успешно сохранен
        """
        try:
            # Если данные не строка, преобразуем их в JSON
            value = json.dumps(data) if isinstance(data, dict) else data

            # Сохраняем токен и устанавливаем время жизни
            await redis.set(token_key, value, ex=life_span)

            return True
        except Exception as e:
            logger.error(f"[tokenstorage.save_token] Ошибка сохранения токена: {str(e)}")
            return False

    @staticmethod
    async def create_onetime(user: AuthInput) -> str:
        """
        Создает одноразовый токен для пользователя.

        Args:
            user: Объект пользователя

        Returns:
            str: Сгенерированный токен
        """
        life_span = ONETIME_TOKEN_LIFE_SPAN
        exp = datetime.now(tz=timezone.utc) + timedelta(seconds=life_span)
        one_time_token = JWTCodec.encode(user, exp)

        # Сохраняем токен в Redis
        token_key = f"{user.id}-{user.username}-{one_time_token}"
        await TokenStorage.save_token(token_key, "TRUE", life_span)

        return one_time_token

    @staticmethod
    async def create_session(user: AuthInput) -> str:
        """
        Создает сессионный токен для пользователя.

        Args:
            user: Объект пользователя

        Returns:
            str: Сгенерированный токен
        """
        life_span = SESSION_TOKEN_LIFE_SPAN
        exp = datetime.now(tz=timezone.utc) + timedelta(seconds=life_span)
        session_token = JWTCodec.encode(user, exp)

        # Сохраняем токен в Redis
        token_key = f"{user.id}-{user.username}-{session_token}"
        user_sessions_key = f"user_sessions:{user.id}"

        # Создаем данные сессии
        session_data = {
            "user_id": str(user.id),
            "username": user.username,
            "created_at": datetime.now(tz=timezone.utc).timestamp(),
            "expires_at": exp.timestamp(),
        }

        # Сохраняем токен и добавляем его в список сессий пользователя
        pipe = redis.pipeline()
        await pipe.hmset(token_key, session_data)
        await pipe.expire(token_key, life_span)
        await pipe.sadd(user_sessions_key, session_token)
        await pipe.expire(user_sessions_key, life_span)
        await pipe.execute()

        return session_token

    @staticmethod
    async def revoke(token: str) -> bool:
        """
        Отзывает токен.

        Args:
            token: Токен для отзыва

        Returns:
            bool: True, если токен успешно отозван
        """
        try:
            logger.debug("[tokenstorage.revoke] Отзыв токена")

            # Декодируем токен
            payload = JWTCodec.decode(token)
            if not payload:
                logger.warning("[tokenstorage.revoke] Невозможно декодировать токен")
                return False

            # Формируем ключи
            token_key = f"{payload.user_id}-{payload.username}-{token}"
            user_sessions_key = f"user_sessions:{payload.user_id}"

            # Удаляем токен и запись из списка сессий пользователя
            pipe = redis.pipeline()
            await pipe.delete(token_key)
            await pipe.srem(user_sessions_key, token)
            await pipe.execute()

            return True
        except Exception as e:
            logger.error(f"[tokenstorage.revoke] Ошибка отзыва токена: {str(e)}")
            return False

    @staticmethod
    async def revoke_all(user: AuthInput) -> bool:
        """
        Отзывает все токены пользователя.

        Args:
            user: Объект пользователя

        Returns:
            bool: True, если все токены успешно отозваны
        """
        try:
            # Формируем ключи
            user_sessions_key = f"user_sessions:{user.id}"

            # Получаем все токены пользователя
            tokens = await redis.smembers(user_sessions_key)
            if not tokens:
                return True

            # Формируем список ключей для удаления
            keys_to_delete = [f"{user.id}-{user.username}-{token}" for token in tokens]
            keys_to_delete.append(user_sessions_key)

            # Удаляем все токены и список сессий
            await redis.delete(*keys_to_delete)

            return True
        except Exception as e:
            logger.error(f"[tokenstorage.revoke_all] Ошибка отзыва всех токенов: {str(e)}")
            return False
