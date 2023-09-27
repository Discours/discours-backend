from sqlalchemy import select, desc, and_

from auth.credentials import AuthCredentials
from base.resolvers import query
from auth.authenticate import login_required
from base.orm import local_session
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

    with local_session() as session:
        total_count = session.query(Notification).where(
            Notification.user == user_id
        ).count()

        total_unread_count = session.query(Notification).where(
            and_(
                Notification.user == user_id,
                Notification.seen is False
            )
        ).count()

        notifications = session.execute(q).fetchall()

    return {
        "notifications": notifications,
        "totalCount": total_count,
        "totalUnreadCount": total_unread_count
    }
