from binascii import hexlify
from hashlib import sha256
from typing import TYPE_CHECKING, Any, TypeVar

from passlib.hash import bcrypt

from auth.exceptions import ExpiredToken, InvalidPassword, InvalidToken
from auth.jwtcodec import JWTCodec
from services.db import local_session
from services.redis import redis
from utils.logger import root_logger as logger

# Для типизации
if TYPE_CHECKING:
    from auth.orm import Author

AuthorType = TypeVar("AuthorType", bound="Author")


class Password:
    @staticmethod
    def _to_bytes(data: str) -> bytes:
        return bytes(data.encode())

    @classmethod
    def _get_sha256(cls, password: str) -> bytes:
        bytes_password = cls._to_bytes(password)
        return hexlify(sha256(bytes_password).digest())

    @staticmethod
    def encode(password: str) -> str:
        """
        Кодирует пароль пользователя

        Args:
            password (str): Пароль пользователя

        Returns:
            str: Закодированный пароль
        """
        password_sha256 = Password._get_sha256(password)
        return bcrypt.using(rounds=10).hash(password_sha256)

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        r"""
        Verify that password hash is equal to specified hash. Hash format:

        $2a$10$Ro0CUfOqk6cXEKf3dyaM7OhSCvnwM9s4wIX9JeLapehKK5YdLxKcm
        \__/\/ \____________________/\_____________________________/
        |   |        Salt                     Hash
        |  Cost
        Version

        More info: https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt.html

        :param password: clear text password
        :param hashed: hash of the password
        :return: True if clear text password matches specified hash
        """
        hashed_bytes = Password._to_bytes(hashed)
        password_sha256 = Password._get_sha256(password)

        return bcrypt.verify(password_sha256, hashed_bytes)


class Identity:
    @staticmethod
    def password(orm_author: AuthorType, password: str) -> AuthorType:
        """
        Проверяет пароль пользователя

        Args:
            orm_author (Author): Объект пользователя
            password (str): Пароль пользователя

        Returns:
            Author: Объект автора при успешной проверке

        Raises:
            InvalidPassword: Если пароль не соответствует хешу или отсутствует
        """
        # Импортируем внутри функции для избежания циклических импортов
        from utils.logger import root_logger as logger

        # Проверим исходный пароль в orm_author
        if not orm_author.password:
            logger.warning(f"[auth.identity] Пароль в исходном объекте автора пуст: email={orm_author.email}")
            msg = "Пароль не установлен для данного пользователя"
            raise InvalidPassword(msg)

        # Проверяем пароль напрямую, не используя dict()
        password_hash = str(orm_author.password) if orm_author.password else ""
        if not password_hash or not Password.verify(password, password_hash):
            logger.warning(f"[auth.identity] Неверный пароль для {orm_author.email}")
            msg = "Неверный пароль пользователя"
            raise InvalidPassword(msg)

        # Возвращаем исходный объект, чтобы сохранить все связи
        return orm_author

    @staticmethod
    def oauth(inp: dict[str, Any]) -> Any:
        """
        Создает нового пользователя OAuth, если он не существует

        Args:
            inp (dict): Данные OAuth пользователя

        Returns:
            Author: Объект пользователя
        """
        # Импортируем внутри функции для избежания циклических импортов
        from auth.orm import Author

        with local_session() as session:
            author = session.query(Author).filter(Author.email == inp["email"]).first()
            if not author:
                author = Author(**inp)
                author.email_verified = True  # type: ignore[assignment]
                session.add(author)
                session.commit()

        return author

    @staticmethod
    async def onetime(token: str) -> Any:
        """
        Проверяет одноразовый токен

        Args:
            token (str): Одноразовый токен

        Returns:
            Author: Объект пользователя
        """
        # Импортируем внутри функции для избежания циклических импортов
        from auth.orm import Author

        try:
            print("[auth.identity] using one time token")
            payload = JWTCodec.decode(token)
            if payload is None:
                logger.warning("[Identity.token] Токен не валиден (payload is None)")
                return {"error": "Invalid token"}

            # Проверяем существование токена в хранилище
            token_key = f"{payload.user_id}-{payload.username}-{token}"
            if not await redis.exists(token_key):
                logger.warning(f"[Identity.token] Токен не найден в хранилище: {token_key}")
                return {"error": "Token not found"}

            # Если все проверки пройдены, ищем автора в базе данных
            with local_session() as session:
                author = session.query(Author).filter_by(id=payload.user_id).first()
                if not author:
                    logger.warning(f"[Identity.token] Автор с ID {payload.user_id} не найден")
                    return {"error": "User not found"}

                logger.info(f"[Identity.token] Токен валиден для автора {author.id}")
                return author
        except ExpiredToken:
            # raise InvalidToken("Login token has expired, please try again")
            return {"error": "Token has expired"}
        except InvalidToken:
            # raise InvalidToken("token format error") from e
            return {"error": "Token format error"}
