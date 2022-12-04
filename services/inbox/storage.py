import asyncio


class MessagesStorage:
    lock = asyncio.Lock()
    chats = []

    @staticmethod
    async def register_chat(chat):
        async with MessagesStorage.lock:
            MessagesStorage.chats.append(chat)

    @staticmethod
    async def remove_chat(chat):
        async with MessagesStorage.lock:
            MessagesStorage.chats.remove(chat)

    @staticmethod
    async def put(message_result):
        async with MessagesStorage.lock:
            for chat in MessagesStorage.chats:
                if message_result.message["chatId"] == chat.chat_id:
                    chat.queue.put_nowait(message_result)
