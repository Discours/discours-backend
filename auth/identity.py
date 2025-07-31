from typing import TYPE_CHECKING, Any, TypeVar

from auth.exceptions import ExpiredTokenError, InvalidPasswordError, InvalidTokenError
from auth.jwtcodec import JWTCodec
from auth.password import Password
from services.db import local_session
from services.redis import redis
from utils.logger import root_logger as logger

# Для типизации
if TYPE_CHECKING:
    from auth.orm import Author

AuthorType = TypeVar("AuthorType", bound="Author")


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
            InvalidPasswordError: Если пароль не соответствует хешу или отсутствует
        """
        # Проверим исходный пароль в orm_author
        if not orm_author.password:
            logger.warning(f"[auth.identity] Пароль в исходном объекте автора пуст: email={orm_author.email}")
            msg = "Пароль не установлен для данного пользователя"
            raise InvalidPasswordError(msg)

        # Проверяем пароль напрямую, не используя dict()
        password_hash = str(orm_author.password) if orm_author.password else ""
        if not password_hash or not Password.verify(password, password_hash):
            logger.warning(f"[auth.identity] Неверный пароль для {orm_author.email}")
            msg = "Неверный пароль пользователя"
            raise InvalidPasswordError(msg)

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
        # Поздний импорт для избежания циклических зависимостей
        from auth.orm import Author

        with local_session() as session:
            author = session.query(Author).where(Author.email == inp["email"]).first()
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
        try:
            print("[auth.identity] using one time token")
            payload = JWTCodec.decode(token)
            if payload is None:
                logger.warning("[Identity.token] Токен не валиден (payload is None)")
                return {"error": "Invalid token"}

            # Проверяем существование токена в хранилище
            user_id = payload.get("user_id")
            username = payload.get("username")
            if not user_id or not username:
                logger.warning("[Identity.token] Нет user_id или username в токене")
                return {"error": "Invalid token"}

            token_key = f"{user_id}-{username}-{token}"
            if not await redis.exists(token_key):
                logger.warning(f"[Identity.token] Токен не найден в хранилище: {token_key}")
                return {"error": "Token not found"}

            # Если все проверки пройдены, ищем автора в базе данных
            # Поздний импорт для избежания циклических зависимостей
            from auth.orm import Author

            with local_session() as session:
                author = session.query(Author).filter_by(id=user_id).first()
                if not author:
                    logger.warning(f"[Identity.token] Автор с ID {user_id} не найден")
                    return {"error": "User not found"}

                logger.info(f"[Identity.token] Токен валиден для автора {author.id}")
                return author
        except ExpiredTokenError:
            # raise InvalidTokenError("Login token has expired, please try again")
            return {"error": "Token has expired"}
        except InvalidTokenError:
            # raise InvalidTokenError("token format error") from e
            return {"error": "Token format error"}
