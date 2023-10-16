import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import and_

from base.orm import local_session
from orm import Reaction, Shout, Notification, User
from orm.notification import NotificationType
from orm.reaction import ReactionKind
from services.notifications.sse import connection_manager


def shout_to_shout_data(shout):
    return {
        "title": shout.title,
        "slug": shout.slug
    }


def user_to_user_data(user):
    return {
        "id": user.id,
        "name": user.name,
        "slug": user.slug,
        "userpic": user.userpic
    }


def update_prev_notification(notification, user, reaction):
    notification_data = json.loads(notification.data)

    notification_data["users"] = [u for u in notification_data["users"] if u['id'] != user.id]
    notification_data["users"].append(user_to_user_data(user))
    notification_data["reactionIds"].append(reaction.id)

    notification.data = json.dumps(notification_data, ensure_ascii=False)
    notification.seen = False
    notification.occurrences = notification.occurrences + 1
    notification.createdAt = datetime.now(tz=timezone.utc)


class NewReactionNotificator:
    def __init__(self, reaction_id):
        self.reaction_id = reaction_id

    async def run(self):
        with local_session() as session:
            reaction = session.query(Reaction).where(Reaction.id == self.reaction_id).one()
            shout = session.query(Shout).where(Shout.id == reaction.shout).one()
            user = session.query(User).where(User.id == reaction.createdBy).one()
            notify_user_ids = []

            if reaction.kind == ReactionKind.COMMENT:
                parent_reaction = None
                if reaction.replyTo:
                    parent_reaction = session.query(Reaction).where(Reaction.id == reaction.replyTo).one()
                    if parent_reaction.createdBy != reaction.createdBy:
                        prev_new_reply_notification = session.query(Notification).where(
                            and_(
                                Notification.user == shout.createdBy,
                                Notification.type == NotificationType.NEW_REPLY,
                                Notification.shout == shout.id,
                                Notification.reaction == parent_reaction.id,
                                Notification.seen == False
                            )
                        ).first()

                        if prev_new_reply_notification:
                            update_prev_notification(prev_new_reply_notification, user, reaction)
                        else:
                            reply_notification_data = json.dumps({
                                "shout": shout_to_shout_data(shout),
                                "users": [user_to_user_data(user)],
                                "reactionIds": [reaction.id]
                            }, ensure_ascii=False)

                            reply_notification = Notification.create(**{
                                "user": parent_reaction.createdBy,
                                "type": NotificationType.NEW_REPLY,
                                "shout": shout.id,
                                "reaction": parent_reaction.id,
                                "data": reply_notification_data
                            })

                            session.add(reply_notification)

                        notify_user_ids.append(parent_reaction.createdBy)

                if reaction.createdBy != shout.createdBy and (
                    parent_reaction is None or parent_reaction.createdBy != shout.createdBy
                ):
                    prev_new_comment_notification = session.query(Notification).where(
                        and_(
                            Notification.user == shout.createdBy,
                            Notification.type == NotificationType.NEW_COMMENT,
                            Notification.shout == shout.id,
                            Notification.seen == False
                        )
                    ).first()

                    if prev_new_comment_notification:
                        update_prev_notification(prev_new_comment_notification, user, reaction)
                    else:
                        notification_data_string = json.dumps({
                            "shout": shout_to_shout_data(shout),
                            "users": [user_to_user_data(user)],
                            "reactionIds": [reaction.id]
                        }, ensure_ascii=False)

                        author_notification = Notification.create(**{
                            "user": shout.createdBy,
                            "type": NotificationType.NEW_COMMENT,
                            "shout": shout.id,
                            "data": notification_data_string
                        })

                        session.add(author_notification)

                    notify_user_ids.append(shout.createdBy)

            session.commit()

            for user_id in notify_user_ids:
                await connection_manager.notify_user(user_id)


class NotificationService:
    def __init__(self):
        self._queue = asyncio.Queue()

    async def handle_new_reaction(self, reaction_id):
        notificator = NewReactionNotificator(reaction_id)
        await self._queue.put(notificator)

    async def worker(self):
        while True:
            notificator = await self._queue.get()
            try:
                await notificator.run()
            except Exception as e:
                print(f'[NotificationService.worker] error: {str(e)}')


notification_service = NotificationService()
