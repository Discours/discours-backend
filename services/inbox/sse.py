from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from resolvers.inbox.messages import message_generator
from base.exceptions import Unauthorized


async def sse_messages(request: Request):
    print(f'[SSE] {request.scope}')  # FIXME: DOES NOT HAPPEN TO BE CALLED
    # https://github.com/enisdenjo/graphql-sse/blob/master/PROTOCOL.md
    if request['user']:
        event_generator = await message_generator(None, request.scope)
        return EventSourceResponse(event_generator)
    else:
        raise Unauthorized("Please login")
