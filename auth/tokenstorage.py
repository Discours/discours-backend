import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from auth.jwtcodec import JWTCodec
from auth.validations import AuthInput
from services.redis import redis
from settings import ONETIME_TOKEN_LIFE_SPAN, SESSION_TOKEN_LIFE_SPAN
from utils.logger import root_logger as logger


class TokenStorage:
    """
    Класс для работы с хранилищем токенов в Redis
    """

    @staticmethod
    def _make_token_key(user_id: str, username: str, token: str) -> str:
        """
        Создает ключ для хранения токена

        Args:
            user_id: ID пользователя
            username: Имя пользователя
            token: Токен

        Returns:
            str: Ключ токена
        """
        # Сохраняем в старом формате для обратной совместимости
        return f"{user_id}-{username}-{token}"

    @staticmethod
    def _make_session_key(user_id: str, token: str) -> str:
        """
        Создает ключ в новом формате SessionManager

        Args:
            user_id: ID пользователя
            token: Токен

        Returns:
            str: Ключ сессии
        """
        return f"session:{user_id}:{token}"

    @staticmethod
    def _make_user_sessions_key(user_id: str) -> str:
        """
        Создает ключ для списка сессий пользователя

        Args:
            user_id: ID пользователя

        Returns:
            str: Ключ списка сессий
        """
        return f"user_sessions:{user_id}"

    @classmethod
    async def create_session(cls, user_id: str, username: str, device_info: Optional[Dict[str, str]] = None) -> str:
        """
        Создает новую сессию для пользователя

        Args:
            user_id: ID пользователя
            username: Имя пользователя
            device_info: Информация об устройстве (опционально)

        Returns:
            str: Токен сессии
        """
        logger.debug(f"[TokenStorage.create_session] Начало создания сессии для пользователя {user_id}")

        # Генерируем JWT токен с явным указанием времени истечения
        expiration_date = datetime.now(tz=timezone.utc) + timedelta(days=30)
        token = JWTCodec.encode({"id": user_id, "email": username}, exp=expiration_date)
        logger.debug(f"[TokenStorage.create_session] Создан JWT токен длиной {len(token)}")

        # Формируем ключи для Redis
        token_key = cls._make_token_key(user_id, username, token)
        logger.debug(f"[TokenStorage.create_session] Сформированы ключи: token_key={token_key}")

        # Формируем ключи в новом формате SessionManager для совместимости
        session_key = cls._make_session_key(user_id, token)
        user_sessions_key = cls._make_user_sessions_key(user_id)

        # Готовим данные для сохранения
        token_data = {
            "user_id": user_id,
            "username": username,
            "created_at": time.time(),
            "expires_at": time.time() + 30 * 24 * 60 * 60,  # 30 дней
        }

        if device_info:
            token_data.update(device_info)

        logger.debug(f"[TokenStorage.create_session] Сформированы данные сессии: {token_data}")

        # Сохраняем в Redis старый формат
        pipeline = redis.pipeline()
        pipeline.hset(token_key, mapping=token_data)
        pipeline.expire(token_key, 30 * 24 * 60 * 60)  # 30 дней

        # Также сохраняем в новом формате SessionManager для обеспечения совместимости
        pipeline.hset(session_key, mapping=token_data)
        pipeline.expire(session_key, 30 * 24 * 60 * 60)  # 30 дней
        pipeline.sadd(user_sessions_key, token)
        pipeline.expire(user_sessions_key, 30 * 24 * 60 * 60)  # 30 дней

        results = await pipeline.execute()
        logger.info(f"[TokenStorage.create_session] Сессия успешно создана для пользователя {user_id}")

        return token

    @classmethod
    async def exists(cls, token_key: str) -> bool:
        """
        Проверяет существование токена по ключу

        Args:
            token_key: Ключ токена

        Returns:
            bool: True, если токен существует
        """
        exists = await redis.exists(token_key)
        return bool(exists)

    @classmethod
    async def validate_token(cls, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Проверяет валидность токена

        Args:
            token: JWT токен

        Returns:
            Tuple[bool, Dict[str, Any]]: (Валиден ли токен, данные токена)
        """
        try:
            # Декодируем JWT токен
            payload = JWTCodec.decode(token)
            if not payload:
                logger.warning(f"[TokenStorage.validate_token] Токен не валиден (не удалось декодировать)")
                return False, None

            user_id = payload.user_id
            username = payload.username

            # Формируем ключи для Redis в обоих форматах
            token_key = cls._make_token_key(user_id, username, token)
            session_key = cls._make_session_key(user_id, token)

            # Проверяем в обоих форматах для совместимости
            old_exists = await redis.exists(token_key)
            new_exists = await redis.exists(session_key)

            if old_exists or new_exists:
                logger.info(f"[TokenStorage.validate_token] Токен валиден для пользователя {user_id}")

                # Получаем данные токена из актуального хранилища
                if new_exists:
                    token_data = await redis.hgetall(session_key)
                else:
                    token_data = await redis.hgetall(token_key)

                    # Если найден только в старом формате, создаем запись в новом формате
                    if not new_exists:
                        logger.info(f"[TokenStorage.validate_token] Миграция токена в новый формат: {session_key}")
                        await redis.hset(session_key, mapping=token_data)
                        await redis.expire(session_key, 30 * 24 * 60 * 60)
                        await redis.sadd(cls._make_user_sessions_key(user_id), token)

                return True, token_data
            else:
                logger.warning(f"[TokenStorage.validate_token] Токен не найден в Redis: {token_key}")
                return False, None

        except Exception as e:
            logger.error(f"[TokenStorage.validate_token] Ошибка при проверке токена: {e}")
            return False, None

    @classmethod
    async def invalidate_token(cls, token: str) -> bool:
        """
        Инвалидирует токен

        Args:
            token: JWT токен

        Returns:
            bool: True, если токен успешно инвалидирован
        """
        try:
            # Декодируем JWT токен
            payload = JWTCodec.decode(token)
            if not payload:
                logger.warning(f"[TokenStorage.invalidate_token] Токен не валиден (не удалось декодировать)")
                return False

            user_id = payload.user_id
            username = payload.username

            # Формируем ключи для Redis в обоих форматах
            token_key = cls._make_token_key(user_id, username, token)
            session_key = cls._make_session_key(user_id, token)
            user_sessions_key = cls._make_user_sessions_key(user_id)

            # Удаляем токен из Redis в обоих форматах
            pipeline = redis.pipeline()
            pipeline.delete(token_key)
            pipeline.delete(session_key)
            pipeline.srem(user_sessions_key, token)
            results = await pipeline.execute()

            success = any(results)
            if success:
                logger.info(f"[TokenStorage.invalidate_token] Токен успешно инвалидирован для пользователя {user_id}")
            else:
                logger.warning(f"[TokenStorage.invalidate_token] Токен не найден: {token_key}")

            return success

        except Exception as e:
            logger.error(f"[TokenStorage.invalidate_token] Ошибка при инвалидации токена: {e}")
            return False

    @classmethod
    async def invalidate_all_tokens(cls, user_id: str) -> int:
        """
        Инвалидирует все токены пользователя

        Args:
            user_id: ID пользователя

        Returns:
            int: Количество инвалидированных токенов
        """
        try:
            # Получаем список сессий пользователя
            user_sessions_key = cls._make_user_sessions_key(user_id)
            tokens = await redis.smembers(user_sessions_key)

            if not tokens:
                logger.warning(f"[TokenStorage.invalidate_all_tokens] Нет активных сессий пользователя {user_id}")
                return 0

            count = 0
            for token in tokens:
                # Декодируем JWT токен
                try:
                    payload = JWTCodec.decode(token)
                    if payload:
                        username = payload.username

                        # Формируем ключи для Redis
                        token_key = cls._make_token_key(user_id, username, token)
                        session_key = cls._make_session_key(user_id, token)

                        # Удаляем токен из Redis
                        pipeline = redis.pipeline()
                        pipeline.delete(token_key)
                        pipeline.delete(session_key)
                        results = await pipeline.execute()

                        count += 1
                except Exception as e:
                    logger.error(f"[TokenStorage.invalidate_all_tokens] Ошибка при обработке токена: {e}")
                    continue

            # Удаляем список сессий пользователя
            await redis.delete(user_sessions_key)

            logger.info(f"[TokenStorage.invalidate_all_tokens] Инвалидировано {count} токенов пользователя {user_id}")
            return count

        except Exception as e:
            logger.error(f"[TokenStorage.invalidate_all_tokens] Ошибка при инвалидации всех токенов: {e}")
            return 0

    @classmethod
    async def get_session_data(cls, token: str) -> Optional[Dict[str, Any]]:
        """
        Получает данные сессии

        Args:
            token: JWT токен

        Returns:
            Dict[str, Any]: Данные сессии или None
        """
        valid, data = await cls.validate_token(token)
        return data if valid else None

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
