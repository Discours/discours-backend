import pytest
from auth.identity import Password

def test_password_verify():
    # Создаем пароль
    original_password = "test_password123"
    hashed_password = Password.encode(original_password)

    # Проверяем корректный пароль
    assert Password.verify(original_password, hashed_password) is True

    # Проверяем некорректный пароль
    assert Password.verify("wrong_password", hashed_password) is False
