import warnings

from typing import Type

from sqlalchemy import String, Column, ForeignKey, types, UniqueConstraint

from orm.base import Base, REGISTRY, engine, global_session


class ClassType(types.TypeDecorator):
    impl = types.String

    @property
    def python_type(self):
        return NotImplemented

    def process_literal_param(self, value, dialect):
        return NotImplemented

    def process_bind_param(self, value, dialect):
        return value.__name__ if isinstance(value, type) else str(value)

    def process_result_value(self, value, dialect):
        class_ = REGISTRY.get(value)
        if class_ is None:
            warnings.warn(f"Can't find class <{value}>,find it yourself 😊", stacklevel=2)
        return class_


class Role(Base):
    __tablename__ = 'role'
    name: str = Column(String, nullable=False, unique=True, comment="Role Name")


class Operation(Base):
    __tablename__ = 'operation'
    name: str = Column(String, nullable=False, unique=True, comment="Operation Name")


class Resource(Base):
    __tablename__ = "resource"
    resource_class: Type[Base] = Column(ClassType, nullable=False, unique=True, comment="Resource class")
    name: str = Column(String, nullable=False, unique=True, comment="Resource name")


class Permission(Base):
    __tablename__ = "permission"
    __table_args__ = (UniqueConstraint("role_id", "operation_id", "resource_id"), {"extend_existing": True})

    role_id: int = Column(ForeignKey("role.id", ondelete="CASCADE"), nullable=False, comment="Role")
    operation_id: int = Column(ForeignKey("operation.id", ondelete="CASCADE"), nullable=False, comment="Operation")
    resource_id: int = Column(ForeignKey("operation.id", ondelete="CASCADE"), nullable=False, comment="Resource")


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    ops = [
        Permission(role_id=1, operation_id=1, resource_id=1),
        Permission(role_id=1, operation_id=2, resource_id=1),
        Permission(role_id=1, operation_id=3, resource_id=1),
        Permission(role_id=1, operation_id=4, resource_id=1),
        Permission(role_id=2, operation_id=4, resource_id=1)
    ]
    global_session.add_all(ops)
    global_session.commit()
