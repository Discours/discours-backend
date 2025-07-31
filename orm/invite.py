import enum

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orm.base import BaseModel as Base


class InviteStatus(enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

    @classmethod
    def from_string(cls, value: str) -> "InviteStatus":
        return cls(value)


class Invite(Base):
    __tablename__ = "invite"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    shout_id: Mapped[int] = mapped_column(ForeignKey("shout.id"))
    status: Mapped[str] = mapped_column(String, default=InviteStatus.PENDING.value)

    inviter = relationship("Author", foreign_keys=[inviter_id])
    author = relationship("Author", foreign_keys=[author_id])
    shout = relationship("Shout")

    __table_args__ = (
        UniqueConstraint(inviter_id, author_id, shout_id),
        Index("idx_invite_inviter_id", "inviter_id"),
        Index("idx_invite_author_id", "author_id"),
        Index("idx_invite_shout_id", "shout_id"),
        {"extend_existing": True},
    )

    def set_status(self, status: InviteStatus) -> None:
        self.status = status.value

    def get_status(self) -> InviteStatus:
        return InviteStatus.from_string(str(self.status))
