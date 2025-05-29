from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from auth.jwtcodec import JWTCodec, TokenPayload
from services.redis import redis
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
        """
        Создаёт ключ для сессии в Redis.

        Args:
            user_id: ID пользователя
            token: JWT токен сессии

        Returns:
            str: Ключ сессии
        """
        session_key = f"session:{user_id}:{token}"
        logger.debug(f"[SessionManager._make_session_key] Сформирован ключ сессии: {session_key}")
        return session_key

    @staticmethod
    def _make_user_sessions_key(user_id: str) -> str:
        """
        Создаёт ключ для списка активных сессий пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            str: Ключ списка сессий
        """
        return f"user_sessions:{user_id}"

    @classmethod
    async def create_session(cls, user_id: str, username: str, device_info: Optional[dict] = None) -> str:
        """
        Создаёт новую сессию.

        Args:
            user_id: ID пользователя
            username: Имя пользователя
            device_info: Информация об устройстве (опционально)

        Returns:
            str: JWT токен сессии
        """
        # Создаём токен с явным указанием срока действия (30 дней)
        expiration_date = datetime.now(tz=timezone.utc) + timedelta(days=30)
        token = JWTCodec.encode({"id": user_id, "email": username}, exp=expiration_date)

        # Сохраняем сессию в Redis
        session_key = cls._make_session_key(user_id, token)
        user_sessions_key = cls._make_user_sessions_key(user_id)

        # Сохраняем информацию о сессии
        session_data = {
            "user_id": user_id,
            "username": username,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "expires_at": expiration_date.isoformat(),
        }

        # Добавляем информацию об устройстве, если она есть
        if device_info:
            for key, value in device_info.items():
                session_data[f"device_{key}"] = value

        # Сохраняем сессию в Redis
        pipeline = redis.pipeline()
        # Сохраняем данные сессии
        pipeline.hset(session_key, mapping=session_data)
        # Добавляем токен в список сессий пользователя
        pipeline.sadd(user_sessions_key, token)
        # Устанавливаем время жизни ключей (30 дней)
        pipeline.expire(session_key, 30 * 24 * 60 * 60)
        pipeline.expire(user_sessions_key, 30 * 24 * 60 * 60)

        # Также создаем ключ в формате, совместимом с TokenStorage для обратной совместимости
        token_key = f"{user_id}-{username}-{token}"
        pipeline.hset(token_key, mapping={"user_id": user_id, "username": username})
        pipeline.expire(token_key, 30 * 24 * 60 * 60)

        result = await pipeline.execute()
        logger.info(f"[SessionManager.create_session] Сессия успешно создана для пользователя {user_id}")

        return token

    @classmethod
    async def verify_session(cls, token: str) -> Optional[TokenPayload]:
        """
        Проверяет сессию по токену.

        Args:
            token: JWT токен

        Returns:
            Optional[TokenPayload]: Данные токена или None, если сессия недействительна
        """
        logger.debug(f"[SessionManager.verify_session] Проверка сессии для токена: {token[:20]}...")

        # Декодируем токен для получения payload
        try:
            payload = JWTCodec.decode(token)
            if not payload:
                logger.error("[SessionManager.verify_session] Не удалось декодировать токен")
                return None

            logger.debug(f"[SessionManager.verify_session] Успешно декодирован токен, user_id={payload.user_id}")
        except Exception as e:
            logger.error(f"[SessionManager.verify_session] Ошибка при декодировании токена: {str(e)}")
            return None

        # Получаем данные из payload
        user_id = payload.user_id

        # Формируем ключ сессии
        session_key = cls._make_session_key(user_id, token)
        logger.debug(f"[SessionManager.verify_session] Сформирован ключ сессии: {session_key}")

        # Проверяем существование сессии в Redis
        exists = await redis.exists(session_key)
        if not exists:
            logger.warning(f"[SessionManager.verify_session] Сессия не найдена: {user_id}. Ключ: {session_key}")

            # Проверяем также ключ в старом формате TokenStorage для обратной совместимости
            token_key = f"{user_id}-{payload.username}-{token}"
            old_format_exists = await redis.exists(token_key)

            if old_format_exists:
                logger.info(f"[SessionManager.verify_session] Найдена сессия в старом формате: {token_key}")

                # Миграция: создаем запись в новом формате
                session_data = {
                    "user_id": user_id,
                    "username": payload.username,
                }

                # Копируем сессию в новый формат
                pipeline = redis.pipeline()
                pipeline.hset(session_key, mapping=session_data)
                pipeline.expire(session_key, 30 * 24 * 60 * 60)
                pipeline.sadd(cls._make_user_sessions_key(user_id), token)
                await pipeline.execute()

                logger.info(f"[SessionManager.verify_session] Сессия мигрирована в новый формат: {session_key}")
                return payload

            # Если сессия не найдена ни в новом, ни в старом формате, проверяем все ключи в Redis
            keys = await redis.keys("session:*")
            logger.debug(f"[SessionManager.verify_session] Все ключи сессий в Redis: {keys}")

            # Проверяем, можно ли доверять токену напрямую
            # Если токен валидный и не истек, мы можем доверять ему даже без записи в Redis
            if payload and payload.exp and payload.exp > datetime.now(tz=timezone.utc):
                logger.info(f"[SessionManager.verify_session] Токен валиден по JWT, создаем сессию для {user_id}")

                # Создаем сессию на основе валидного токена
                session_data = {
                    "user_id": user_id,
                    "username": payload.username,
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                    "expires_at": payload.exp.isoformat()
                    if isinstance(payload.exp, datetime)
                    else datetime.fromtimestamp(payload.exp, tz=timezone.utc).isoformat(),
                }

                # Сохраняем сессию в Redis
                pipeline = redis.pipeline()
                pipeline.hset(session_key, mapping=session_data)
                pipeline.expire(session_key, 30 * 24 * 60 * 60)
                pipeline.sadd(cls._make_user_sessions_key(user_id), token)
                await pipeline.execute()

                logger.info(f"[SessionManager.verify_session] Создана новая сессия для валидного токена: {session_key}")
                return payload

            # Если сессии нет, возвращаем None
            return None

        # Если сессия найдена, возвращаем payload
        logger.debug(f"[SessionManager.verify_session] Сессия найдена для пользователя {user_id}")
        return payload

    @classmethod
    async def get_user_sessions(cls, user_id: str) -> List[Dict[str, Any]]:
        """
        Получает список активных сессий пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            List[Dict[str, Any]]: Список сессий
        """
        user_sessions_key = cls._make_user_sessions_key(user_id)
        tokens = await redis.smembers(user_sessions_key)

        sessions = []
        for token in tokens:
            session_key = cls._make_session_key(user_id, token)
            session_data = await redis.hgetall(session_key)

            if session_data:
                session = dict(session_data)
                session["token"] = token
                sessions.append(session)

        return sessions

    @classmethod
    async def delete_session(cls, user_id: str, token: str) -> bool:
        """
        Удаляет сессию.

        Args:
            user_id: ID пользователя
            token: JWT токен

        Returns:
            bool: True, если сессия успешно удалена
        """
        session_key = cls._make_session_key(user_id, token)
        user_sessions_key = cls._make_user_sessions_key(user_id)

        # Удаляем данные сессии и токен из списка сессий пользователя
        pipeline = redis.pipeline()
        pipeline.delete(session_key)
        pipeline.srem(user_sessions_key, token)

        # Также удаляем ключ в формате TokenStorage для полной очистки
        token_payload = JWTCodec.decode(token)
        if token_payload:
            token_key = f"{user_id}-{token_payload.username}-{token}"
            pipeline.delete(token_key)

        results = await pipeline.execute()

        return bool(results[0]) or bool(results[1])

    @classmethod
    async def delete_all_sessions(cls, user_id: str) -> int:
        """
        Удаляет все сессии пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            int: Количество удаленных сессий
        """
        user_sessions_key = cls._make_user_sessions_key(user_id)
        tokens = await redis.smembers(user_sessions_key)

        count = 0
        for token in tokens:
            session_key = cls._make_session_key(user_id, token)

            # Удаляем данные сессии
            deleted = await redis.delete(session_key)
            count += deleted

            # Также удаляем ключ в формате TokenStorage
            token_payload = JWTCodec.decode(token)
            if token_payload:
                token_key = f"{user_id}-{token_payload.username}-{token}"
                await redis.delete(token_key)

        # Очищаем список токенов
        await redis.delete(user_sessions_key)

        return count

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
            session_data = await redis.execute("HGETALL", session_key)
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
