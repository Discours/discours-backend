from orm.collection import Collection
from base.orm import local_session
from orm.user import User
from base.resolvers import mutation, query
from auth.authenticate import login_required
from datetime import datetime
from typing import Collection
from sqlalchemy import and_

@mutation.field("createCollection")
@login_required
async def create_collection(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id
	collection = Collection.create(
		slug = input.get('slug', ''),
		title = input.get('title', ''),
		desc = input.get('desc', ''),
		pic = input.get('pic', '')
		)

	return {"collection": collection}

@mutation.field("updateCollection")
@login_required
async def update_collection(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id
	collection_slug = input.get('slug', '')
	with local_session() as session:
		owner = session.query(User).filter(User.id == user_id) # note list here
		collection = session.query(Collection).filter(Collection.slug == collection_slug).first()
		editors = [e.slug for e in collection.editors]
		if not collection:
			return {"error": "invalid collection id"}
		if collection.createdBy not in (owner + editors):
			return {"error": "access denied"}
		collection.title = input.get('title', '')
		collection.desc = input.get('desc', '')
		collection.pic = input.get('pic', '')
		collection.updatedAt = datetime.now()
		session.commit()

@mutation.field("deleteCollection")
@login_required
async def delete_collection(_, info, slug):
	auth = info.context["request"].auth
	user_id = auth.user_id
	with local_session() as session:
		collection = session.query(Collection).filter(Collection.slug == slug).first()
		if not collection:
			return {"error": "invalid collection slug"}
		if collection.owner != user_id:
			return {"error": "access denied"}
		collection.deletedAt = datetime.now()
		session.commit()

	return {}

@query.field("getCollection")
async def get_collection(_, info, userslug, colslug):
	with local_session() as session:
		user = session.query(User).filter(User.slug == userslug).first()
		if user:
			collection = session.\
				query(Collection).\
				where(and_(Collection.createdBy == user.id, Collection.slug == colslug)).\
				first()
		if not collection:
			return {"error": "collection not found"}
	return collection

@query.field("getMyColelctions")
@login_required
async def get_collections(_, info):
	auth = info.context["request"].auth
	user_id = auth.user_id
	with local_session() as session:
		collections = session.query(Collection).when(Collection.createdBy == user_id).all()
	return collections