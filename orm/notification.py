from sqlalchemy import Column, String, JSON

from base.orm import Base


class Notification(Base):
    __tablename__ = "notification"

    kind = Column(String, unique=True, primary_key=True)
    template = Column(String, nullable=False)
    variables = Column(JSON, nullable=True)  # [ <var1>, .. ]

    # looks like frontend code
