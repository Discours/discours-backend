from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship

from auth.orm import Author
from orm.base import BaseModel as Base
from utils.logger import root_logger as logger


class NotificationEntity(Enum):
    """
    Перечисление сущностей для уведомлений.
    Определяет типы объектов, к которым относятся уведомления.
    """

    TOPIC = "topic"
    COMMENT = "comment"
    SHOUT = "shout"
    AUTHOR = "author"
    COMMUNITY = "community"

    @classmethod
    def from_string(cls, value: str) -> "NotificationEntity":
        """
        Создает экземпляр сущности уведомления из строки.

        Args:
            value (str): Строковое представление сущности.

        Returns:
            NotificationEntity: Экземпляр сущности уведомления.
        """
        try:
            return cls(value)
        except ValueError:
            logger.error(f"Неверная сущность уведомления: {value}")
            raise ValueError("Неверная сущность уведомления")  # noqa: B904


class NotificationAction(Enum):
    """
    Перечисление действий для уведомлений.
    Определяет типы событий, которые могут происходить с сущностями.
    """

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MENTION = "mention"
    REACT = "react"
    FOLLOW = "follow"
    INVITE = "invite"

    @classmethod
    def from_string(cls, value: str) -> "NotificationAction":
        """
        Создает экземпляр действия уведомления из строки.

        Args:
            value (str): Строковое представление действия.

        Returns:
            NotificationAction: Экземпляр действия уведомления.
        """
        try:
            return cls(value)
        except ValueError:
            logger.error(f"Неверное действие уведомления: {value}")
            raise ValueError("Неверное действие уведомления")  # noqa: B904


# Оставляем для обратной совместимости
NotificationStatus = Enum("NotificationStatus", ["UNREAD", "READ", "ARCHIVED"])
NotificationKind = NotificationAction  # Для совместимости со старым кодом


class NotificationSeen(Base):
    __tablename__ = "notification_seen"

    viewer = Column(ForeignKey("author.id"), primary_key=True)
    notification = Column(ForeignKey("notification.id"), primary_key=True)


class Notification(Base):
    __tablename__ = "notification"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entity = Column(String, nullable=False)
    action = Column(String, nullable=False)
    payload = Column(JSON, nullable=True)

    status = Column(SQLAlchemyEnum(NotificationStatus), default=NotificationStatus.UNREAD)
    kind = Column(SQLAlchemyEnum(NotificationKind), nullable=False)

    seen = relationship(Author, secondary="notification_seen")

    def set_entity(self, entity: NotificationEntity):
        """Устанавливает сущность уведомления."""
        self.entity = entity.value

    def get_entity(self) -> NotificationEntity:
        """Возвращает сущность уведомления."""
        return NotificationEntity.from_string(self.entity)

    def set_action(self, action: NotificationAction):
        """Устанавливает действие уведомления."""
        self.action = action.value

    def get_action(self) -> NotificationAction:
        """Возвращает действие уведомления."""
        return NotificationAction.from_string(self.action)
