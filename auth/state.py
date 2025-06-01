"""
Классы состояния авторизации
"""

from typing import Optional


class AuthState:
    """
    Класс для хранения информации о состоянии авторизации пользователя.
    Используется в аутентификационных middleware и функциях.
    """

    def __init__(self) -> None:
        self.logged_in: bool = False
        self.author_id: Optional[str] = None
        self.token: Optional[str] = None
        self.username: Optional[str] = None
        self.is_admin: bool = False
        self.is_editor: bool = False
        self.error: Optional[str] = None

    def __bool__(self) -> bool:
        """Возвращает True если пользователь авторизован"""
        return self.logged_in
