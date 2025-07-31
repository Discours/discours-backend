import math
import time
import traceback
import warnings
from io import TextIOWrapper
from typing import Any, Type, TypeVar

import sqlalchemy
from sqlalchemy import create_engine, event, exc, func, inspect
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Session, configure_mappers
from sqlalchemy.pool import StaticPool

from settings import DB_URL
from utils.logger import root_logger as logger

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
                except Exception:
                    logger.exception("Error formatting query")
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


def create_table_if_not_exists(
    connection_or_engine_or_session: Connection | Engine | Session, model_cls: Type[DeclarativeBase]
) -> None:
    """Creates table for the given model if it doesn't exist"""

    # Handle different input types
    if isinstance(connection_or_engine_or_session, Session):
        # Use session's bind
        connection = connection_or_engine_or_session.get_bind()
        should_close = False
    elif isinstance(connection_or_engine_or_session, Engine):
        # Get a connection from engine
        connection = connection_or_engine_or_session.connect()
        should_close = True
    else:
        # Already a connection
        connection = connection_or_engine_or_session
        should_close = False

    try:
        inspector = inspect(connection)
        if not inspector.has_table(model_cls.__tablename__):
            # Use SQLAlchemy's built-in table creation instead of manual SQL generation
            model_cls.__table__.create(bind=connection, checkfirst=False)  # type: ignore[attr-defined]
            logger.info(f"Created table: {model_cls.__tablename__}")
    finally:
        # Close connection only if we created it
        if should_close:
            if hasattr(connection, "close"):
                connection.close()  # type: ignore[attr-defined]


def get_column_names_without_virtual(model_cls: Type[DeclarativeBase]) -> list[str]:
    """Получает имена колонок модели без виртуальных полей"""
    try:
        column_names: list[str] = [
            col.name for col in model_cls.__table__.columns if not getattr(col, "_is_virtual", False)
        ]
        return column_names
    except AttributeError:
        return []


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

    def custom_formatwarning(
        message: str, category: type[Warning], filename: str, lineno: int, line: str | None = None
    ) -> str:
        return f"{category.__name__}: {message}\n"

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
