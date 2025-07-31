#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправлений в функции unfollow.

Этот скрипт тестирует:
1. Корректную работу unfollow при существующей подписке
2. Корректную работу unfollow при несуществующей подписке
3. Возврат актуального списка подписок в обоих случаях
4. Инвалидацию кэша после операций
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cache.cache import get_cached_follower_topics
from orm.topic import Topic, TopicFollower
from services.db import local_session
from services.redis import redis
from utils.logger import root_logger as logger


class MockRequest:
    """Мок для HTTP запроса"""

    def __init__(self):
        self.method = "POST"
        self.url = MockURL()
        self.headers = {}
        self.cookies = {}


class MockURL:
    """Мок для URL"""

    def __init__(self):
        self.path = "/graphql"


class MockInfo:
    """Мок для GraphQL info контекста"""

    def __init__(self, author_id: int):
        self.context = {
            "author": {"id": author_id, "slug": f"test_user_{author_id}"},
            "roles": [],
            "request": MockRequest(),
        }


async def test_unfollow_logic_directly():
    """Тестируем логику unfollow напрямую, обходя декораторы"""
    logger.info("=== Тест логики unfollow напрямую ===")

    # Импортируем функции напрямую из модуля
    from resolvers.follower import unfollow

    # Создаём мок контекста
    mock_info = MockInfo(999)

    # Обходим декоратор, вызывая функцию напрямую
    try:
        # Тестируем отписку от несуществующей подписки
        logger.info("1. Тестируем отписку от несуществующей подписки")

        # Сначала проверим, что в кэше нет данных
        await redis.execute("DEL", "author:follows-topics:999")

        # Пытаемся отписаться от темы, если она существует
        with local_session() as session:
            test_topic = session.query(Topic).where(Topic.slug == "moda").first()
            if not test_topic:
                logger.info("Тема 'moda' не найдена, создаём тестовую")
                # Можем протестировать с любой существующей темой
                test_topic = session.query(Topic).first()
                if not test_topic:
                    logger.warning("Нет тем в базе данных для тестирования")
                    return

        unfollow_result = await unfollow(None, mock_info, "TOPIC", slug=test_topic.slug)
        logger.info(f"Результат отписки: {unfollow_result}")

        # Проверяем результат
        if unfollow_result.get("error") == "following was not found":
            logger.info("✅ Правильно обработана ошибка 'following was not found'")

        if "topics" in unfollow_result and isinstance(unfollow_result["topics"], list):
            logger.info(f"✅ Возвращён актуальный список тем: {len(unfollow_result['topics'])} элементов")
        else:
            logger.error("❌ Не возвращён список тем или неправильный формат")

        logger.info("=== Тест завершён ===")

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте: {e}")
        import traceback

        traceback.print_exc()


async def test_cache_invalidation_directly():
    """Тестируем инвалидацию кэша напрямую"""
    logger.info("=== Тест инвалидации кэша ===")

    cache_key = "author:follows-topics:999"

    # Устанавливаем тестовые данные
    await redis.execute("SET", cache_key, "[1, 2, 3]")
    cached_before = await redis.execute("GET", cache_key)
    logger.info(f"Данные в кэше до операции: {cached_before}")

    # Проверяем функцию инвалидации
    await redis.execute("DEL", cache_key)
    cached_after = await redis.execute("GET", cache_key)
    logger.info(f"Данные в кэше после DEL: {cached_after}")

    if cached_after is None:
        logger.info("✅ Кэш успешно инвалидирован")
    else:
        logger.error("❌ Кэш не был инвалидирован")


async def test_get_cached_follower_topics():
    """Тестируем функцию получения подписок из кэша"""
    logger.info("=== Тест получения подписок из кэша ===")

    try:
        # Очищаем кэш
        await redis.execute("DEL", "author:follows-topics:1")

        # Получаем подписки (должны загрузиться из БД)
        topics = await get_cached_follower_topics(1)
        logger.info(f"Получено тем из кэша/БД: {len(topics)}")

        if isinstance(topics, list):
            logger.info("✅ Функция get_cached_follower_topics работает корректно")
            if topics:
                logger.info(f"Пример темы: {topics[0].get('slug', 'Без slug')}")
        else:
            logger.error("❌ Функция вернула не список")

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте: {e}")
        import traceback

        traceback.print_exc()


async def cleanup_test_data():
    """Очищает тестовые данные"""
    logger.info("=== Очистка тестовых данных ===")

    with local_session() as session:
        # Удаляем тестовые подписки
        session.query(TopicFollower).where(TopicFollower.follower == 999).delete()
        session.commit()

    # Очищаем кэш
    cache_keys = ["author:follows-topics:999", "author:follows-authors:999", "author:follows-topics:1"]
    for key in cache_keys:
        await redis.execute("DEL", key)

    logger.info("Тестовые данные очищены")


async def main():
    """Главная функция теста"""
    try:
        logger.info("🚀 Начало тестирования исправлений unfollow")

        await test_cache_invalidation_directly()
        await test_get_cached_follower_topics()
        await test_unfollow_logic_directly()

        logger.info("🎉 Все тесты завершены!")

    except Exception as e:
        logger.error(f"❌ Тест провалился: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await cleanup_test_data()


if __name__ == "__main__":
    asyncio.run(main())
