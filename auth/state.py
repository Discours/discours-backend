"""
Классы состояния авторизации
"""

class AuthState:
    """
    Класс для хранения информации о состоянии авторизации пользователя.
    Используется в аутентификационных middleware и функциях.
    """
    
    def __init__(self):
        self.logged_in = False
        self.author_id = None
        self.token = None
        self.username = None
        self.is_admin = False
        self.is_editor = False
        self.error = None
    
    def __bool__(self):
        """Возвращает True если пользователь авторизован"""
        return self.logged_in 