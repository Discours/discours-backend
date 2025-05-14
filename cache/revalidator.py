import asyncio

from cache.cache import (
    cache_author,
    cache_topic,
    get_cached_author,
    get_cached_topic,
    invalidate_cache_by_prefix,
)
from resolvers.stat import get_with_stat
from services.redis import redis
from utils.logger import root_logger as logger

CACHE_REVALIDATION_INTERVAL = 300  # 5 minutes


class CacheRevalidationManager:
    def __init__(self, interval=CACHE_REVALIDATION_INTERVAL):
        """Инициализация менеджера с заданным интервалом проверки (в секундах)."""
        self.interval = interval
        self.items_to_revalidate = {"authors": set(), "topics": set(), "shouts": set(), "reactions": set()}
        self.lock = asyncio.Lock()
        self.running = True
        self.MAX_BATCH_SIZE = 10  # Максимальное количество элементов для поштучной обработки
        self._redis = redis  # Добавлена инициализация _redis для доступа к Redis-клиенту

    async def start(self):
        """Запуск фонового воркера для ревалидации кэша."""
        # Проверяем, что у нас есть соединение с Redis
        if not self._redis._client:
            logger.warning("Redis connection not established. Waiting for connection...")
            try:
                await self._redis.connect()
                logger.info("Redis connection established for revalidation manager")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                
        self.task = asyncio.create_task(self.revalidate_cache())

    async def revalidate_cache(self):
        """Циклическая проверка и ревалидация кэша каждые self.interval секунд."""
        try:
            while self.running:
                await asyncio.sleep(self.interval)
                await self.process_revalidation()
        except asyncio.CancelledError:
            logger.info("Revalidation worker was stopped.")
        except Exception as e:
            logger.error(f"An error occurred in the revalidation worker: {e}")

    async def process_revalidation(self):
        """Обновление кэша для всех сущностей, требующих ревалидации."""
        # Проверяем соединение с Redis
        if not self._redis._client:
            return  # Выходим из метода, если не удалось подключиться
                
        async with self.lock:
            # Ревалидация кэша авторов
            if self.items_to_revalidate["authors"]:
                logger.debug(f"Revalidating {len(self.items_to_revalidate['authors'])} authors")
                for author_id in self.items_to_revalidate["authors"]:
                    if author_id == "all":
                        await invalidate_cache_by_prefix("authors")
                        break
                    author = await get_cached_author(author_id, get_with_stat)
                    if author:
                        await cache_author(author)
                self.items_to_revalidate["authors"].clear()

            # Ревалидация кэша тем
            if self.items_to_revalidate["topics"]:
                logger.debug(f"Revalidating {len(self.items_to_revalidate['topics'])} topics")
                for topic_id in self.items_to_revalidate["topics"]:
                    if topic_id == "all":
                        await invalidate_cache_by_prefix("topics")
                        break
                    topic = await get_cached_topic(topic_id)
                    if topic:
                        await cache_topic(topic)
                self.items_to_revalidate["topics"].clear()

            # Ревалидация шаутов (публикаций)
            if self.items_to_revalidate["shouts"]:
                shouts_count = len(self.items_to_revalidate["shouts"])
                logger.debug(f"Revalidating {shouts_count} shouts")

                # Проверяем наличие специального флага 'all'
                if "all" in self.items_to_revalidate["shouts"]:
                    await invalidate_cache_by_prefix("shouts")
                # Если элементов много, но не 'all', используем специфический подход
                elif shouts_count > self.MAX_BATCH_SIZE:
                    # Инвалидируем только collections keys, которые затрагивают много сущностей
                    collection_keys = await asyncio.create_task(self._redis.execute("KEYS", "shouts:*"))
                    if collection_keys:
                        await self._redis.execute("DEL", *collection_keys)
                        logger.debug(f"Удалено {len(collection_keys)} коллекционных ключей шаутов")

                    # Обновляем кеш каждого конкретного шаута
                    for shout_id in self.items_to_revalidate["shouts"]:
                        if shout_id != "all":
                            # Точечная инвалидация для каждого shout_id
                            specific_keys = [f"shout:id:{shout_id}"]
                            for key in specific_keys:
                                await self._redis.execute("DEL", key)
                                logger.debug(f"Удален ключ кеша {key}")
                else:
                    # Если элементов немного, обрабатываем каждый
                    for shout_id in self.items_to_revalidate["shouts"]:
                        if shout_id != "all":
                            # Точечная инвалидация для каждого shout_id
                            specific_keys = [f"shout:id:{shout_id}"]
                            for key in specific_keys:
                                await self._redis.execute("DEL", key)
                                logger.debug(f"Удален ключ кеша {key}")

                self.items_to_revalidate["shouts"].clear()

            # Аналогично для реакций - точечная инвалидация
            if self.items_to_revalidate["reactions"]:
                reactions_count = len(self.items_to_revalidate["reactions"])
                logger.debug(f"Revalidating {reactions_count} reactions")

                if "all" in self.items_to_revalidate["reactions"]:
                    await invalidate_cache_by_prefix("reactions")
                elif reactions_count > self.MAX_BATCH_SIZE:
                    # Инвалидируем только collections keys для реакций
                    collection_keys = await asyncio.create_task(self._redis.execute("KEYS", "reactions:*"))
                    if collection_keys:
                        await self._redis.execute("DEL", *collection_keys)
                        logger.debug(f"Удалено {len(collection_keys)} коллекционных ключей реакций")

                    # Точечная инвалидация для каждой реакции
                    for reaction_id in self.items_to_revalidate["reactions"]:
                        if reaction_id != "all":
                            specific_keys = [f"reaction:id:{reaction_id}"]
                            for key in specific_keys:
                                await self._redis.execute("DEL", key)
                                logger.debug(f"Удален ключ кеша {key}")
                else:
                    # Точечная инвалидация для каждой реакции
                    for reaction_id in self.items_to_revalidate["reactions"]:
                        if reaction_id != "all":
                            specific_keys = [f"reaction:id:{reaction_id}"]
                            for key in specific_keys:
                                await self._redis.execute("DEL", key)
                                logger.debug(f"Удален ключ кеша {key}")

                self.items_to_revalidate["reactions"].clear()

    def mark_for_revalidation(self, entity_id, entity_type):
        """Отметить сущность для ревалидации."""
        if entity_id and entity_type:
            self.items_to_revalidate[entity_type].add(entity_id)

    def invalidate_all(self, entity_type):
        """Пометить для инвалидации все элементы указанного типа."""
        logger.debug(f"Marking all {entity_type} for invalidation")
        # Особый флаг для полной инвалидации
        self.items_to_revalidate[entity_type].add("all")

    async def stop(self):
        """Остановка фонового воркера."""
        self.running = False
        if hasattr(self, "task"):
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


revalidation_manager = CacheRevalidationManager()
