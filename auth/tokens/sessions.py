"""
Управление токенами сессий
"""

import json
import time
from typing import Any, List, Optional, Union

from auth.jwtcodec import JWTCodec
from services.redis import redis as redis_adapter
from utils.logger import root_logger as logger

from .base import BaseTokenManager
from .types import DEFAULT_TTL, TokenData


class SessionTokenManager(BaseTokenManager):
    """
    Менеджер токенов сессий
    """

    async def create_session(
        self,
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

        return await self.create_session_token(user_id, session_data)

    async def create_session_token(self, user_id: str, token_data: TokenData) -> str:
        """Создание JWT токена сессии"""
        username = token_data.get("username", "")

        # Создаем JWT токен
        jwt_token = JWTCodec.encode(
            {
                "user_id": user_id,
                "username": username,
            }
        )

        session_token = jwt_token.decode("utf-8") if isinstance(jwt_token, bytes) else str(jwt_token)
        token_key = self._make_token_key("session", user_id, session_token)
        user_tokens_key = self._make_user_tokens_key(user_id, "session")
        ttl = DEFAULT_TTL["session"]

        # Добавляем метаданные
        token_data.update({"user_id": user_id, "token_type": "session", "created_at": int(time.time())})

        # Используем новый метод execute_pipeline для избежания deprecated warnings
        commands: list[tuple[str, tuple[Any, ...]]] = []

        # Сохраняем данные сессии в hash, преобразуя значения в строки
        for field, value in token_data.items():
            commands.append(("hset", (token_key, field, str(value))))
        commands.append(("expire", (token_key, ttl)))

        # Добавляем в список сессий пользователя
        commands.append(("sadd", (user_tokens_key, session_token)))
        commands.append(("expire", (user_tokens_key, ttl)))

        await redis_adapter.execute_pipeline(commands)

        logger.info(f"Создан токен сессии для пользователя {user_id}")
        return session_token

    async def get_session_data(self, token: str, user_id: Optional[str] = None) -> Optional[TokenData]:
        """Получение данных сессии"""
        if not user_id:
            # Извлекаем user_id из JWT
            payload = JWTCodec.decode(token)
            if payload:
                user_id = payload.get("user_id")
            else:
                return None

        token_key = self._make_token_key("session", user_id, token)

        # Используем новый метод execute_pipeline для избежания deprecated warnings
        commands: list[tuple[str, tuple[Any, ...]]] = [
            ("hgetall", (token_key,)),
            ("hset", (token_key, "last_activity", str(int(time.time())))),
        ]
        results = await redis_adapter.execute_pipeline(commands)

        token_data = results[0] if results else None
        return dict(token_data) if token_data else None

    async def validate_session_token(self, token: str) -> tuple[bool, Optional[TokenData]]:
        """
        Проверяет валидность токена сессии
        """
        try:
            # Декодируем JWT токен
            payload = JWTCodec.decode(token)
            if not payload:
                return False, None

            user_id = payload.get("user_id")
            token_key = self._make_token_key("session", user_id, token)

            # Проверяем существование и получаем данные
            commands: list[tuple[str, tuple[Any, ...]]] = [("exists", (token_key,)), ("hgetall", (token_key,))]
            results = await redis_adapter.execute_pipeline(commands)

            if results and results[0]:  # exists
                return True, dict(results[1])

            return False, None

        except Exception as e:
            logger.error(f"Ошибка валидации токена сессии: {e}")
            return False, None

    async def revoke_session_token(self, token: str) -> bool:
        """Отзыв токена сессии"""
        payload = JWTCodec.decode(token)
        if not payload:
            return False

        user_id = payload.get("user_id")

        # Используем новый метод execute_pipeline для избежания deprecated warnings
        token_key = self._make_token_key("session", user_id, token)
        user_tokens_key = self._make_user_tokens_key(user_id, "session")

        commands: list[tuple[str, tuple[Any, ...]]] = [("delete", (token_key,)), ("srem", (user_tokens_key, token))]
        results = await redis_adapter.execute_pipeline(commands)

        return any(result > 0 for result in results if result is not None)

    async def revoke_user_sessions(self, user_id: str) -> int:
        """Отзыв всех сессий пользователя"""
        user_tokens_key = self._make_user_tokens_key(user_id, "session")
        tokens = await redis_adapter.smembers(user_tokens_key)

        if not tokens:
            return 0

        # Используем пакетное удаление
        keys_to_delete = []
        for token in tokens:
            token_str = token if isinstance(token, str) else str(token)
            keys_to_delete.append(self._make_token_key("session", user_id, token_str))

        # Добавляем ключ списка токенов
        keys_to_delete.append(user_tokens_key)

        # Удаляем все ключи пакетно
        if keys_to_delete:
            await redis_adapter.delete(*keys_to_delete)

        return len(tokens)

    async def get_user_sessions(self, user_id: Union[int, str]) -> List[TokenData]:
        """Получение сессий пользователя"""
        try:
            user_tokens_key = self._make_user_tokens_key(str(user_id), "session")
            tokens = await redis_adapter.smembers(user_tokens_key)

            if not tokens:
                return []

            # Получаем данные всех сессий пакетно
            sessions = []
            async with redis_adapter.pipeline() as pipe:
                for token in tokens:
                    token_str = token if isinstance(token, str) else str(token)
                    await pipe.hgetall(self._make_token_key("session", str(user_id), token_str))
                results = await pipe.execute()

            for token, session_data in zip(tokens, results):
                if session_data:
                    token_str = token if isinstance(token, str) else str(token)
                    session_dict = dict(session_data)
                    session_dict["token"] = token_str
                    sessions.append(session_dict)

            return sessions

        except Exception as e:
            logger.error(f"Ошибка получения сессий пользователя: {e}")
            return []

    async def refresh_session(self, user_id: int, old_token: str, device_info: Optional[dict] = None) -> Optional[str]:
        """
        Обновляет сессию пользователя, заменяя старый токен новым
        """
        try:
            user_id_str = str(user_id)
            # Получаем данные старой сессии
            old_session_data = await self.get_session_data(old_token)

            if not old_session_data:
                logger.warning(f"Сессия не найдена: {user_id}")
                return None

            # Используем старые данные устройства, если новые не предоставлены
            if not device_info and "device_info" in old_session_data:
                try:
                    device_info = json.loads(old_session_data.get("device_info", "{}"))
                except (json.JSONDecodeError, TypeError):
                    device_info = None

            # Создаем новую сессию
            new_token = await self.create_session(
                user_id_str, device_info=device_info, username=old_session_data.get("username", "")
            )

            # Отзываем старую сессию
            await self.revoke_session_token(old_token)

            return new_token
        except Exception as e:
            logger.error(f"Ошибка обновления сессии: {e}")
            return None

    async def verify_session(self, token: str) -> Optional[Any]:
        """
        Проверяет сессию по токену для совместимости с TokenStorage
        """
        if not token:
            logger.debug("Пустой токен")
            return None

        logger.debug(f"Проверка сессии для токена: {token[:20]}...")

        try:
            # Декодируем токен для получения payload
            payload = JWTCodec.decode(token)
            if not payload:
                logger.error("Не удалось декодировать токен")
                return None

            user_id = payload.get("user_id")
            if not user_id:
                logger.error("В токене отсутствует user_id")
                return None

            logger.debug(f"Успешно декодирован токен, user_id={user_id}")

            # Проверяем наличие сессии в Redis
            token_key = self._make_token_key("session", str(user_id), token)
            session_exists = await redis_adapter.exists(token_key)

            if not session_exists:
                logger.warning(f"Сессия не найдена в Redis для user_id={user_id}")
                return None

            # Обновляем last_activity
            await redis_adapter.hset(token_key, "last_activity", str(int(time.time())))

            return payload

        except Exception as e:
            logger.error(f"Ошибка при проверке сессии: {e}")
            return None
