from typing import TypeVar, Any, Dict, Generic, Callable

from sqlalchemy import create_engine, Column, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.schema import Table

from settings import SQLITE_URI

engine = create_engine(f'sqlite:///{SQLITE_URI}', convert_unicode=True, echo=False)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
global_session = Session()

T = TypeVar("T")

REGISTRY: Dict[str, type] = {}


class Base(declarative_base()):
    __table__: Table
    __tablename__: str
    __new__: Callable
    __init__: Callable

    __abstract__: bool = True
    __table_args__ = {"extend_existing": True}
    id: int = Column(Integer, primary_key=True)
    session = global_session

    def __init_subclass__(cls, **kwargs):
        REGISTRY[cls.__name__] = cls

    @classmethod
    def create(cls: Generic[T], **kwargs) -> Generic[T]:
        instance = cls(**kwargs)
        return instance.save()

    def save(self) -> Generic[T]:
        self.session.add(self)
        self.session.commit()
        return self

    def dict(self) -> Dict[str, Any]:
        column_names = self.__table__.columns.keys()
        return {c: getattr(self, c) for c in column_names}
