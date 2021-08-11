from passlib.hash import bcrypt


class Password:
    @staticmethod
    def encode(password: str) -> str:
        return bcrypt.hash(password)

    @staticmethod
    def verify(password: str, other: str) -> bool:
        return bcrypt.verify(password, other)
