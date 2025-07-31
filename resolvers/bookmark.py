from operator import and_

from graphql import GraphQLError
from sqlalchemy import delete, insert

from auth.orm import AuthorBookmark
from orm.shout import Shout
from resolvers.reader import apply_options, get_shouts_with_links, query_with_stat
from services.auth import login_required
from services.common_result import CommonResult
from services.db import local_session
from services.schema import mutation, query


@query.field("load_shouts_bookmarked")
@login_required
def load_shouts_bookmarked(_: None, info, options) -> list[Shout]:
    """
    Load bookmarked shouts for the authenticated user.

    Args:
        limit (int): Maximum number of shouts to return.
        offset (int): Number of shouts to skip.

    Returns:
        list: List of bookmarked shouts.
    """
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    if not author_id:
        msg = "User not authenticated"
        raise GraphQLError(msg)

    q = query_with_stat(info)
    q = q.join(AuthorBookmark)
    q = q.where(
        and_(
            Shout.id == AuthorBookmark.shout,
            AuthorBookmark.author == author_id,
        )
    )
    q, limit, offset = apply_options(q, options, author_id)
    shouts = get_shouts_with_links(info, q, limit, offset)
    return shouts


@mutation.field("toggle_bookmark_shout")
def toggle_bookmark_shout(_: None, info, slug: str) -> CommonResult:
    """
    Toggle bookmark status for a specific shout.

    Args:
        slug (str): Unique identifier of the shout.

    Returns:
        CommonResult: Result of the operation with bookmark status.
    """
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    if not author_id:
        msg = "User not authenticated"
        raise GraphQLError(msg)

    with local_session() as db:
        shout = db.query(Shout).where(Shout.slug == slug).first()
        if not shout:
            msg = "Shout not found"
            raise GraphQLError(msg)

        existing_bookmark = (
            db.query(AuthorBookmark).where(AuthorBookmark.author == author_id, AuthorBookmark.shout == shout.id).first()
        )

        if existing_bookmark:
            db.execute(
                delete(AuthorBookmark).where(AuthorBookmark.author == author_id, AuthorBookmark.shout == shout.id)
            )
            result = CommonResult()
        else:
            db.execute(insert(AuthorBookmark).values(author=author_id, shout=shout.id))
            result = CommonResult()

        db.commit()
        return result
