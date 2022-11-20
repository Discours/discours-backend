from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean

from base.orm import Base, local_session


class CommunityFollower(Base):
    __tablename__ = "community_followers"

    id = None  # type: ignore
    follower = Column(ForeignKey("user.slug"), primary_key=True)
    community = Column(ForeignKey("community.slug"), primary_key=True)
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    auto = Column(Boolean, nullable=False, default=False)


class Community(Base):
    __tablename__ = "community"

    name = Column(String, nullable=False, comment="Name")
    slug = Column(String, nullable=False, unique=True, comment="Slug")
    desc = Column(String, nullable=False, default="")
    pic = Column(String, nullable=False, default="")
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    createdBy = Column(ForeignKey("user.slug"), nullable=False, comment="Author")

    @staticmethod
    def init_table():
        with local_session() as session:
            d = (
                session.query(Community).filter(Community.slug == "discours").first()
            )
            if not d:
                d = Community.create(
                    name="Дискурс", slug="discours", createdBy="anonymous"
                )
                session.add(d)
                session.commit()
            Community.default_community = d
            print('[orm] created default community with id %s' % d.id)
