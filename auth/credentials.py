from typing import List, Optional, Text

from pydantic import BaseModel

from base.exceptions import Unauthorized


class Permission(BaseModel):
    name: Text


class AuthCredentials(BaseModel):
    user_id: Optional[int] = None
    scopes: Optional[dict] = {}
    logged_in: bool = False
    error_message: str = ""

    @property
    def is_admin(self):
        # TODO: check admin logix
        return True

    async def permissions(self) -> List[Permission]:
        if self.user_id is None:
            raise Unauthorized("Please login first")
        # TODO: implement permissions logix
        return NotImplemented()


class AuthUser(BaseModel):
    user_id: Optional[int]

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def display_id(self) -> int:
        return self.user_id
