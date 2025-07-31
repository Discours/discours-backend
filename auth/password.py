"""
Модуль для работы с паролями
Отдельный модуль для избежания циклических импортов
"""

from binascii import hexlify
from hashlib import sha256

import bcrypt


class Password:
    @staticmethod
    def _to_bytes(data: str) -> bytes:
        return bytes(data.encode())

    @classmethod
    def _get_sha256(cls, password: str) -> bytes:
        bytes_password = cls._to_bytes(password)
        return hexlify(sha256(bytes_password).digest())

    @staticmethod
    def encode(password: str) -> str:
        """
        Кодирует пароль пользователя

        Args:
            password (str): Пароль пользователя

        Returns:
            str: Закодированный пароль
        """
        password_sha256 = Password._get_sha256(password)
        salt = bcrypt.gensalt(rounds=10)
        return bcrypt.hashpw(password_sha256, salt).decode("utf-8")

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        r"""
        Verify that password hash is equal to specified hash. Hash format:

        $2a$10$Ro0CUfOqk6cXEKf3dyaM7OhSCvnwM9s4wIX9JeLapehKK5YdLxKcm
        \__/\/ \____________________/\_____________________________/
        |   |        Salt                     Hash
        |  Cost
        Version

        More info: https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt.html

        :param password: clear text password
        :param hashed: hash of the password
        :return: True if clear text password matches specified hash
        """
        hashed_bytes = Password._to_bytes(hashed)
        password_sha256 = Password._get_sha256(password)

        return bcrypt.checkpw(password_sha256, hashed_bytes)
