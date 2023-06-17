from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.responses import StreamingResponse, JSONResponse
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    def add_connection(self, connection):
        self.active_connections.append(connection)

    def remove_connection(self, connection):
        self.active_connections.remove(connection)

    async def broadcast(self, data: str):
        for connection in self.active_connections:
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


class NotificationEndpoint(HTTPEndpoint):
    async def post(self, request):
        data = await request.json()
        await connection_manager.broadcast(data)
        print('[sse] send event')
        return JSONResponse({"detail": "Notification sent"})


class SubscribeEndpoint(HTTPEndpoint):
    async def get(self, request):
        connection = Connection()
        connection_manager.add_connection(connection)
        return StreamingResponse(connection.listen(), media_type="text/event-stream")


async def broadcast_message():
    while True:
        await asyncio.sleep(1)
        await connection_manager.broadcast("Hello, World!")

