from sqlalchemy import select, desc, and_, update

from auth.credentials import AuthCredentials
from services.schema import query, mutation
from auth.authenticate import login_required
from services.db import local_session
from orm import Notification


@query.field("loadNotifications")
@login_required
async def load_notifications(_, info, params=None):
    if params is None:
        params = {}

    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id

    limit = params.get('limit', 50)
    offset = params.get('offset', 0)

    q = select(Notification).where(
        Notification.user == user_id
    ).order_by(desc(Notification.createdAt)).limit(limit).offset(offset)

    notifications = []
    with local_session() as session:
        total_count = session.query(Notification).where(
            Notification.user == user_id
        ).count()

        total_unread_count = session.query(Notification).where(
            and_(
                Notification.user == user_id,
                Notification.seen == False
            )
        ).count()

        for [notification] in session.execute(q):
            notification.type = notification.type.name
            notifications.append(notification)

    return {
        "notifications": notifications,
        "totalCount": total_count,
        "totalUnreadCount": total_unread_count
    }


@mutation.field("markNotificationAsRead")
@login_required
async def mark_notification_as_read(_, info, notification_id: int):
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id

    with local_session() as session:
        notification = session.query(Notification).where(
            and_(Notification.id == notification_id, Notification.user == user_id)
        ).one()
        notification.seen = True
        session.commit()

    return {}


@mutation.field("markAllNotificationsAsRead")
@login_required
async def mark_all_notifications_as_read(_, info):
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id

    statement = update(Notification).where(
        and_(
            Notification.user == user_id,
            Notification.seen == False
        )
    ).values(seen=True)

    with local_session() as session:
        try:
            session.execute(statement)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[mark_all_notifications_as_read] error: {str(e)}")

    return {}
