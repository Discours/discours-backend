import enum
import time

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, Text, distinct, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from auth.orm import Author
from services.db import BaseModel


class CommunityRole(enum.Enum):
    READER = "reader"  # can read and comment
    AUTHOR = "author"  # + can vote and invite collaborators
    ARTIST = "artist"  # + can be credited as featured artist
    EXPERT = "expert"  # + can add proof or disproof to shouts, can manage topics
    EDITOR = "editor"  # + can manage topics, comments and community settings
    ADMIN = "admin"

    @classmethod
    def as_string_array(cls, roles):
        return [role.value for role in roles]

    @classmethod
    def from_string(cls, value: str) -> "CommunityRole":
        return cls(value)


class CommunityFollower(BaseModel):
    __tablename__ = "community_follower"

    community = Column(ForeignKey("community.id"), primary_key=True)
    follower = Column(ForeignKey("author.id"), primary_key=True)
    roles = Column(String, nullable=True)

    def __init__(self, community: int, follower: int, roles: list[str] | None = None) -> None:
        self.community = community  # type: ignore[assignment]
        self.follower = follower  # type: ignore[assignment]
        if roles:
            self.roles = ",".join(roles)  # type: ignore[assignment]

    def get_roles(self) -> list[CommunityRole]:
        roles_str = getattr(self, "roles", "")
        return [CommunityRole(role) for role in roles_str.split(",")] if roles_str else []


class Community(BaseModel):
    __tablename__ = "community"

    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    desc = Column(String, nullable=False, default="")
    pic = Column(String, nullable=False, default="")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    created_by = Column(ForeignKey("author.id"), nullable=False)
    settings = Column(JSON, nullable=True)
    updated_at = Column(Integer, nullable=True)
    deleted_at = Column(Integer, nullable=True)
    private = Column(Boolean, default=False)

    followers = relationship("Author", secondary="community_follower")

    @hybrid_property
    def stat(self):
        return CommunityStats(self)

    @property
    def role_list(self):
        return self.roles.split(",") if self.roles else []

    @role_list.setter
    def role_list(self, value) -> None:
        self.roles = ",".join(value) if value else None  # type: ignore[assignment]

    def is_followed_by(self, author_id: int) -> bool:
        # Check if the author follows this community
        from services.db import local_session

        with local_session() as session:
            follower = (
                session.query(CommunityFollower)
                .filter(CommunityFollower.community == self.id, CommunityFollower.follower == author_id)
                .first()
            )
            return follower is not None

    def get_role(self, author_id: int) -> CommunityRole | None:
        # Get the role of the author in this community
        from services.db import local_session

        with local_session() as session:
            follower = (
                session.query(CommunityFollower)
                .filter(CommunityFollower.community == self.id, CommunityFollower.follower == author_id)
                .first()
            )
            if follower and follower.roles:
                roles = follower.roles.split(",")
                return CommunityRole.from_string(roles[0]) if roles else None
            return None


class CommunityStats:
    def __init__(self, community) -> None:
        self.community = community

    @property
    def shouts(self):
        from orm.shout import Shout

        return self.community.session.query(func.count(Shout.id)).filter(Shout.community == self.community.id).scalar()

    @property
    def followers(self):
        return (
            self.community.session.query(func.count(CommunityFollower.follower))
            .filter(CommunityFollower.community == self.community.id)
            .scalar()
        )

    @property
    def authors(self):
        from orm.shout import Shout

        # author has a shout with community id and its featured_at is not null
        return (
            self.community.session.query(func.count(distinct(Author.id)))
            .join(Shout)
            .filter(
                Shout.community == self.community.id,
                Shout.featured_at.is_not(None),
                Author.id.in_(Shout.authors),
            )
            .scalar()
        )


class CommunityAuthor(BaseModel):
    __tablename__ = "community_author"

    id = Column(Integer, primary_key=True)
    community_id = Column(Integer, ForeignKey("community.id"))
    author_id = Column(Integer, ForeignKey("author.id"))
    roles = Column(Text, nullable=True, comment="Roles (comma-separated)")

    @property
    def role_list(self):
        return self.roles.split(",") if self.roles else []

    @role_list.setter
    def role_list(self, value) -> None:
        self.roles = ",".join(value) if value else None  # type: ignore[assignment]
