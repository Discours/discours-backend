import pytest

from orm.notification import (
    NotificationStatus,
    NotificationEntity,
    NotificationAction,
)

def test_notification_status():
    """Тестирование перечисления статусов уведомлений."""
    assert NotificationStatus.UNREAD == NotificationStatus.UNREAD
    assert NotificationStatus.READ == NotificationStatus.READ

    # Проверяем, что старый метод from_string больше не работает
    with pytest.raises(AttributeError):
        NotificationStatus.from_string("UNREAD")

def test_notification_entity():
    """Тестирование перечисления сущностей уведомлений."""
    assert NotificationEntity.TOPIC == NotificationEntity.from_string("topic")
    assert NotificationEntity.SHOUT == NotificationEntity.from_string("shout")
    assert NotificationEntity.COMMENT == NotificationEntity.from_string("comment")

    with pytest.raises(ValueError):
        NotificationEntity.from_string("INVALID_ENTITY")

def test_notification_action():
    """Тестирование перечисления действий уведомлений."""
    assert NotificationAction.CREATE == NotificationAction.from_string("create")
    assert NotificationAction.UPDATE == NotificationAction.from_string("update")
    assert NotificationAction.REACT == NotificationAction.from_string("react")

    with pytest.raises(ValueError):
        NotificationAction.from_string("INVALID_ACTION")
