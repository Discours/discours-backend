"""
Тесты для проверки функций работы с базой данных
"""
import pytest
import time
from sqlalchemy import create_engine, Column, Integer, String, inspect
from sqlalchemy.orm import declarative_base, Session

from services.db import create_table_if_not_exists, get_column_names_without_virtual, local_session

# Создаем базовую модель для тестирования
Base = declarative_base()

class TestModel(Base):
    """Тестовая модель для проверки функций базы данных"""
    __tablename__ = 'test_model'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String, nullable=True)
    
    def __init__(self, name: str = None, description: str = None):
        self.name = name
        self.description = description

class TestDatabaseFunctions:
    """Тесты для функций работы с базой данных"""

    def test_create_table_if_not_exists(self, tmp_path):
        """
        Проверка создания таблицы, если она не существует
        """
        # Создаем временную базу данных SQLite
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)

        # Создаем таблицу
        create_table_if_not_exists(engine, TestModel)

        # Проверяем, что таблица создана
        inspector = inspect(engine)
        assert inspector.has_table('test_model')

    def test_get_column_names_without_virtual(self):
        """
        Проверка получения имен колонок без виртуальных полей
        """
        columns = get_column_names_without_virtual(TestModel)

        # Ожидаем, что будут только реальные колонки
        assert set(columns) == {'id', 'name', 'description'}

    def test_local_session_management(self):
        """
        Проверка создания и управления локальной сессией
        """
        # Создаем сессию
        session = local_session()

        try:
            # Проверяем, что сессия создана корректно
            assert isinstance(session, Session)

            # Проверяем, что сессия работает с существующими таблицами
            # Используем Author вместо TestModel
            from auth.orm import Author
            authors_count = session.query(Author).count()
            assert isinstance(authors_count, int)

        finally:
            # Всегда закрываем сессию
            session.close()
