import asyncio


class MessageResult:
    def __init__(self, status, message):
        self.seen = status
        self.message = message


class ChatFollowing:
    queue = asyncio.Queue()

    def __init__(self, chat_id):
        self.chat_id = chat_id
