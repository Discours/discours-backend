from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import jwt
from pydantic import BaseModel

from settings import JWT_ALGORITHM, JWT_SECRET_KEY
from utils.logger import root_logger as logger


class TokenPayload(BaseModel):
    user_id: str
    username: str
    exp: Optional[datetime] = None
    iat: datetime
    iss: str


class JWTCodec:
    @staticmethod
    def encode(user: Union[dict[str, Any], Any], exp: Optional[datetime] = None) -> str:
        # Поддержка как объектов, так и словарей
        if isinstance(user, dict):
            # В TokenStorage.create_session передается словарь {"id": user_id, "email": username}
            user_id = str(user.get("id", ""))
            username = user.get("email", "") or user.get("username", "")
        else:
            # Для объектов с атрибутами
            user_id = str(getattr(user, "id", ""))
            username = getattr(user, "slug", "") or getattr(user, "email", "") or getattr(user, "phone", "") or ""

        logger.debug(f"[JWTCodec.encode] Кодирование токена для user_id={user_id}, username={username}")

        # Если время истечения не указано, установим срок годности на 30 дней
        if exp is None:
            exp = datetime.now(tz=timezone.utc) + timedelta(days=30)
            logger.debug(f"[JWTCodec.encode] Время истечения не указано, устанавливаем срок: {exp}")

        # Важно: убедимся, что exp всегда является либо datetime, либо целым числом от timestamp
        if isinstance(exp, datetime):
            # Преобразуем datetime в timestamp чтобы гарантировать правильный формат
            exp_timestamp = int(exp.timestamp())
        else:
            # Если передано что-то другое, установим значение по умолчанию
            logger.warning(f"[JWTCodec.encode] Некорректный формат exp: {exp}, используем значение по умолчанию")
            exp_timestamp = int((datetime.now(tz=timezone.utc) + timedelta(days=30)).timestamp())

        payload = {
            "user_id": user_id,
            "username": username,
            "exp": exp_timestamp,  # Используем timestamp вместо datetime
            "iat": datetime.now(tz=timezone.utc),
            "iss": "discours",
        }

        logger.debug(f"[JWTCodec.encode] Сформирован payload: {payload}")

        try:
            token = jwt.encode(payload, JWT_SECRET_KEY, JWT_ALGORITHM)
            logger.debug(f"[JWTCodec.encode] Токен успешно создан, длина: {len(token) if token else 0}")
            # Ensure we always return str, not bytes
            if isinstance(token, bytes):
                return token.decode("utf-8")
            return str(token)
        except Exception as e:
            logger.error(f"[JWTCodec.encode] Ошибка при кодировании JWT: {e}")
            raise

    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> Optional[TokenPayload]:
        logger.debug(f"[JWTCodec.decode] Начало декодирования токена длиной {len(token) if token else 0}")

        if not token:
            logger.error("[JWTCodec.decode] Пустой токен")
            return None

        try:
            payload = jwt.decode(
                token,
                key=JWT_SECRET_KEY,
                options={
                    "verify_exp": verify_exp,
                    # "verify_signature": False
                },
                algorithms=[JWT_ALGORITHM],
                issuer="discours",
            )
            logger.debug(f"[JWTCodec.decode] Декодирован payload: {payload}")

            # Убедимся, что exp существует (добавим обработку если exp отсутствует)
            if "exp" not in payload:
                logger.warning("[JWTCodec.decode] В токене отсутствует поле exp")
                # Добавим exp по умолчанию, чтобы избежать ошибки при создании TokenPayload
                payload["exp"] = int((datetime.now(tz=timezone.utc) + timedelta(days=30)).timestamp())

            try:
                r = TokenPayload(**payload)
                logger.debug(
                    f"[JWTCodec.decode] Создан объект TokenPayload: user_id={r.user_id}, username={r.username}"
                )
                return r
            except Exception as e:
                logger.error(f"[JWTCodec.decode] Ошибка при создании TokenPayload: {e}")
                return None

        except jwt.InvalidIssuedAtError:
            logger.error("[JWTCodec.decode] Недействительное время выпуска токена")
            return None
        except jwt.ExpiredSignatureError:
            logger.error("[JWTCodec.decode] Истек срок действия токена")
            return None
        except jwt.InvalidSignatureError:
            logger.error("[JWTCodec.decode] Недействительная подпись токена")
            return None
        except jwt.InvalidTokenError:
            logger.error("[JWTCodec.decode] Недействительный токен")
            return None
        except jwt.InvalidKeyError:
            logger.error("[JWTCodec.decode] Недействительный ключ")
            return None
        except Exception as e:
            logger.error(f"[JWTCodec.decode] Неожиданная ошибка при декодировании: {e}")
            return None
