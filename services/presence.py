import json
from orm.reaction import Reaction
from orm.shout import Shout
from services.redis import redis


async def notify_reaction(reaction: Reaction):
    channel_name = f"new_reaction"
    data = {**reaction, "kind": f"new_reaction{reaction.kind}"}
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")


async def notify_shout(shout: Shout):
    channel_name = f"new_shout"
    data = {**shout, "kind": "new_shout"}
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")


async def notify_follower(follower_id: int, author_id: int):
    channel_name = f"new_follower"
    data = {
        "follower_id": follower_id,
        "author_id": author_id,
        "kind": "new_follower",
    }
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")
