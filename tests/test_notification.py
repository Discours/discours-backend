import pytest

from orm.notification import (
    NotificationStatus,
    NotificationKind,
    NotificationEntity,
    NotificationAction,
)

def test_notification_status():
    """Тестирование перечисления статусов уведомлений."""
    assert NotificationStatus.UNREAD == NotificationStatus.from_string("UNREAD")
    assert NotificationStatus.READ == NotificationStatus.from_string("READ")

    with pytest.raises(ValueError):
        NotificationStatus.from_string("INVALID_STATUS")

def test_notification_kind():
    """Тестирование перечисления типов уведомлений."""
    assert NotificationKind.COMMENT == NotificationKind.from_string("COMMENT")
    assert NotificationKind.MENTION == NotificationKind.from_string("MENTION")

    with pytest.raises(ValueError):
        NotificationKind.from_string("INVALID_KIND")

def test_notification_entity():
    """Тестирование перечисления сущностей уведомлений."""
    assert NotificationEntity.TOPIC == NotificationEntity.from_string("topic")
    assert NotificationEntity.SHOUT == NotificationEntity.from_string("shout")

    with pytest.raises(ValueError):
        NotificationEntity.from_string("INVALID_ENTITY")

def test_notification_action():
    """Тестирование перечисления действий уведомлений."""
    assert NotificationAction.CREATE == NotificationAction.from_string("create")
    assert NotificationAction.UPDATE == NotificationAction.from_string("update")

    with pytest.raises(ValueError):
        NotificationAction.from_string("INVALID_ACTION")
