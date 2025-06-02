"""
Простой интерфейс для системы токенов
"""

from typing import Any, Optional

from .batch import BatchTokenOperations
from .monitoring import TokenMonitoring
from .oauth import OAuthTokenManager
from .sessions import SessionTokenManager
from .verification import VerificationTokenManager


class _TokenStorageImpl:
    """
    Внутренний класс для фасада токенов.
    Использует композицию вместо наследования.
    """

    def __init__(self) -> None:
        self._sessions = SessionTokenManager()
        self._verification = VerificationTokenManager()
        self._oauth = OAuthTokenManager()
        self._batch = BatchTokenOperations()
        self._monitoring = TokenMonitoring()

    # === МЕТОДЫ ДЛЯ СЕССИЙ ===

    async def create_session(
        self,
        user_id: str,
        auth_data: Optional[dict] = None,
        username: Optional[str] = None,
        device_info: Optional[dict] = None,
    ) -> str:
        """Создание сессии пользователя"""
        return await self._sessions.create_session(user_id, auth_data, username, device_info)

    async def verify_session(self, token: str) -> Optional[Any]:
        """Проверка сессии по токену"""
        return await self._sessions.verify_session(token)

    async def refresh_session(self, user_id: int, old_token: str, device_info: Optional[dict] = None) -> Optional[str]:
        """Обновление сессии пользователя"""
        return await self._sessions.refresh_session(user_id, old_token, device_info)

    async def revoke_session(self, session_token: str) -> bool:
        """Отзыв сессии"""
        return await self._sessions.revoke_session_token(session_token)

    async def revoke_user_sessions(self, user_id: str) -> int:
        """Отзыв всех сессий пользователя"""
        return await self._sessions.revoke_user_sessions(user_id)

    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===

    async def cleanup_expired_tokens(self) -> int:
        """Очистка истекших токенов"""
        return await self._batch.cleanup_expired_tokens()

    async def get_token_statistics(self) -> dict:
        """Получение статистики токенов"""
        return await self._monitoring.get_token_statistics()


# Глобальный экземпляр фасада
_token_storage = _TokenStorageImpl()


class TokenStorage:
    """
    Статический фасад для системы токенов.
    Все методы делегируются глобальному экземпляру.
    """

    @staticmethod
    async def create_session(
        user_id: str,
        auth_data: Optional[dict] = None,
        username: Optional[str] = None,
        device_info: Optional[dict] = None,
    ) -> str:
        """Создание сессии пользователя"""
        return await _token_storage.create_session(user_id, auth_data, username, device_info)

    @staticmethod
    async def verify_session(token: str) -> Optional[Any]:
        """Проверка сессии по токену"""
        return await _token_storage.verify_session(token)

    @staticmethod
    async def refresh_session(user_id: int, old_token: str, device_info: Optional[dict] = None) -> Optional[str]:
        """Обновление сессии пользователя"""
        return await _token_storage.refresh_session(user_id, old_token, device_info)

    @staticmethod
    async def revoke_session(session_token: str) -> bool:
        """Отзыв сессии"""
        return await _token_storage.revoke_session(session_token)

    @staticmethod
    async def revoke_user_sessions(user_id: str) -> int:
        """Отзыв всех сессий пользователя"""
        return await _token_storage.revoke_user_sessions(user_id)

    @staticmethod
    async def cleanup_expired_tokens() -> int:
        """Очистка истекших токенов"""
        return await _token_storage.cleanup_expired_tokens()

    @staticmethod
    async def get_token_statistics() -> dict:
        """Получение статистики токенов"""
        return await _token_storage.get_token_statistics()
