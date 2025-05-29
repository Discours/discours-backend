import math
import time
import traceback
import warnings
from typing import Any, Callable, Dict, TypeVar

import orjson
import sqlalchemy
from sqlalchemy import (
    JSON,
    Column,
    Engine,
    Index,
    Integer,
    create_engine,
    event,
    exc,
    func,
    inspect,
    text,
)
from sqlalchemy.orm import Session, configure_mappers, declarative_base, joinedload
from sqlalchemy.sql.schema import Table

from settings import DB_URL
from utils.logger import root_logger as logger

if DB_URL.startswith("postgres"):
    engine = create_engine(
        DB_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,  # Время ожидания свободного соединения
        pool_recycle=1800,  # Время жизни соединения
        pool_pre_ping=True,  # Добавить проверку соединений
        connect_args={
            "sslmode": "disable",
            "connect_timeout": 40,  # Добавить таймаут подключения
        },
    )
else:
    engine = create_engine(DB_URL, echo=False, connect_args={"check_same_thread": False})

inspector = inspect(engine)
configure_mappers()
T = TypeVar("T")
REGISTRY: Dict[str, type] = {}
FILTERED_FIELDS = ["_sa_instance_state", "search_vector"]


def create_table_if_not_exists(engine, table):
    """
    Создает таблицу, если она не существует в базе данных.

    Args:
        engine: SQLAlchemy движок базы данных
        table: Класс модели SQLAlchemy
    """
    inspector = inspect(engine)
    if table and not inspector.has_table(table.__tablename__):
        try:
            table.__table__.create(engine)
            logger.info(f"Table '{table.__tablename__}' created.")
        except exc.OperationalError as e:
            # Проверяем, содержит ли ошибка упоминание о том, что индекс уже существует
            if "already exists" in str(e):
                logger.warning(f"Skipping index creation for table '{table.__tablename__}': {e}")
            else:
                # Перевыбрасываем ошибку, если она не связана с дублированием
                raise
    else:
        logger.info(f"Table '{table.__tablename__}' ok.")


def sync_indexes():
    """
    Синхронизирует индексы в БД с индексами, определенными в моделях SQLAlchemy.
    Создает недостающие индексы, если они определены в моделях, но отсутствуют в БД.

    Использует pg_catalog для PostgreSQL для получения списка существующих индексов.
    """
    if not DB_URL.startswith("postgres"):
        logger.warning("Функция sync_indexes поддерживается только для PostgreSQL.")
        return

    logger.info("Начинаем синхронизацию индексов в базе данных...")

    # Получаем все существующие индексы в БД
    with local_session() as session:
        existing_indexes_query = text("""
            SELECT 
                t.relname AS table_name,
                i.relname AS index_name
            FROM 
                pg_catalog.pg_class i
            JOIN 
                pg_catalog.pg_index ix ON ix.indexrelid = i.oid
            JOIN 
                pg_catalog.pg_class t ON t.oid = ix.indrelid
            JOIN 
                pg_catalog.pg_namespace n ON n.oid = i.relnamespace
            WHERE 
                i.relkind = 'i'
                AND n.nspname = 'public'
                AND t.relkind = 'r'
            ORDER BY 
                t.relname, i.relname;
        """)

        existing_indexes = {row[1].lower() for row in session.execute(existing_indexes_query)}
        logger.debug(f"Найдено {len(existing_indexes)} существующих индексов в БД")

        # Проверяем каждую модель и её индексы
        for _model_name, model_class in REGISTRY.items():
            if hasattr(model_class, "__table__") and hasattr(model_class, "__table_args__"):
                table_args = model_class.__table_args__

                # Если table_args - это кортеж, ищем в нём объекты Index
                if isinstance(table_args, tuple):
                    for arg in table_args:
                        if isinstance(arg, Index):
                            index_name = arg.name.lower()

                            # Проверяем, существует ли индекс в БД
                            if index_name not in existing_indexes:
                                logger.info(
                                    f"Создаем отсутствующий индекс {index_name} для таблицы {model_class.__tablename__}"
                                )

                                # Создаем индекс если он отсутствует
                                try:
                                    arg.create(engine)
                                    logger.info(f"Индекс {index_name} успешно создан")
                                except Exception as e:
                                    logger.error(f"Ошибка при создании индекса {index_name}: {e}")
                            else:
                                logger.debug(f"Индекс {index_name} уже существует")

        # Анализируем таблицы для оптимизации запросов
        for model_name, model_class in REGISTRY.items():
            if hasattr(model_class, "__tablename__"):
                try:
                    session.execute(text(f"ANALYZE {model_class.__tablename__}"))
                    logger.debug(f"Таблица {model_class.__tablename__} проанализирована")
                except Exception as e:
                    logger.error(f"Ошибка при анализе таблицы {model_class.__tablename__}: {e}")

    logger.info("Синхронизация индексов завершена.")


# noinspection PyUnusedLocal
def local_session(src=""):
    return Session(bind=engine, expire_on_commit=False)


class Base(declarative_base()):
    __table__: Table
    __tablename__: str
    __new__: Callable
    __init__: Callable
    __allow_unmapped__ = True
    __abstract__ = True
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    def __init_subclass__(cls, **kwargs):
        REGISTRY[cls.__name__] = cls

    def dict(self) -> Dict[str, Any]:
        """
        Конвертирует ORM объект в словарь.

        Пропускает атрибуты, которые отсутствуют в объекте, но присутствуют в колонках таблицы.
        Преобразует JSON поля в словари.
        Добавляет синтетическое поле .stat, если оно существует.

        Returns:
            Dict[str, Any]: Словарь с атрибутами объекта
        """
        column_names = filter(lambda x: x not in FILTERED_FIELDS, self.__table__.columns.keys())
        data = {}
        try:
            for column_name in column_names:
                try:
                    # Проверяем, существует ли атрибут в объекте
                    if hasattr(self, column_name):
                        value = getattr(self, column_name)
                        # Проверяем, является ли значение JSON и декодируем его при необходимости
                        if isinstance(value, (str, bytes)) and isinstance(
                            self.__table__.columns[column_name].type, JSON
                        ):
                            try:
                                data[column_name] = orjson.loads(value)
                            except (TypeError, orjson.JSONDecodeError) as e:
                                logger.error(f"Error decoding JSON for column '{column_name}': {e}")
                                data[column_name] = value
                        else:
                            data[column_name] = value
                    else:
                        # Пропускаем атрибут, если его нет в объекте (может быть добавлен после миграции)
                        logger.debug(f"Skipping missing attribute '{column_name}' for {self.__class__.__name__}")
                except AttributeError as e:
                    logger.warning(f"Attribute error for column '{column_name}': {e}")
            # Добавляем синтетическое поле .stat если оно существует
            if hasattr(self, "stat"):
                data["stat"] = self.stat
        except Exception as e:
            logger.error(f"Error occurred while converting object to dictionary: {e}")
        return data

    def update(self, values: Dict[str, Any]) -> None:
        for key, value in values.items():
            if hasattr(self, key):
                setattr(self, key, value)


# make_searchable(Base.metadata)
# Base.metadata.create_all(bind=engine)


# Функция для вывода полного трейсбека при предупреждениях
def warning_with_traceback(message: Warning | str, category, filename: str, lineno: int, file=None, line=None):
    tb = traceback.format_stack()
    tb_str = "".join(tb)
    return f"{message} ({filename}, {lineno}): {category.__name__}\n{tb_str}"


# Установка функции вывода трейсбека для предупреждений SQLAlchemy
warnings.showwarning = warning_with_traceback
warnings.simplefilter("always", exc.SAWarning)


# Функция для извлечения SQL-запроса из контекста
def get_statement_from_context(context):
    query = ""
    compiled = context.compiled
    if compiled:
        compiled_statement = compiled.string
        compiled_parameters = compiled.params
        if compiled_statement:
            if compiled_parameters:
                try:
                    # Безопасное форматирование параметров
                    query = compiled_statement % compiled_parameters
                except Exception as e:
                    logger.error(f"Error formatting query: {e}")
            else:
                query = compiled_statement
    if query:
        query = query.replace("\n", " ").replace("  ", " ").replace("  ", " ").strip()
    return query


# Обработчик события перед выполнением запроса
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.query_start_time = time.time()
    conn.cursor_id = id(cursor)  # Отслеживание конкретного курсора


# Обработчик события после выполнения запроса
@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if hasattr(conn, "cursor_id") and conn.cursor_id == id(cursor):
        query = get_statement_from_context(context)
        if query:
            elapsed = time.time() - conn.query_start_time
            if elapsed > 1:
                query_end = query[-16:]
                query = query.split(query_end)[0] + query_end
                logger.debug(query)
                elapsed_n = math.floor(elapsed)
                logger.debug("*" * (elapsed_n))
                logger.debug(f"{elapsed:.3f} s")
        del conn.cursor_id  # Удаление идентификатора курсора после выполнения


def get_json_builder():
    """
    Возвращает подходящие функции для построения JSON объектов в зависимости от драйвера БД
    """
    dialect = engine.dialect.name
    json_cast = lambda x: x  # noqa: E731
    if dialect.startswith("postgres"):
        json_cast = lambda x: func.cast(x, sqlalchemy.Text)  # noqa: E731
        return func.json_build_object, func.json_agg, json_cast
    elif dialect.startswith("sqlite") or dialect.startswith("mysql"):
        return func.json_object, func.json_group_array, json_cast
    else:
        raise NotImplementedError(f"JSON builder not implemented for dialect {dialect}")


# Используем их в коде
json_builder, json_array_builder, json_cast = get_json_builder()

# Fetch all shouts, with authors preloaded
# This function is used for search indexing


async def fetch_all_shouts(session=None):
    """Fetch all published shouts for search indexing with authors preloaded"""
    from orm.shout import Shout

    close_session = False
    if session is None:
        session = local_session()
        close_session = True

    try:
        # Fetch only published and non-deleted shouts with authors preloaded
        query = (
            session.query(Shout)
            .options(joinedload(Shout.authors))
            .filter(Shout.published_at.is_not(None), Shout.deleted_at.is_(None))
        )
        shouts = query.all()
        return shouts
    except Exception as e:
        logger.error(f"Error fetching shouts for search indexing: {e}")
        return []
    finally:
        if close_session:
            session.close()
