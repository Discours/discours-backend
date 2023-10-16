import json
from services.redis import redis


async def notify_reaction(reaction):
    channel_name = "new_reaction"
    data = {
        "payload": reaction, 
        "kind": f"new_reaction{reaction.kind}"
    }
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")


async def notify_shout(shout):
    channel_name = "new_shout"
    data = {
        "payload": shout, 
        "kind": "new_shout"
    }
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")


async def notify_follower(follower: dict, author_id: int):
    fields = follower.keys()
    for k in fields:
        if k not in ["id", "name", "slug", "userpic"]:
            del follower[k]
    channel_name = f"followers:{author_id}"
    data = {
        "payload": follower,
        "kind": "new_follower",
    }
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")
