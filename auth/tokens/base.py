"""
Базовый класс для работы с токенами
"""

import secrets
from functools import lru_cache
from typing import Optional

from .types import TokenType


class BaseTokenManager:
    """
    Базовый класс с общими методами для всех типов токенов
    """

    @staticmethod
    @lru_cache(maxsize=1000)
    def _make_token_key(token_type: TokenType, identifier: str, token: Optional[str] = None) -> str:
        """
        Создает унифицированный ключ для токена с кэшированием

        Args:
            token_type: Тип токена
            identifier: Идентификатор (user_id, user_id:provider, etc)
            token: Сам токен (для session и verification)

        Returns:
            str: Ключ токена
        """
        if token_type == "session":  # noqa: S105
            return f"session:{identifier}:{token}"
        if token_type == "verification":  # noqa: S105
            return f"verification_token:{token}"
        if token_type == "oauth_access":  # noqa: S105
            return f"oauth_access:{identifier}"
        if token_type == "oauth_refresh":  # noqa: S105
            return f"oauth_refresh:{identifier}"

        error_msg = f"Неизвестный тип токена: {token_type}"
        raise ValueError(error_msg)

    @staticmethod
    @lru_cache(maxsize=500)
    def _make_user_tokens_key(user_id: str, token_type: TokenType) -> str:
        """Создает ключ для списка токенов пользователя"""
        if token_type == "session":  # noqa: S105
            return f"user_sessions:{user_id}"
        return f"user_tokens:{user_id}:{token_type}"

    @staticmethod
    def generate_token() -> str:
        """Генерирует криптографически стойкий токен"""
        return secrets.token_urlsafe(32)
