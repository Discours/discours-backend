import datetime
import logging
from typing import Any, Dict, Optional

import jwt

from settings import JWT_ALGORITHM, JWT_ISSUER, JWT_REFRESH_TOKEN_EXPIRE_DAYS, JWT_SECRET_KEY


class JWTCodec:
    """
    Кодировщик и декодировщик JWT токенов.
    """

    @staticmethod
    def encode(
        payload: Dict[str, Any],
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        expiration: Optional[datetime.datetime] = None,
    ) -> str | bytes:
        """
        Кодирует payload в JWT токен.

        Args:
            payload (Dict[str, Any]): Полезная нагрузка для кодирования
            secret_key (Optional[str]): Секретный ключ. По умолчанию используется JWT_SECRET_KEY
            algorithm (Optional[str]): Алгоритм шифрования. По умолчанию используется JWT_ALGORITHM
            expiration (Optional[datetime.datetime]): Время истечения токена

        Returns:
            str: Закодированный JWT токен
        """
        logger = logging.getLogger("root")
        logger.debug(f"[JWTCodec.encode] Кодирование токена для payload: {payload}")

        # Используем переданные или дефолтные значения
        secret_key = secret_key or JWT_SECRET_KEY
        algorithm = algorithm or JWT_ALGORITHM

        # Если время истечения не указано, устанавливаем дефолтное
        if not expiration:
            expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                days=JWT_REFRESH_TOKEN_EXPIRE_DAYS
            )
            logger.debug(f"[JWTCodec.encode] Время истечения не указано, устанавливаем срок: {expiration}")

        # Формируем payload с временными метками
        payload.update(
            {"exp": int(expiration.timestamp()), "iat": datetime.datetime.now(datetime.timezone.utc), "iss": JWT_ISSUER}
        )

        logger.debug(f"[JWTCodec.encode] Сформирован payload: {payload}")

        try:
            # Используем PyJWT для кодирования
            encoded = jwt.encode(payload, secret_key, algorithm=algorithm)
            token_str = encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded
            return token_str
        except Exception as e:
            logger.warning(f"[JWTCodec.encode] Ошибка при кодировании JWT: {e}")
            raise

    @staticmethod
    def decode(
        token: str,
        secret_key: Optional[str] = None,
        algorithms: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Декодирует JWT токен.

        Args:
            token (str): JWT токен
            secret_key (Optional[str]): Секретный ключ. По умолчанию используется JWT_SECRET_KEY
            algorithms (Optional[list]): Список алгоритмов. По умолчанию используется [JWT_ALGORITHM]

        Returns:
            Dict[str, Any]: Декодированный payload
        """
        logger = logging.getLogger("root")
        logger.debug("[JWTCodec.decode] Декодирование токена")

        # Используем переданные или дефолтные значения
        secret_key = secret_key or JWT_SECRET_KEY
        algorithms = algorithms or [JWT_ALGORITHM]

        try:
            # Используем PyJWT для декодирования
            decoded = jwt.decode(token, secret_key, algorithms=algorithms)
            return decoded
        except jwt.ExpiredSignatureError:
            logger.warning("[JWTCodec.decode] Токен просрочен")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"[JWTCodec.decode] Ошибка при декодировании JWT: {e}")
            raise
