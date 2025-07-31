from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    REACTION = "reaction"

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

    viewer: Mapped[int] = mapped_column(ForeignKey("author.id"))
    notification: Mapped[int] = mapped_column(ForeignKey("notification.id"))

    __table_args__ = (
        PrimaryKeyConstraint(viewer, notification),
        Index("idx_notification_seen_viewer", "viewer"),
        Index("idx_notification_seen_notification", "notification"),
        {"extend_existing": True},
    )


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    entity: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[NotificationStatus] = mapped_column(default=NotificationStatus.UNREAD)
    kind: Mapped[NotificationKind] = mapped_column(nullable=False)

    seen = relationship(Author, secondary="notification_seen")

    __table_args__ = (
        Index("idx_notification_created_at", "created_at"),
        Index("idx_notification_status", "status"),
        Index("idx_notification_kind", "kind"),
        {"extend_existing": True},
    )

    def set_entity(self, entity: NotificationEntity) -> None:
        """Устанавливает сущность уведомления."""
        self.entity = entity.value

    def get_entity(self) -> NotificationEntity:
        """Возвращает сущность уведомления."""
        return NotificationEntity.from_string(self.entity)

    def set_action(self, action: NotificationAction) -> None:
        """Устанавливает действие уведомления."""
        self.action = action.value

    def get_action(self) -> NotificationAction:
        """Возвращает действие уведомления."""
        return NotificationAction.from_string(self.action)
