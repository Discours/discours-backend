from typing import List, Optional, Text

from pydantic import BaseModel


class Message(BaseModel):
    id: int
    body: Text
    author: int
    chatId: Text
    createdAt: int
    updatedAt: Optional[int]
    replyTo: Optional[int]


class Member(BaseModel):
    id: int
    name: Text
    pic: Optional[Text]
    # TODO: extend chat member model


class Chat(BaseModel):
    id: int
    createdAt: int
    createdBy: int
    users: List[int]
    updatedAt: Optional[int]
    title: Optional[Text]
    description: Optional[Text]
