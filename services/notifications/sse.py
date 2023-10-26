from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

import asyncio
import json


class ConnectionManager:
    def __init__(self):
        self.connections_by_user_id = {}

    def add_connection(self, user_id, connection):
        if user_id not in self.connections_by_user_id:
            self.connections_by_user_id[user_id] = []
        self.connections_by_user_id[user_id].append(connection)

    def remove_connection(self, user_id, connection):
        if user_id not in self.connections_by_user_id:
            return

        self.connections_by_user_id[user_id].remove(connection)

        if len(self.connections_by_user_id[user_id]) == 0:
            del self.connections_by_user_id[user_id]

    async def notify_user(self, user_id):
        if user_id not in self.connections_by_user_id:
            return

        for connection in self.connections_by_user_id[user_id]:
            data = {"type": "newNotifications"}
            data_string = json.dumps(data, ensure_ascii=False)
            await connection.put(data_string)

    async def broadcast(self, data: str):
        for user_id in self.connections_by_user_id:
            for connection in self.connections_by_user_id[user_id]:
                await connection.put(data)


class Connection:
    def __init__(self):
        self._queue = asyncio.Queue()

    async def put(self, data: str):
        await self._queue.put(data)

    async def listen(self):
        data = await self._queue.get()
        return data


connection_manager = ConnectionManager()


async def sse_subscribe_handler(request: Request):
    user_id = int(request.path_params["user_id"])
    connection = Connection()
    connection_manager.add_connection(user_id, connection)

    async def event_publisher():
        try:
            while True:
                data = await connection.listen()
                yield data
        except asyncio.CancelledError as e:
            connection_manager.remove_connection(user_id, connection)
            raise e

    return EventSourceResponse(event_publisher())
