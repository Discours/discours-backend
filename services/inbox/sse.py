from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from resolvers.inbox.messages import messages_generator_by_user
from base.exceptions import Unauthorized


async def sse_messages(request: Request):
    print(f'[SSE] {request.scope}')
    # https://github.com/enisdenjo/graphql-sse/blob/master/PROTOCOL.md
    if request['user']:
        return EventSourceResponse(messages_generator_by_user(request['user'].user_id))
    else:
        raise Unauthorized("Please login")
