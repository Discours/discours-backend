from sse_starlette.sse import EventSourceResponse
from resolvers.inbox.messages import message_generator


async def sse_messages(request):
    print(f'[SSE] {request}')
    # https://github.com/enisdenjo/graphql-sse/blob/master/PROTOCOL.md

    return EventSourceResponse(message_generator)
