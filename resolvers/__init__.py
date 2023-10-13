from resolvers.auth import (
    login,
    sign_out,
    is_email_used,
    register_by_email,
    confirm_email,
    auth_send_link,
    get_current_user,
)

from resolvers.editor import create_shout, delete_shout, update_shout
from resolvers.profile import (
    load_authors_by,
    rate_user,
    update_profile,
    get_authors_all,
    get_followed_authors2,
    get_followed_authors,
    get_author,
    get_author_by_id
)

from resolvers.topics import (
    topics_all,
    topics_by_community,
    topics_by_author,
    topic_follow,
    topic_unfollow,
    get_topic,
)

from resolvers.reactions import (
    create_reaction,
    delete_reaction,
    update_reaction,
    reactions_unfollow,
    reactions_follow,
    load_reactions_by,
)

from resolvers.following import follow, unfollow

from resolvers.load import load_shout, load_shouts_by

__all__ = [
    # auth
    "login",
    "register_by_email",
    "is_email_used",
    "confirm_email",
    "auth_send_link",
    "sign_out",
    "get_current_user",
    # profile
    "load_authors_by",
    "rate_user",
    "update_profile",
    "get_authors_all",
    "get_followed_authors2",
    "get_followed_authors",
    "get_author",
    "get_author_by_id",
    # load
    "load_shout",
    "load_shouts_by",
    # zine.following
    "follow",
    "unfollow",
    # create
    "create_shout",
    "update_shout",
    "delete_shout",
    # topics
    "topics_all",
    "topics_by_community",
    "topics_by_author",
    "topic_follow",
    "topic_unfollow",
    "get_topic",
    # zine.reactions
    "reactions_follow",
    "reactions_unfollow",
    "create_reaction",
    "update_reaction",
    "delete_reaction",
    "load_reactions_by",
]
