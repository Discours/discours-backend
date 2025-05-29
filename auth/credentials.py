from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

# from base.exceptions import Unauthorized
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


class Permission(BaseModel):
    """Модель разрешения для RBAC"""

    resource: str
    operation: str

    def __str__(self) -> str:
        return f"{self.resource}:{self.operation}"


class AuthCredentials(BaseModel):
    """
    Модель учетных данных авторизации.
    Используется как часть механизма аутентификации Starlette.
    """

    author_id: Optional[int] = Field(None, description="ID автора")
    scopes: Dict[str, Set[str]] = Field(default_factory=dict, description="Разрешения пользователя")
    logged_in: bool = Field(False, description="Флаг, указывающий, авторизован ли пользователь")
    error_message: str = Field("", description="Сообщение об ошибке аутентификации")
    email: Optional[str] = Field(None, description="Email пользователя")
    token: Optional[str] = Field(None, description="JWT токен авторизации")

    def get_permissions(self) -> List[str]:
        """
        Возвращает список строковых представлений разрешений.
        Например: ["posts:read", "posts:write", "comments:create"].

        Returns:
            List[str]: Список разрешений
        """
        result = []
        for resource, operations in self.scopes.items():
            for operation in operations:
                result.append(f"{resource}:{operation}")
        return result

    def has_permission(self, resource: str, operation: str) -> bool:
        """
        Проверяет наличие определенного разрешения.

        Args:
            resource: Ресурс (например, "posts")
            operation: Операция (например, "read")

        Returns:
            bool: True, если пользователь имеет указанное разрешение
        """
        if not self.logged_in:
            return False

        return resource in self.scopes and operation in self.scopes[resource]

    @property
    def is_admin(self) -> bool:
        """
        Проверяет, является ли пользователь администратором.

        Returns:
            bool: True, если email пользователя находится в списке ADMIN_EMAILS
        """
        return self.email in ADMIN_EMAILS if self.email else False

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует учетные данные в словарь

        Returns:
            Dict[str, Any]: Словарь с данными учетных данных
        """
        return {
            "author_id": self.author_id,
            "logged_in": self.logged_in,
            "is_admin": self.is_admin,
            "permissions": self.get_permissions(),
        }

    async def permissions(self) -> List[Permission]:
        if self.author_id is None:
            # raise Unauthorized("Please login first")
            return {"error": "Please login first"}
        else:
            # TODO: implement permissions logix
            print(self.author_id)
        return NotImplemented
