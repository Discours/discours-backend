import asyncio

from sse import connection_manager

class NewCommentNotificator:

# NewCommentNotificator
# Notificator -> Run

class NotificationService:
    def __init__(self):
        self._queue = asyncio.Queue()

    async def put(self, data: str):
        await self._queue.put(data)

    async def listen(self):
        data = await self._queue.get()
        return data
