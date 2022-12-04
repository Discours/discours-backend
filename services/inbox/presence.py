from base.exceptions import Unauthorized
from auth.tokenstorage import SessionToken
from base.redis import redis


async def set_online_status(user_id, status):
    if user_id:
        if status:
            await redis.execute("SADD", "users-online", user_id)
        else:
            await redis.execute("SREM", "users-online", user_id)


async def on_connect(websocket, params):
    if not isinstance(params, dict):
        websocket.scope["connection_params"] = {}
        return
    token = params.get('token')
    if not token:
        raise Unauthorized("Please login")
    else:
        payload = await SessionToken.verify(token)
        if payload and payload.user_id:
            websocket.scope["user_id"] = payload.user_id
            await set_online_status(payload.user_id, True)


async def on_disconnect(websocket):
    user_id = websocket.scope.get("user_id")
    await set_online_status(user_id, False)


# FIXME: not used yet
def context_value(request):
    context = {}
    print(f"[inbox.presense] request debug: {request}")
    if request.scope["type"] == "websocket":
        # request is an instance of WebSocket
        context.update(request.scope["connection_params"])
    else:
        context["token"] = request.META.get("authorization")

    return context
