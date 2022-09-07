from orm.collection import Collection, ShoutCollection
from base.orm import local_session
from orm.user import User
from base.resolvers import mutation, query
from auth.authenticate import login_required
from datetime import datetime
from sqlalchemy import and_


@mutation.field("createCollection")
@login_required
async def create_collection(_, _info, inp):
    # auth = info.context["request"].auth
    # user_id = auth.user_id
    collection = Collection.create(
        slug=inp.get("slug", ""),
        title=inp.get("title", ""),
        desc=inp.get("desc", ""),
        pic=inp.get("pic", ""),
    )

    return {"collection": collection}


@mutation.field("updateCollection")
@login_required
async def update_collection(_, info, inp):
    auth = info.context["request"].auth
    user_id = auth.user_id
    collection_slug = input.get("slug", "")
    with local_session() as session:
        owner = session.query(User).filter(User.id == user_id)  # note list here
        collection = (
            session.query(Collection).filter(Collection.slug == collection_slug).first()
        )
        editors = [e.slug for e in collection.editors]
        if not collection:
            return {"error": "invalid collection id"}
        if collection.createdBy not in (owner + editors):
            return {"error": "access denied"}
        collection.title = inp.get("title", "")
        collection.desc = inp.get("desc", "")
        collection.pic = inp.get("pic", "")
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


@query.field("getUserCollections")
async def get_user_collections(_, _info, userslug):
    collections = []
    with local_session() as session:
        user = session.query(User).filter(User.slug == userslug).first()
        if user:
            # TODO: check rights here
            collections = (
                session.query(Collection)
                .where(
                    and_(Collection.createdBy == userslug, bool(Collection.publishedAt))
                )
                .all()
            )
        for c in collections:
            shouts = (
                session.query(ShoutCollection)
                .filter(ShoutCollection.collection == c.id)
                .all()
            )
            c.amount = len(shouts)
    return collections


@query.field("getMyColelctions")
@login_required
async def get_my_collections(_, info):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        collections = (
            session.query(Collection).when(Collection.createdBy == user_id).all()
        )
    return collections
