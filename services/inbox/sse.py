from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from graphql.type import GraphQLResolveInfo
from resolvers.inbox.messages import message_generator
# from base.exceptions import Unauthorized

# https://github.com/enisdenjo/graphql-sse/blob/master/PROTOCOL.md


async def sse_messages(request: Request):
    print(f'[SSE] request\n{request}\n')
    info = GraphQLResolveInfo()
    info.context['request'] = request.scope
    user_id = request.scope['user'].user_id
    if user_id:
        event_generator = await message_generator(None, info)
        return EventSourceResponse(event_generator)
    else:
        # raise Unauthorized("Please login")
        return {
            "error": "Please login first"
        }
