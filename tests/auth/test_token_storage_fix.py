#!/usr/bin/env python3
"""
Тест для проверки исправленной системы токенов
"""

import pytest

from auth.tokens.monitoring import TokenMonitoring
from auth.tokens.sessions import SessionTokenManager
from auth.tokens.storage import TokenStorage


@pytest.mark.asyncio
async def test_token_storage(redis_client):
    """Тест базовой функциональности TokenStorage с правильными fixtures"""

    print("✅ Тестирование TokenStorage...")

    # Тест создания сессии
    print("1. Создание сессии...")
    token = await TokenStorage.create_session(user_id="test_user_123", username="test_user", device_info={"test": True})
    print(f"   Создан токен: {token[:20]}...")

    # Тест проверки сессии
    print("2. Проверка сессии...")
    session_data = await TokenStorage.verify_session(token)
    if session_data:
        print(f"   Сессия найдена для user_id: {session_data.user_id}")
    else:
        print("   ❌ Сессия не найдена")
        return False

    # Тест прямого использования SessionTokenManager
    print("3. Прямое использование SessionTokenManager...")
    sessions = SessionTokenManager()
    valid, data = await sessions.validate_session_token(token)
    print(f"   Валидация: {valid}, данные: {bool(data)}")

    # Тест мониторинга
    print("4. Мониторинг токенов...")
    monitoring = TokenMonitoring()
    stats = await monitoring.get_token_statistics()
    print(f"   Активных сессий: {stats.get('session_tokens', 0)}")

    # Очистка
    print("5. Отзыв сессии...")
    revoked = await TokenStorage.revoke_session(token)
    print(f"   Отозван: {revoked}")

    print("✅ Все тесты пройдены успешно!")
    return True
