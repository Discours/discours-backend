import logging
import math
import time
import traceback
import warnings
from io import TextIOWrapper
from typing import Any, TypeVar

import sqlalchemy
from sqlalchemy import create_engine, event, exc, func, inspect
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, configure_mappers, joinedload
from sqlalchemy.pool import StaticPool

from orm.base import BaseModel
from settings import DB_URL
from utils.logger import root_logger as logger

# Global variables
logger = logging.getLogger(__name__)

# Database configuration
engine = create_engine(DB_URL, echo=False, poolclass=StaticPool if "sqlite" in DB_URL else None)
ENGINE = engine  # Backward compatibility alias
inspector = inspect(engine)
# Session = sessionmaker(engine)
configure_mappers()
T = TypeVar("T")
FILTERED_FIELDS = ["_sa_instance_state", "search_vector"]

# make_searchable(Base.metadata)
# Base.metadata.create_all(bind=engine)


# Функция для вывода полного трейсбека при предупреждениях
def warning_with_traceback(
    message: Warning | str,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: TextIOWrapper | None = None,
    line: str | None = None,
) -> None:
    tb = traceback.format_stack()
    tb_str = "".join(tb)
    print(f"{message} ({filename}, {lineno}): {category.__name__}\n{tb_str}")


# Установка функции вывода трейсбека для предупреждений SQLAlchemy
warnings.showwarning = warning_with_traceback  # type: ignore[assignment]
warnings.simplefilter("always", exc.SAWarning)


# Функция для извлечения SQL-запроса из контекста
def get_statement_from_context(context: Connection) -> str | None:
    query = ""
    compiled = getattr(context, "compiled", None)
    if compiled:
        compiled_statement = getattr(compiled, "string", None)
        compiled_parameters = getattr(compiled, "params", None)
        if compiled_statement:
            if compiled_parameters:
                try:
                    # Безопасное форматирование параметров
                    query = compiled_statement % compiled_parameters
                except Exception as e:
                    logger.exception(f"Error formatting query: {e}")
            else:
                query = compiled_statement
    if query:
        query = query.replace("\n", " ").replace("  ", " ").replace("  ", " ").strip()
    return query


# Обработчик события перед выполнением запроса
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: dict[str, Any] | None,
    context: Connection,
    executemany: bool,
) -> None:
    conn.query_start_time = time.time()  # type: ignore[attr-defined]
    conn.cursor_id = id(cursor)  # type: ignore[attr-defined]


# Обработчик события после выполнения запроса
@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: dict[str, Any] | None,
    context: Connection,
    executemany: bool,
) -> None:
    if hasattr(conn, "cursor_id") and conn.cursor_id == id(cursor):
        query = get_statement_from_context(context)
        if query:
            elapsed = time.time() - getattr(conn, "query_start_time", time.time())
            if elapsed > 1:
                query_end = query[-16:]
                query = query.split(query_end)[0] + query_end
                logger.debug(query)
                elapsed_n = math.floor(elapsed)
                logger.debug("*" * (elapsed_n))
                logger.debug(f"{elapsed:.3f} s")
        if hasattr(conn, "cursor_id"):
            delattr(conn, "cursor_id")  # Удаление идентификатора курсора после выполнения


def get_json_builder() -> tuple[Any, Any, Any]:
    """
    Возвращает подходящие функции для построения JSON объектов в зависимости от драйвера БД
    """
    dialect = engine.dialect.name
    json_cast = lambda x: x  # noqa: E731
    if dialect.startswith("postgres"):
        json_cast = lambda x: func.cast(x, sqlalchemy.Text)  # noqa: E731
        return func.json_build_object, func.json_agg, json_cast
    if dialect.startswith(("sqlite", "mysql")):
        return func.json_object, func.json_group_array, json_cast
    msg = f"JSON builder not implemented for dialect {dialect}"
    raise NotImplementedError(msg)


# Используем их в коде
json_builder, json_array_builder, json_cast = get_json_builder()

# Fetch all shouts, with authors preloaded
# This function is used for search indexing


def fetch_all_shouts(session: Session | None = None) -> list[Any]:
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
            .filter(Shout.published_at is not None, Shout.deleted_at is None)
        )
        return query.all()
    except Exception as e:
        logger.exception(f"Error fetching shouts for search indexing: {e}")
        return []
    finally:
        if close_session:
            # Подавляем SQLAlchemy deprecated warning для синхронной сессии
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                session.close()


def get_column_names_without_virtual(model_cls: type[BaseModel]) -> list[str]:
    """Получает имена колонок модели без виртуальных полей"""
    try:
        column_names: list[str] = [
            col.name for col in model_cls.__table__.columns if not getattr(col, "_is_virtual", False)
        ]
        return column_names
    except AttributeError:
        return []


def get_primary_key_columns(model_cls: type[BaseModel]) -> list[str]:
    """Получает имена первичных ключей модели"""
    try:
        return [col.name for col in model_cls.__table__.primary_key.columns]
    except AttributeError:
        return ["id"]


def create_table_if_not_exists(engine: Engine, model_cls: type[BaseModel]) -> None:
    """Creates table for the given model if it doesn't exist"""
    if hasattr(model_cls, "__tablename__"):
        inspector = inspect(engine)
        if not inspector.has_table(model_cls.__tablename__):
            model_cls.__table__.create(engine)
            logger.info(f"Created table: {model_cls.__tablename__}")


def format_sql_warning(
    message: str | Warning,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: TextIOWrapper | None = None,
    line: str | None = None,
) -> str:
    """Custom warning formatter for SQL warnings"""
    return f"SQL Warning: {message}\n"


# Apply the custom warning formatter
def _set_warning_formatter() -> None:
    """Set custom warning formatter"""
    import warnings

    original_formatwarning = warnings.formatwarning

    def custom_formatwarning(
        message: Warning | str,
        category: type[Warning],
        filename: str,
        lineno: int,
        file: TextIOWrapper | None = None,
        line: str | None = None,
    ) -> str:
        return format_sql_warning(message, category, filename, lineno, file, line)

    warnings.formatwarning = custom_formatwarning  # type: ignore[assignment]


_set_warning_formatter()


def upsert_on_duplicate(table: sqlalchemy.Table, **values: Any) -> sqlalchemy.sql.Insert:
    """
    Performs an upsert operation (insert or update on conflict)
    """
    if engine.dialect.name == "sqlite":
        return insert(table).values(**values).on_conflict_do_update(index_elements=["id"], set_=values)
    # For other databases, implement appropriate upsert logic
    return table.insert().values(**values)


def get_sql_functions() -> dict[str, Any]:
    """Returns database-specific SQL functions"""
    if engine.dialect.name == "sqlite":
        return {
            "now": sqlalchemy.func.datetime("now"),
            "extract_epoch": lambda x: sqlalchemy.func.strftime("%s", x),
            "coalesce": sqlalchemy.func.coalesce,
        }
    return {
        "now": sqlalchemy.func.now(),
        "extract_epoch": sqlalchemy.func.extract("epoch", sqlalchemy.text("?")),
        "coalesce": sqlalchemy.func.coalesce,
    }


# noinspection PyUnusedLocal
def local_session(src: str = "") -> Session:
    """Create a new database session"""
    return Session(bind=engine, expire_on_commit=False)


# Also export the type for type hints
__all__ = ["engine", "local_session"]
