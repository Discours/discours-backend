#!/usr/bin/env python3
"""
Тест мутации updateSecurity для смены пароля и email.
Проверяет различные сценарии:
- Смена пароля
- Смена email
- Одновременная смена пароля и email
- Валидация и обработка ошибок
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from auth.orm import Author
from resolvers.auth import update_security
from services.db import local_session

# Настройка логгера
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class MockInfo:
    """Мок для GraphQL info контекста"""

    def __init__(self, author_id: int) -> None:
        self.context = {
            "author": {"id": author_id},
            "roles": ["reader", "author"],  # Добавляем необходимые роли
        }


async def test_password_change() -> None:
    """Тестируем смену пароля"""
    logger.info("🔐 Тестирование смены пароля")

    # Создаем тестового пользователя
    with local_session() as session:
        # Проверяем, есть ли тестовый пользователь
        test_user = session.query(Author).filter(Author.email == "test@example.com").first()

        if not test_user:
            test_user = Author(email="test@example.com", name="Test User", slug="test-user")
            test_user.set_password("old_password123")
            session.add(test_user)
            session.commit()
            logger.info(f"   Создан тестовый пользователь с ID {test_user.id}")
        else:
            test_user.set_password("old_password123")
            session.add(test_user)
            session.commit()
            logger.info(f"   Используется существующий пользователь с ID {test_user.id}")

    # Тест 1: Успешная смена пароля
    logger.info("   📝 Тест 1: Успешная смена пароля")
    info = MockInfo(test_user.id)

    result = await update_security(
        None,
        info,
        email=None,
        old_password="old_password123",
        new_password="new_password456",
    )

    if result["success"]:
        logger.info("   ✅ Смена пароля успешна")

        # Проверяем, что новый пароль работает
        with local_session() as session:
            updated_user = session.query(Author).filter(Author.id == test_user.id).first()
            if updated_user.verify_password("new_password456"):
                logger.info("   ✅ Новый пароль работает")
            else:
                logger.error("   ❌ Новый пароль не работает")
    else:
        logger.error(f"   ❌ Ошибка смены пароля: {result['error']}")

    # Тест 2: Неверный старый пароль
    logger.info("   📝 Тест 2: Неверный старый пароль")

    result = await update_security(
        None,
        info,
        email=None,
        old_password="wrong_password",
        new_password="another_password789",
    )

    if not result["success"] and result["error"] == "incorrect old password":
        logger.info("   ✅ Корректно отклонен неверный старый пароль")
    else:
        logger.error(f"   ❌ Неожиданный результат: {result}")

    # Тест 3: Пароли не совпадают
    logger.info("   📝 Тест 3: Пароли не совпадают")

    result = await update_security(
        None,
        info,
        email=None,
        old_password="new_password456",
        new_password="password1",
    )

    if not result["success"] and result["error"] == "PASSWORDS_NOT_MATCH":
        logger.info("   ✅ Корректно отклонены несовпадающие пароли")
    else:
        logger.error(f"   ❌ Неожиданный результат: {result}")


async def test_email_change() -> None:
    """Тестируем смену email"""
    logger.info("📧 Тестирование смены email")

    with local_session() as session:
        test_user = session.query(Author).filter(Author.email == "test@example.com").first()
        if not test_user:
            logger.error("   ❌ Тестовый пользователь не найден")
            return

    # Тест 1: Успешная инициация смены email
    logger.info("   📝 Тест 1: Инициация смены email")
    info = MockInfo(test_user.id)

    result = await update_security(
        None,
        info,
        email="newemail@example.com",
        old_password="new_password456",
        new_password=None,
    )

    if result["success"]:
        logger.info("   ✅ Смена email инициирована")

        # Проверяем pending_email
        with local_session() as session:
            updated_user = session.query(Author).filter(Author.id == test_user.id).first()
            if updated_user.pending_email == "newemail@example.com":
                logger.info("   ✅ pending_email установлен корректно")
                if updated_user.email_change_token:
                    logger.info("   ✅ Токен подтверждения создан")
                else:
                    logger.error("   ❌ Токен подтверждения не создан")
            else:
                logger.error(f"   ❌ pending_email неверен: {updated_user.pending_email}")
    else:
        logger.error(f"   ❌ Ошибка инициации смены email: {result['error']}")

    # Тест 2: Email уже существует
    logger.info("   📝 Тест 2: Email уже существует")

    # Создаем другого пользователя с новым email
    with local_session() as session:
        existing_user = session.query(Author).filter(Author.email == "existing@example.com").first()
        if not existing_user:
            existing_user = Author(email="existing@example.com", name="Existing User", slug="existing-user")
            existing_user.set_password("password123")
            session.add(existing_user)
            session.commit()

    result = await update_security(
        None,
        info,
        email="existing@example.com",
        old_password="new_password456",
        new_password=None,
    )

    if not result["success"] and result["error"] == "email already exists":
        logger.info("   ✅ Корректно отклонен существующий email")
    else:
        logger.error(f"   ❌ Неожиданный результат: {result}")


async def test_combined_changes() -> None:
    """Тестируем одновременную смену пароля и email"""
    logger.info("🔄 Тестирование одновременной смены пароля и email")

    with local_session() as session:
        test_user = session.query(Author).filter(Author.email == "test@example.com").first()
        if not test_user:
            logger.error("   ❌ Тестовый пользователь не найден")
            return

    info = MockInfo(test_user.id)

    result = await update_security(
        None,
        info,
        email="combined@example.com",
        old_password="new_password456",
        new_password="combined_password789",
    )

    if result["success"]:
        logger.info("   ✅ Одновременная смена успешна")

        # Проверяем изменения
        with local_session() as session:
            updated_user = session.query(Author).filter(Author.id == test_user.id).first()

            # Проверяем пароль
            if updated_user.verify_password("combined_password789"):
                logger.info("   ✅ Новый пароль работает")
            else:
                logger.error("   ❌ Новый пароль не работает")

            # Проверяем pending email
            if updated_user.pending_email == "combined@example.com":
                logger.info("   ✅ pending_email установлен корректно")
            else:
                logger.error(f"   ❌ pending_email неверен: {updated_user.pending_email}")
    else:
        logger.error(f"   ❌ Ошибка одновременной смены: {result['error']}")


async def test_validation_errors() -> None:
    """Тестируем различные ошибки валидации"""
    logger.info("⚠️ Тестирование ошибок валидации")

    with local_session() as session:
        test_user = session.query(Author).filter(Author.email == "test@example.com").first()
        if not test_user:
            logger.error("   ❌ Тестовый пользователь не найден")
            return

    info = MockInfo(test_user.id)

    # Тест 1: Нет параметров для изменения
    logger.info("   📝 Тест 1: Нет параметров для изменения")
    result = await update_security(None, info, email=None, old_password="combined_password789", new_password=None)

    if not result["success"] and result["error"] == "VALIDATION_ERROR":
        logger.info("   ✅ Корректно отклонен запрос без параметров")
    else:
        logger.error(f"   ❌ Неожиданный результат: {result}")

    # Тест 2: Слабый пароль
    logger.info("   📝 Тест 2: Слабый пароль")
    result = await update_security(None, info, email=None, old_password="combined_password789", new_password="123")

    if not result["success"] and result["error"] == "WEAK_PASSWORD":
        logger.info("   ✅ Корректно отклонен слабый пароль")
    else:
        logger.error(f"   ❌ Неожиданный результат: {result}")

    # Тест 3: Неверный формат email
    logger.info("   📝 Тест 3: Неверный формат email")
    result = await update_security(
        None,
        info,
        email="invalid-email",
        old_password="combined_password789",
        new_password=None,
    )

    if not result["success"] and result["error"] == "INVALID_EMAIL":
        logger.info("   ✅ Корректно отклонен неверный email")
    else:
        logger.error(f"   ❌ Неожиданный результат: {result}")


async def cleanup_test_data() -> None:
    """Очищает тестовые данные"""
    logger.info("🧹 Очистка тестовых данных")

    with local_session() as session:
        # Удаляем тестовых пользователей
        test_emails = ["test@example.com", "existing@example.com"]
        for email in test_emails:
            user = session.query(Author).filter(Author.email == email).first()
            if user:
                session.delete(user)

        session.commit()

    logger.info("Тестовые данные очищены")


async def main() -> None:
    """Главная функция теста"""
    try:
        logger.info("🚀 Начало тестирования updateSecurity")

        await test_password_change()
        await test_email_change()
        await test_combined_changes()
        await test_validation_errors()

        logger.info("🎉 Все тесты updateSecurity прошли успешно!")

    except Exception:
        logger.exception("❌ Тест провалился")
        import traceback

        traceback.print_exc()
    finally:
        await cleanup_test_data()


if __name__ == "__main__":
    asyncio.run(main())
