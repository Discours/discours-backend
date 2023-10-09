import asyncio
import json

from base.orm import local_session
from orm import Reaction, Shout, Notification, User
from orm.notification import NotificationType
from orm.reaction import ReactionKind
from services.notifications.sse import connection_manager


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
                if reaction.createdBy != shout.createdBy:
                    author_notification_data = json.dumps({
                        "shout": {
                            "title": shout.title
                        },
                        "users": [
                            {"id": user.id, "name": user.name}
                        ]
                    })
                    author_notification = Notification.create(**{
                        "user": shout.createdBy,
                        "type": NotificationType.NEW_COMMENT.name,
                        "shout": shout.id,
                        "data": author_notification_data
                    })

                    session.add(author_notification)
                    notify_user_ids.append(author_notification.user)

                if reaction.replyTo:
                    parent_reaction = session.query(Reaction).where(Reaction.id == reaction.replyTo).one()
                    if parent_reaction.createdBy != reaction.createdBy:
                        reply_notification_data = json.dumps({
                            "shout": {
                                "title": shout.title
                            },
                            "users": [
                                {"id": user.id, "name": user.name}
                            ]
                        })
                        reply_notification = Notification.create(**{
                            "user": parent_reaction.createdBy,
                            "type": NotificationType.NEW_REPLY.name,
                            "shout": shout.id,
                            "reaction": parent_reaction.id,
                            "data": reply_notification_data
                        })

                        session.add(author_notification)
                        notify_user_ids.append(reply_notification.user)

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
            except Exception as ex:
                print('[NotificationService.worker] error')
                print(ex)
                print()


notification_service = NotificationService()
