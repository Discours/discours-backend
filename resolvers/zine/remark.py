
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy.sql.expression import desc, asc, select, func
from base.orm import local_session
from base.resolvers import query, mutation
from base.exceptions import ObjectNotExist
from orm.remark import Remark


@mutation.field("createRemark")
@login_required
async def create_remark(_, info, slug, body):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        tt = Remark.create(slug=slug, body=body)
        session.commit()
        return

@mutation.field("updateRemark")
@login_required
async def update_remark(_, info, slug, body = ''):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        rmrk = session.query(Remark).where(Remark.slug == slug).one()
        if body:
            tt.body = body
            session.add(rmrk)
        session.commit()
        return

@mutation.field("deleteRemark")
@login_required
async def delete_remark(_, info, slug):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        rmrk = session.query(Remark).where(Remark.slug == slug).one()
        rmrk.remove()
        session.commit()
        return

@query.field("loadRemark")
@login_required
async def load_remark(_, info, slug):
    pass
