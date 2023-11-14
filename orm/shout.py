from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import column_property, relationship

from base.orm import Base, local_session
from orm.reaction import Reaction
from orm.topic import Topic
from orm.user import User


class ShoutTopic(Base):
    __tablename__ = "shout_topic"

    id = None
    shout: Column = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    topic: Column = Column(ForeignKey("topic.id"), primary_key=True, index=True)


class ShoutReactionsFollower(Base):
    __tablename__ = "shout_reactions_followers"

    id = None
    follower: Column = Column(ForeignKey("user.id"), primary_key=True, index=True)
    shout: Column = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    auto = Column(Boolean, nullable=False, default=False)
    createdAt = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="Created at"
    )
    deletedAt = Column(DateTime(timezone=True), nullable=True)


class ShoutAuthor(Base):
    __tablename__ = "shout_author"

    id = None
    shout: Column = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    user: Column = Column(ForeignKey("user.id"), primary_key=True, index=True)
    caption: Column = Column(String, nullable=True, default="")


class Shout(Base):
    __tablename__ = "shout"

    # timestamps
    createdAt = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="Created at"
    )
    updatedAt = Column(DateTime(timezone=True), nullable=True, comment="Updated at")
    publishedAt = Column(DateTime(timezone=True), nullable=True)
    deletedAt = Column(DateTime(timezone=True), nullable=True)

    createdBy: Column = Column(ForeignKey("user.id"), comment="Created By")
    deletedBy: Column = Column(ForeignKey("user.id"), nullable=True)

    slug = Column(String, unique=True)
    cover = Column(String, nullable=True, comment="Cover image url")
    lead = Column(String, nullable=True)
    description = Column(String, nullable=True)
    body = Column(String, nullable=False, comment="Body")
    title = Column(String, nullable=True)
    subtitle = Column(String, nullable=True)
    layout = Column(String, nullable=True)
    media = Column(JSON, nullable=True)
    authors = relationship(lambda: User, secondary=ShoutAuthor.__tablename__)
    topics = relationship(lambda: Topic, secondary=ShoutTopic.__tablename__)

    # views from the old Discours website
    viewsOld = Column(Integer, default=0)
    # views from Ackee tracker on the new Discours website
    viewsAckee = Column(Integer, default=0)
    views = column_property(viewsOld + viewsAckee)
    reactions = relationship(lambda: Reaction)

    # TODO: these field should be used or modified
    community: Column = Column(ForeignKey("community.id"), default=1)
    lang = Column(String, nullable=False, default="ru", comment="Language")
    mainTopic: Column = Column(ForeignKey("topic.slug"), nullable=True)
    visibility = Column(String, nullable=True)  # owner authors community public
    versionOf: Column = Column(ForeignKey("shout.id"), nullable=True)
    oid = Column(String, nullable=True)

    @staticmethod
    def init_table():
        with local_session() as session:
            s = session.query(Shout).first()
            if not s:
                entry = {"slug": "genesis-block", "body": "", "title": "Ничего", "lang": "ru"}
                s = Shout.create(**entry)
                session.add(s)
                session.commit()
