import json
from orm.reaction import Reaction
from orm.shout import Shout
from orm.user import Author
from services.redis import redis


async def notify_reaction(reaction: Reaction):
    channel_name = "new_reaction"
    data = {
        "payload": reaction, 
        "kind": f"new_reaction{reaction.kind}"
    }
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")


async def notify_shout(shout: Shout):
    channel_name = "new_shout"
    data = {
        "payload": shout, 
        "kind": "new_shout"
    }
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")


async def notify_follower(follower: Author, author_id: int):
    channel_name = f"followers:{author_id}"
    data = {
        "payload": follower,
        "kind": "new_follower",
    }
    try:
        await redis.publish(channel_name, json.dumps(data))
    except Exception as e:
        print(f"Failed to publish to channel {channel_name}: {e}")
