import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

# ga
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.analytics.data_v1beta.types import Filter as GAFilter

from orm.author import Author
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic
from services.db import local_session
from services.redis import redis
from utils.logger import root_logger as logger

GOOGLE_KEYFILE_PATH = os.environ.get("GOOGLE_KEYFILE_PATH", "/dump/google-service.json")
GOOGLE_PROPERTY_ID = os.environ.get("GOOGLE_PROPERTY_ID", "")


class ViewedStorage:
    """
    Класс для хранения и доступа к данным о просмотрах.
    Использует Redis в качестве основного хранилища и Google Analytics для сбора новых данных.
    """
    lock = asyncio.Lock()
    views_by_shout = {}
    shouts_by_topic = {}
    shouts_by_author = {}
    views = None
    period = 60 * 60  # каждый час
    analytics_client: Optional[BetaAnalyticsDataClient] = None
    auth_result = None
    running = False
    redis_views_key = None
    last_update_timestamp = 0
    start_date = datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    async def init():
        """Подключение к клиенту Google Analytics и загрузка данных о просмотрах из Redis"""
        self = ViewedStorage
        async with self.lock:
            # Загрузка предварительно подсчитанных просмотров из Redis
            await self.load_views_from_redis()

            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", GOOGLE_KEYFILE_PATH)
            if GOOGLE_KEYFILE_PATH and os.path.isfile(GOOGLE_KEYFILE_PATH):
                # Using a default constructor instructs the client to use the credentials
                # specified in GOOGLE_APPLICATION_CREDENTIALS environment variable.
                self.analytics_client = BetaAnalyticsDataClient()
                logger.info(" * Google Analytics credentials accepted")

                # Запуск фоновой задачи
                _task = asyncio.create_task(self.worker())
            else:
                logger.warning(" * please, add Google Analytics credentials file")
                self.running = False

    @staticmethod
    async def load_views_from_redis():
        """Загрузка предварительно подсчитанных просмотров из Redis"""
        self = ViewedStorage
        
        # Подключаемся к Redis если соединение не установлено
        if not redis._client:
            await redis.connect()
        
        # Получаем список всех ключей migrated_views_* и находим самый последний
        keys = await redis.execute("KEYS", "migrated_views_*")
        if not keys:
            logger.warning(" * No migrated_views keys found in Redis")
            return
        
        # Фильтруем только ключи timestamp формата (исключаем migrated_views_slugs)
        timestamp_keys = [k for k in keys if k != "migrated_views_slugs"]
        if not timestamp_keys:
            logger.warning(" * No migrated_views timestamp keys found in Redis")
            return
            
        # Сортируем по времени создания (в названии ключа) и берем последний
        timestamp_keys.sort()
        latest_key = timestamp_keys[-1]
        self.redis_views_key = latest_key
        
        # Получаем метку времени создания для установки start_date
        timestamp = await redis.execute("HGET", latest_key, "_timestamp")
        if timestamp:
            self.last_update_timestamp = int(timestamp)
            timestamp_dt = datetime.fromtimestamp(int(timestamp))
            self.start_date = timestamp_dt.strftime("%Y-%m-%d")
            
            # Если данные сегодняшние, считаем их актуальными
            now_date = datetime.now().strftime("%Y-%m-%d")
            if now_date == self.start_date:
                logger.info(" * Views data is up to date!")
            else:
                logger.warning(f" * Views data is from {self.start_date}, may need update")
                
        # Выводим информацию о количестве загруженных записей
        total_entries = await redis.execute("HGET", latest_key, "_total")
        if total_entries:
            logger.info(f" * {total_entries} shouts with views loaded from Redis key: {latest_key}")

    # noinspection PyTypeChecker
    @staticmethod
    async def update_pages():
        """Запрос всех страниц от Google Analytics, отсортированных по количеству просмотров"""
        self = ViewedStorage
        logger.info(" ⎧ views update from Google Analytics ---")
        if self.running:
            try:
                start = time.time()
                async with self.lock:
                    if self.analytics_client:
                        request = RunReportRequest(
                            property=f"properties/{GOOGLE_PROPERTY_ID}",
                            dimensions=[Dimension(name="pagePath")],
                            metrics=[Metric(name="screenPageViews")],
                            date_ranges=[DateRange(start_date=self.start_date, end_date="today")],
                        )
                        response = self.analytics_client.run_report(request)
                        if response and isinstance(response.rows, list):
                            slugs = set()
                            for row in response.rows:
                                print(
                                    row.dimension_values[0].value,
                                    row.metric_values[0].value,
                                )
                                # Извлечение путей страниц из ответа Google Analytics
                                if isinstance(row.dimension_values, list):
                                    page_path = row.dimension_values[0].value
                                    slug = page_path.split("discours.io/")[-1]
                                    fresh_views = int(row.metric_values[0].value)

                                    # Обновление данных в хранилище
                                    self.views_by_shout[slug] = self.views_by_shout.get(slug, 0)
                                    self.views_by_shout[slug] += fresh_views
                                    self.update_topics(slug)

                                    # Запись путей страниц для логирования
                                    slugs.add(slug)

                                logger.info(f" ⎪ collected pages: {len(slugs)} ")

                        end = time.time()
                        logger.info(" ⎪ views update time: %fs " % (end - start))
            except Exception as error:
                logger.error(error)
                self.running = False

    @staticmethod
    async def get_shout(shout_slug="", shout_id=0) -> int:
        """
        Получение метрики просмотров shout по slug или id.
        
        Args:
            shout_slug: Slug публикации
            shout_id: ID публикации
            
        Returns:
            int: Количество просмотров
        """
        self = ViewedStorage
        
        # Получаем данные из Redis для новой схемы хранения
        if not redis._client:
            await redis.connect()
            
        fresh_views = self.views_by_shout.get(shout_slug, 0)
        
        # Если есть id, пытаемся получить данные из Redis по ключу migrated_views_<timestamp>
        if shout_id and self.redis_views_key:
            precounted_views = await redis.execute("HGET", self.redis_views_key, str(shout_id))
            if precounted_views:
                return fresh_views + int(precounted_views)
                
        # Если нет id или данных, пытаемся получить по slug из отдельного хеша
        precounted_views = await redis.execute("HGET", "migrated_views_slugs", shout_slug)
        if precounted_views:
            return fresh_views + int(precounted_views)
            
        return fresh_views

    @staticmethod
    async def get_shout_media(shout_slug) -> Dict[str, int]:
        """Получение метрики воспроизведения shout по slug."""
        self = ViewedStorage

        # TODO: get media plays from Google Analytics

        return self.views_by_shout.get(shout_slug, 0)

    @staticmethod
    async def get_topic(topic_slug) -> int:
        """Получение суммарного значения просмотров темы."""
        self = ViewedStorage
        views_count = 0
        for shout_slug in self.shouts_by_topic.get(topic_slug, []):
            views_count += await self.get_shout(shout_slug=shout_slug)
        return views_count

    @staticmethod
    async def get_author(author_slug) -> int:
        """Получение суммарного значения просмотров автора."""
        self = ViewedStorage
        views_count = 0
        for shout_slug in self.shouts_by_author.get(author_slug, []):
            views_count += await self.get_shout(shout_slug=shout_slug)
        return views_count

    @staticmethod
    def update_topics(shout_slug):
        """Обновление счетчиков темы по slug shout"""
        self = ViewedStorage
        with local_session() as session:
            # Определение вспомогательной функции для избежания повторения кода
            def update_groups(dictionary, key, value):
                dictionary[key] = list(set(dictionary.get(key, []) + [value]))

            # Обновление тем и авторов с использованием вспомогательной функции
            for [_st, topic] in (
                session.query(ShoutTopic, Topic).join(Topic).join(Shout).where(Shout.slug == shout_slug).all()
            ):
                update_groups(self.shouts_by_topic, topic.slug, shout_slug)

            for [_st, author] in (
                session.query(ShoutAuthor, Author).join(Author).join(Shout).where(Shout.slug == shout_slug).all()
            ):
                update_groups(self.shouts_by_author, author.slug, shout_slug)

    @staticmethod
    async def stop():
        """Остановка фоновой задачи"""
        self = ViewedStorage
        async with self.lock:
            self.running = False
            logger.info("ViewedStorage worker was stopped.")

    @staticmethod
    async def worker():
        """Асинхронная задача обновления"""
        failed = 0
        self = ViewedStorage

        while self.running:
            try:
                await self.update_pages()
                failed = 0
            except Exception as exc:
                failed += 1
                logger.debug(exc)
                logger.info(" - update failed #%d, wait 10 secs" % failed)
                if failed > 3:
                    logger.info(" - views update failed, not trying anymore")
                    self.running = False
                    break
            if failed == 0:
                when = datetime.now(timezone.utc) + timedelta(seconds=self.period)
                t = format(when.astimezone().isoformat())
                logger.info("       ⎩ next update: %s" % (t.split("T")[0] + " " + t.split("T")[1].split(".")[0]))
                await asyncio.sleep(self.period)
            else:
                await asyncio.sleep(10)
                logger.info(" - try to update views again")

    @staticmethod
    async def update_slug_views(slug: str) -> int:
        """
        Получает fresh статистику просмотров для указанного slug.

        Args:
            slug: Идентификатор страницы

        Returns:
            int: Количество просмотров
        """
        self = ViewedStorage
        if not self.analytics_client:
            logger.warning("Google Analytics client not initialized")
            return 0

        try:
            # Создаем фильтр для точного совпадения конца URL
            request = RunReportRequest(
                property=f"properties/{GOOGLE_PROPERTY_ID}",
                date_ranges=[DateRange(start_date=self.start_date, end_date="today")],
                dimensions=[Dimension(name="pagePath")],
                dimension_filter=GAFilter(
                    field_name="pagePath",
                    string_filter=GAFilter.StringFilter(
                        value=f".*/{slug}$",  # Используем регулярное выражение для точного совпадения конца URL
                        match_type=GAFilter.StringFilter.MatchType.FULL_REGEXP,
                        case_sensitive=False,  # Включаем чувствительность к регистру для точности
                    ),
                ),
                metrics=[Metric(name="screenPageViews")],
            )

            response = self.analytics_client.run_report(request)

            if not response.rows:
                return 0

            views = int(response.rows[0].metric_values[0].value)
            # Кэшируем результат
            self.views_by_shout[slug] = views
            return views

        except Exception as e:
            logger.error(f"Google Analytics API Error: {e}")
            return 0 