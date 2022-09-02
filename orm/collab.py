from datetime import datetime
from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime
from base.orm import Base

class CollabAuthor(Base):
	__tablename__ = 'collab_author'

	id = None
	collab = Column(ForeignKey('collab.id'), primary_key = True)
	author = Column(ForeignKey('user.slug'), primary_key = True)
	accepted = Column(Boolean, default=False)

class Collab(Base):
	__tablename__ = 'collab'

	authors = Column()
	title: str = Column(String, nullable=True, comment="Title")
	body: str = Column(String, nullable=True, comment="Body")
	pic: str = Column(String, nullable=True, comment="Picture")
	createdAt: datetime = Column(DateTime, default=datetime.now, comment="Created At")
	createdBy: str = Column(ForeignKey('user.id'), comment="Created By")

