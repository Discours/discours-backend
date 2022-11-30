from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, JSON
from sqlalchemy.orm import relationship

from base.orm import Base, local_session
from orm.reaction import Reaction
from orm.topic import Topic
from orm.user import User


class ShoutTopic(Base):
    __tablename__ = "shout_topic"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    topic = Column(ForeignKey("topic.id"), primary_key=True, index=True)


class ShoutReactionsFollower(Base):
    __tablename__ = "shout_reactions_followers"

    id = None  # type: ignore
    follower = Column(ForeignKey("user.id"), primary_key=True, index=True)
    shout = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    auto = Column(Boolean, nullable=False, default=False)
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    deletedAt = Column(DateTime, nullable=True)


class ShoutAuthor(Base):
    __tablename__ = "shout_author"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    user = Column(ForeignKey("user.id"), primary_key=True, index=True)
    caption = Column(String, nullable=True, default="")


class Shout(Base):
    __tablename__ = "shout"

    slug = Column(String, unique=True)
    community = Column(ForeignKey("community.id"), default=1)
    lang = Column(String, nullable=False, default='ru', comment="Language")
    body = Column(String, nullable=False, comment="Body")
    title = Column(String, nullable=True)
    subtitle = Column(String, nullable=True)
    layout = Column(String, nullable=True)
    mainTopic = Column(ForeignKey("topic.slug"), nullable=True)
    cover = Column(String, nullable=True)
    authors = relationship(lambda: User, secondary=ShoutAuthor.__tablename__)
    topics = relationship(lambda: Topic, secondary=ShoutTopic.__tablename__)
    reactions = relationship(lambda: Reaction)
    visibility = Column(String, nullable=True)  # owner authors community public
    versionOf = Column(ForeignKey("shout.id"), nullable=True)
    oid = Column(String, nullable=True)
    media = Column(JSON, nullable=True)

    createdAt = Column(DateTime, nullable=False, default=datetime.now, comment="Created at")
    updatedAt = Column(DateTime, nullable=True, comment="Updated at")
    publishedAt = Column(DateTime, nullable=True)
    deletedAt = Column(DateTime, nullable=True)

    @staticmethod
    def init_table():
        with local_session() as session:
            s = session.query(Shout).first()
            if not s:
                entry = {
                    "slug": "genesis-block",
                    "body": "",
                    "title": "Ничего",
                    "lang": "ru"
                }
                s = Shout.create(**entry)
                session.add(s)
                session.commit()
