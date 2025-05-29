from binascii import hexlify
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Dict, TypeVar

from passlib.hash import bcrypt

from auth.exceptions import ExpiredToken, InvalidPassword, InvalidToken
from auth.jwtcodec import JWTCodec
from auth.tokenstorage import TokenStorage
from services.db import local_session

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
        """
        Verify that password hash is equal to specified hash. Hash format:

        $2a$10$Ro0CUfOqk6cXEKf3dyaM7OhSCvnwM9s4wIX9JeLapehKK5YdLxKcm
        \__/\/ \____________________/\_____________________________/  # noqa: W605
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
    def password(orm_author: Any, password: str) -> Any:
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
        from auth.orm import Author
        from utils.logger import root_logger as logger

        # Проверим исходный пароль в orm_author
        if not orm_author.password:
            logger.warning(f"[auth.identity] Пароль в исходном объекте автора пуст: email={orm_author.email}")
            raise InvalidPassword("Пароль не установлен для данного пользователя")

        # Проверяем пароль напрямую, не используя dict()
        if not Password.verify(password, orm_author.password):
            logger.warning(f"[auth.identity] Неверный пароль для {orm_author.email}")
            raise InvalidPassword("Неверный пароль пользователя")

        # Возвращаем исходный объект, чтобы сохранить все связи
        return orm_author

    @staticmethod
    def oauth(inp: Dict[str, Any]) -> Any:
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
                author.email_verified = True
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
            if not await TokenStorage.exist(f"{payload.user_id}-{payload.username}-{token}"):
                # raise InvalidToken("Login token has expired, please login again")
                return {"error": "Token has expired"}
        except ExpiredToken:
            # raise InvalidToken("Login token has expired, please try again")
            return {"error": "Token has expired"}
        except InvalidToken:
            # raise InvalidToken("token format error") from e
            return {"error": "Token format error"}
        with local_session() as session:
            author = session.query(Author).filter_by(id=payload.user_id).first()
            if not author:
                # raise Exception("user not exist")
                return {"error": "Author does not exist"}
            if not author.email_verified:
                author.email_verified = True
                session.commit()
            return author
