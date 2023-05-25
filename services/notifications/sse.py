from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.endpoints import HTTPEndpoint

class EventManager:
    def __init__(self):
        self._connections = []

    def add_connection(self, connection):
        self._connections.append(connection)

    def remove_connection(self, connection):
        self._connections.remove(connection)

    async def send_event(self, data):
        dead_connections = []
        for connection in self._connections:
            awaitable = connection.send_text(f"data: {data}\n\n")
            try:
                await awaitable
            except RuntimeError:
                dead_connections.append(connection)

        for connection in dead_connections:
            self._connections.remove(connection)


event_manager = EventManager()

class NotificationEndpoint(HTTPEndpoint):
    async def post(self, request):
        data = await request.json()
        await event_manager.send_event(data)
        return Response("Notification sent")

class SubscribeEndpoint(HTTPEndpoint):
    async def get(self, request):
        async def event_stream():
            with event_manager as connection:
                while True:
                    data = await connection.receive_text()
                    yield f"data: {data}\n\n"

        return Response(event_stream(), media_type="text/event-stream")

app = Starlette(
    routes=[
        Route("/notify", NotificationEndpoint),
        Route("/subscribe", SubscribeEndpoint),
    ]
)

