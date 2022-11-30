from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime
from base.orm import Base, local_session


class CommunityFollower(Base):
    __tablename__ = "community_followers"

    id = None  # type: ignore
    follower = Column(ForeignKey("user.id"), primary_key=True)
    communityId = Column(ForeignKey("community.id"), primary_key=True)
    joinedAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    # role = Column(ForeignKey(Role.id), nullable=False, comment="Role for member")


class Community(Base):
    __tablename__ = "community"

    name = Column(String, nullable=False, comment="Name")
    slug = Column(String, nullable=False, unique=True, comment="Slug")
    desc = Column(String, nullable=False, default="")
    pic = Column(String, nullable=False, default="")
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )

    @staticmethod
    def init_table():
        with local_session() as session:
            d = (
                session.query(Community).filter(Community.slug == "discours").first()
            )
            if not d:
                d = Community.create(name="Дискурс", slug="discours")
                session.add(d)
                session.commit()
            Community.default_community = d
            print('[orm] default community id: %s' % d.id)
