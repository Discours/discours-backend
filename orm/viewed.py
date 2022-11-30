from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer
from base.orm import Base, local_session


class ViewedEntry(Base):
    __tablename__ = "viewed"

    viewerId = Column(ForeignKey("user.id"), index=True, default=1)
    shout = Column(ForeignKey("shout.id"), index=True, default=1)
    amount = Column(Integer, default=1)
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )

    @staticmethod
    def init_table():
        with local_session() as session:
            entry = {
                "amount": 0
            }
            viewed = ViewedEntry.create(**entry)
            session.add(viewed)
            session.commit()
