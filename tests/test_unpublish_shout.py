#!/usr/bin/env python3
"""
Тест мутации unpublishShout для снятия поста с публикации.
Проверяет различные сценарии:
- Успешное снятие публикации автором
- Снятие публикации редактором
- Отказ в доступе неавторизованному пользователю
- Отказ в доступе не-автору без прав редактора
- Обработку несуществующих публикаций
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from auth.orm import Author
from orm.community import assign_role_to_user
from orm.shout import Shout
from resolvers.editor import unpublish_shout
from services.db import local_session

# Настройка логгера
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class MockInfo:
    """Мок для GraphQL info контекста"""

    def __init__(self, author_id: int, roles: list[str] | None = None) -> None:
        if author_id:
            self.context = {
                "author": {"id": author_id},
                "roles": roles or ["reader", "author"],
                "request": None,  # Важно: указываем None для тестового режима
            }
        else:
            # Для неавторизованного пользователя
            self.context = {
                "author": {},
                "roles": [],
                "request": None,
            }


async def setup_test_data() -> tuple[Author, Shout, Author]:
    """Создаем тестовые данные: автора, публикацию и другого автора"""
    logger.info("🔧 Настройка тестовых данных")

    current_time = int(time.time())

    with local_session() as session:
        # Создаем первого автора (владельца публикации)
        test_author = session.query(Author).filter(Author.email == "test_author@example.com").first()
        if not test_author:
            test_author = Author(email="test_author@example.com", name="Test Author", slug="test-author")
            test_author.set_password("password123")
            session.add(test_author)
            session.flush()  # Получаем ID

        # Создаем второго автора (не владельца)
        other_author = session.query(Author).filter(Author.email == "other_author@example.com").first()
        if not other_author:
            other_author = Author(email="other_author@example.com", name="Other Author", slug="other-author")
            other_author.set_password("password456")
            session.add(other_author)
            session.flush()

        # Создаем опубликованную публикацию
        test_shout = session.query(Shout).filter(Shout.slug == "test-shout-published").first()
        if not test_shout:
            test_shout = Shout(
                title="Test Published Shout",
                slug="test-shout-published",
                body="This is a test published shout content",
                layout="article",
                created_by=test_author.id,
                created_at=current_time,
                published_at=current_time,  # Публикация опубликована
                community=1,
                seo="Test shout for unpublish testing",
            )
            session.add(test_shout)
        else:
            # Убедимся что публикация опубликована
            test_shout.published_at = current_time
            session.add(test_shout)

        session.commit()

        # Добавляем роли пользователям в БД
        assign_role_to_user(test_author.id, "reader")
        assign_role_to_user(test_author.id, "author")
        assign_role_to_user(other_author.id, "reader")
        assign_role_to_user(other_author.id, "author")

        logger.info(
            f"   ✅ Созданы: автор {test_author.id}, другой автор {other_author.id}, публикация {test_shout.id}"
        )

        return test_author, test_shout, other_author


async def test_successful_unpublish_by_author() -> None:
    """Тестируем успешное снятие публикации автором"""
    logger.info("📰 Тестирование успешного снятия публикации автором")

    test_author, test_shout, _ = await setup_test_data()

    # Тест 1: Успешное снятие публикации автором
    logger.info("   📝 Тест 1: Снятие публикации автором")
    info = MockInfo(test_author.id)

    result = await unpublish_shout(None, info, test_shout.id)

    if not result.error:
        logger.info("   ✅ Снятие публикации успешно")

        # Проверяем, что published_at теперь None
        with local_session() as session:
            updated_shout = session.query(Shout).filter(Shout.id == test_shout.id).first()
            if updated_shout and updated_shout.published_at is None:
                logger.info("   ✅ published_at корректно установлен в None")
            else:
                logger.error(
                    f"   ❌ published_at неверен: {updated_shout.published_at if updated_shout else 'shout not found'}"
                )

        if result.shout and result.shout.id == test_shout.id:
            logger.info("   ✅ Возвращен корректный объект публикации")
        else:
            logger.error("   ❌ Возвращен неверный объект публикации")
    else:
        logger.error(f"   ❌ Ошибка снятия публикации: {result.error}")


async def test_unpublish_by_editor() -> None:
    """Тестируем снятие публикации редактором"""
    logger.info("👨‍💼 Тестирование снятия публикации редактором")

    test_author, test_shout, other_author = await setup_test_data()

    # Восстанавливаем публикацию для теста
    with local_session() as session:
        shout = session.query(Shout).filter(Shout.id == test_shout.id).first()
        if shout:
            shout.published_at = int(time.time())
            session.add(shout)
            session.commit()

    # Добавляем роль "editor" другому автору в БД
    assign_role_to_user(other_author.id, "reader")
    assign_role_to_user(other_author.id, "author")
    assign_role_to_user(other_author.id, "editor")

    logger.info("   📝 Тест: Снятие публикации редактором")
    info = MockInfo(other_author.id, roles=["reader", "author", "editor"])  # Другой автор с ролью редактора

    result = await unpublish_shout(None, info, test_shout.id)

    if not result.error:
        logger.info("   ✅ Редактор успешно снял публикацию")

        with local_session() as session:
            updated_shout = session.query(Shout).filter(Shout.id == test_shout.id).first()
            if updated_shout and updated_shout.published_at is None:
                logger.info("   ✅ published_at корректно установлен в None редактором")
            else:
                logger.error(
                    f"   ❌ published_at неверен после действий редактора: {updated_shout.published_at if updated_shout else 'shout not found'}"
                )
    else:
        logger.error(f"   ❌ Ошибка снятия публикации редактором: {result.error}")


async def test_access_denied_scenarios() -> None:
    """Тестируем сценарии отказа в доступе"""
    logger.info("🚫 Тестирование отказа в доступе")

    test_author, test_shout, other_author = await setup_test_data()

    # Восстанавливаем публикацию для теста
    with local_session() as session:
        shout = session.query(Shout).filter(Shout.id == test_shout.id).first()
        if shout:
            shout.published_at = int(time.time())
            session.add(shout)
            session.commit()

    # Тест 1: Неавторизованный пользователь
    logger.info("   📝 Тест 1: Неавторизованный пользователь")
    info = MockInfo(0)  # Нет author_id

    try:
        result = await unpublish_shout(None, info, test_shout.id)
        logger.error("   ❌ Неожиданный результат для неавторизованного: ошибка не была выброшена")
    except Exception as e:
        if "Требуется авторизация" in str(e):
            logger.info("   ✅ Корректно отклонен неавторизованный пользователь")
        else:
            logger.error(f"   ❌ Неожиданная ошибка для неавторизованного: {e}")

    # Тест 2: Не-автор без прав редактора
    logger.info("   📝 Тест 2: Не-автор без прав редактора")
    # Убеждаемся что у other_author нет роли editor
    assign_role_to_user(other_author.id, "reader")
    assign_role_to_user(other_author.id, "author")
    info = MockInfo(other_author.id, roles=["reader", "author"])  # Другой автор без прав редактора

    result = await unpublish_shout(None, info, test_shout.id)

    if result.error == "Access denied":
        logger.info("   ✅ Корректно отклонен не-автор без прав редактора")
    else:
        logger.error(f"   ❌ Неожиданный результат для не-автора: {result.error}")


async def test_nonexistent_shout() -> None:
    """Тестируем обработку несуществующих публикаций"""
    logger.info("👻 Тестирование несуществующих публикаций")

    test_author, _, _ = await setup_test_data()

    logger.info("   📝 Тест: Несуществующая публикация")
    info = MockInfo(test_author.id)

    # Используем заведомо несуществующий ID
    nonexistent_id = 999999
    result = await unpublish_shout(None, info, nonexistent_id)

    if result.error == "Shout not found":
        logger.info("   ✅ Корректно обработана несуществующая публикация")
    else:
        logger.error(f"   ❌ Неожиданный результат для несуществующей публикации: {result.error}")


async def test_already_unpublished_shout() -> None:
    """Тестируем снятие публикации с уже неопубликованной публикации"""
    logger.info("📝 Тестирование уже неопубликованной публикации")

    test_author, test_shout, _ = await setup_test_data()

    # Убеждаемся что публикация не опубликована
    with local_session() as session:
        shout = session.query(Shout).filter(Shout.id == test_shout.id).first()
        if shout:
            shout.published_at = None
            session.add(shout)
            session.commit()

    logger.info("   📝 Тест: Снятие публикации с уже неопубликованной")
    info = MockInfo(test_author.id)

    result = await unpublish_shout(None, info, test_shout.id)

    # Функция должна отработать нормально даже для уже неопубликованной публикации
    if not result.error:
        logger.info("   ✅ Операция с уже неопубликованной публикацией прошла успешно")

        with local_session() as session:
            updated_shout = session.query(Shout).filter(Shout.id == test_shout.id).first()
            if updated_shout and updated_shout.published_at is None:
                logger.info("   ✅ published_at остался None")
            else:
                logger.error(
                    f"   ❌ published_at изменился неожиданно: {updated_shout.published_at if updated_shout else 'shout not found'}"
                )
    else:
        logger.error(f"   ❌ Неожиданная ошибка для уже неопубликованной публикации: {result.error}")


async def cleanup_test_data() -> None:
    """Очистка тестовых данных"""
    logger.info("🧹 Очистка тестовых данных")

    try:
        with local_session() as session:
            # Удаляем тестовую публикацию
            test_shout = session.query(Shout).filter(Shout.slug == "test-shout-published").first()
            if test_shout:
                session.delete(test_shout)

            logger.info("   ✅ Тестовые данные очищены")
    except Exception as e:
        logger.warning(f"   ⚠️ Ошибка при очистке: {e}")


async def main() -> None:
    """Главная функция теста"""
    logger.info("🚀 Запуск тестов unpublish_shout")

    try:
        await test_successful_unpublish_by_author()
        await test_unpublish_by_editor()
        await test_access_denied_scenarios()
        await test_nonexistent_shout()
        await test_already_unpublished_shout()

        logger.info("✅ Все тесты unpublish_shout завершены успешно")

    except Exception as e:
        logger.error(f"❌ Ошибка в тестах: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await cleanup_test_data()


if __name__ == "__main__":
    asyncio.run(main())
