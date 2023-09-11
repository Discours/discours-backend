from starlette.endpoints import HTTPEndpoint
from starlette.responses import StreamingResponse
import asyncio


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

    async def notify_user(self, user_id, data: str):
        if user_id not in self.connections_by_user_id[user_id]:
            return

        for connection in self.connections_by_user_id[user_id]:
            await connection.put(data)

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
        while True:
            data = await self._queue.get()
            yield f"data: {data}\n\n"


connection_manager = ConnectionManager()


class SubscribeEndpoint(HTTPEndpoint):
    async def get(self, request):
        user_id = request.path_params["user_id"]
        connection = Connection()
        connection_manager.add_connection(user_id, connection)
        return StreamingResponse(connection.listen(), media_type="text/event-stream")


async def broadcast_message():
    print("[broadcast_message]: start")
    while True:
        await asyncio.sleep(1)
        print('[broadcast_message]: ping')
        await connection_manager.broadcast('{ "type": "ping" }')
