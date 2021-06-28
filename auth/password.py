from passlib.hash import pbkdf2_sha256


class Password:
    @staticmethod
    def encode(password: str) -> str:
        return pbkdf2_sha256.hash(password)

    @staticmethod
    def verify(password: str, other: str) -> bool:
        return pbkdf2_sha256.verify(password, other)
