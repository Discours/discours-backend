from typing import TypeVar, Any, Dict, Generic, Callable

from sqlalchemy import create_engine, Column, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Table

from settings import DB_URL

if DB_URL.startswith("sqlite"):
    engine = create_engine(DB_URL)
else:
    engine = create_engine(
        DB_URL, convert_unicode=True, echo=False, pool_size=10, max_overflow=20
    )

T = TypeVar("T")

REGISTRY: Dict[str, type] = {}


def local_session():
    return Session(bind=engine, expire_on_commit=False)


class Base(declarative_base()):
    __table__: Table
    __tablename__: str
    __new__: Callable
    __init__: Callable

    __abstract__: bool = True
    __table_args__ = {"extend_existing": True}
    id: int = Column(Integer, primary_key=True)

    def __init_subclass__(cls, **kwargs):
        REGISTRY[cls.__name__] = cls

    @classmethod
    def create(cls: Generic[T], **kwargs) -> Generic[T]:
        instance = cls(**kwargs)
        return instance.save()

    def save(self) -> Generic[T]:
        with local_session() as session:
            session.add(self)
            session.commit()
        return self

    def update(self, input):
        column_names = self.__table__.columns.keys()
        for (name, value) in input.items():
            if name in column_names:
                setattr(self, name, value)

    def dict(self) -> Dict[str, Any]:
        column_names = self.__table__.columns.keys()
        return {c: getattr(self, c) for c in column_names}
