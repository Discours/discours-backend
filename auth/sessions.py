from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from pydantic import BaseModel
from services.redis import redis
from auth.jwtcodec import JWTCodec, TokenPayload
from settings import SESSION_TOKEN_LIFE_SPAN
from utils.logger import root_logger as logger


class SessionData(BaseModel):
    """Модель данных сессии"""

    user_id: str
    username: str
    created_at: datetime
    expires_at: datetime
    device_info: Optional[dict] = None


class SessionManager:
    """
    Менеджер сессий в Redis.
    Управляет созданием, проверкой и отзывом сессий пользователей.
    """

    @staticmethod
    def _make_session_key(user_id: str, token: str) -> str:
        """Формирует ключ сессии в Redis"""
        return f"session:{user_id}:{token}"

    @staticmethod
    def _make_user_sessions_key(user_id: str) -> str:
        """Формирует ключ для списка сессий пользователя в Redis"""
        return f"user_sessions:{user_id}"

    @classmethod
    async def create_session(cls, user_id: str, username: str, device_info: dict = None) -> str:
        """
        Создает новую сессию для пользователя.

        Args:
            user_id: ID пользователя
            username: Имя пользователя/логин
            device_info: Информация об устройстве (опционально)

        Returns:
            str: Токен сессии
        """
        try:
            # Создаем JWT токен
            exp = datetime.now(tz=timezone.utc) + timedelta(seconds=SESSION_TOKEN_LIFE_SPAN)
            session_token = JWTCodec.encode({"id": user_id, "email": username}, exp)

            # Создаем данные сессии
            session_data = SessionData(
                user_id=user_id,
                username=username,
                created_at=datetime.now(tz=timezone.utc),
                expires_at=exp,
                device_info=device_info,
            )

            # Ключи в Redis
            session_key = cls._make_session_key(user_id, session_token)
            user_sessions_key = cls._make_user_sessions_key(user_id)

            # Сохраняем в Redis
            pipe = redis.pipeline()
            await pipe.hset(session_key, mapping=session_data.dict())
            await pipe.expire(session_key, SESSION_TOKEN_LIFE_SPAN)
            await pipe.sadd(user_sessions_key, session_token)
            await pipe.expire(user_sessions_key, SESSION_TOKEN_LIFE_SPAN)
            await pipe.execute()

            return session_token
        except Exception as e:
            logger.error(f"[SessionManager.create_session] Ошибка: {str(e)}")
            raise

    @classmethod
    async def verify_session(cls, token: str) -> Optional[TokenPayload]:
        """
        Проверяет валидность сессии.

        Args:
            token: Токен сессии

        Returns:
            TokenPayload: Данные токена или None, если токен недействителен
        """
        try:
            # Декодируем JWT
            payload = JWTCodec.decode(token)

            # Формируем ключ сессии
            session_key = cls._make_session_key(payload.user_id, token)

            # Проверяем существование сессии в Redis
            session_exists = await redis.exists(session_key)
            if not session_exists:
                logger.debug(f"[SessionManager.verify_session] Сессия не найдена: {payload.user_id}")
                return None

            return payload

        except Exception as e:
            logger.error(f"[SessionManager.verify_session] Ошибка: {str(e)}")
            return None

    @classmethod
    async def get_session_data(cls, user_id: str, token: str) -> Optional[Dict[str, Any]]:
        """
        Получает данные сессии.

        Args:
            user_id: ID пользователя
            token: Токен сессии

        Returns:
            dict: Данные сессии или None, если сессия не найдена
        """
        try:
            session_key = cls._make_session_key(user_id, token)
            session_data = await redis.hgetall(session_key)
            return session_data if session_data else None
        except Exception as e:
            logger.error(f"[SessionManager.get_session_data] Ошибка: {str(e)}")
            return None

    @classmethod
    async def revoke_session(cls, user_id: str, token: str) -> bool:
        """
        Отзывает конкретную сессию.

        Args:
            user_id: ID пользователя
            token: Токен сессии

        Returns:
            bool: True, если сессия успешно отозвана
        """
        try:
            session_key = cls._make_session_key(user_id, token)
            user_sessions_key = cls._make_user_sessions_key(user_id)

            # Удаляем сессию и запись из списка сессий пользователя
            pipe = redis.pipeline()
            await pipe.delete(session_key)
            await pipe.srem(user_sessions_key, token)
            await pipe.execute()
            return True
        except Exception as e:
            logger.error(f"[SessionManager.revoke_session] Ошибка: {str(e)}")
            return False

    @classmethod
    async def revoke_all_sessions(cls, user_id: str) -> bool:
        """
        Отзывает все сессии пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            bool: True, если все сессии успешно отозваны
        """
        try:
            user_sessions_key = cls._make_user_sessions_key(user_id)

            # Получаем все токены пользователя
            tokens = await redis.smembers(user_sessions_key)
            if not tokens:
                return True

            # Создаем команды для удаления всех сессий
            pipe = redis.pipeline()

            # Формируем список ключей для удаления
            for token in tokens:
                session_key = cls._make_session_key(user_id, token)
                await pipe.delete(session_key)

            # Удаляем список сессий
            await pipe.delete(user_sessions_key)
            await pipe.execute()

            return True
        except Exception as e:
            logger.error(f"[SessionManager.revoke_all_sessions] Ошибка: {str(e)}")
            return False

    @classmethod
    async def refresh_session(cls, user_id: str, old_token: str, device_info: dict = None) -> Optional[str]:
        """
        Обновляет сессию пользователя, заменяя старый токен новым.

        Args:
            user_id: ID пользователя
            old_token: Старый токен сессии
            device_info: Информация об устройстве (опционально)

        Returns:
            str: Новый токен сессии или None в случае ошибки
        """
        try:
            # Получаем данные старой сессии
            old_session_key = cls._make_session_key(user_id, old_token)
            old_session_data = await redis.hgetall(old_session_key)

            if not old_session_data:
                logger.warning(f"[SessionManager.refresh_session] Сессия не найдена: {user_id}")
                return None

            # Используем старые данные устройства, если новые не предоставлены
            if not device_info and "device_info" in old_session_data:
                device_info = old_session_data.get("device_info")

            # Создаем новую сессию
            new_token = await cls.create_session(user_id, old_session_data.get("username", ""), device_info)

            # Отзываем старую сессию
            await cls.revoke_session(user_id, old_token)

            return new_token
        except Exception as e:
            logger.error(f"[SessionManager.refresh_session] Ошибка: {str(e)}")
            return None
