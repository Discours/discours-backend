from resolvers.auth import (
    login,
    sign_out,
    is_email_used,
    register,
    confirm_email,
    auth_send_link,
)
from resolvers.collab import remove_author, invite_author
from resolvers.community import (
    create_community,
    delete_community,
    get_community,
    get_communities,
)

# from resolvers.collab import invite_author, remove_author
from resolvers.editor import create_shout, delete_shout, update_shout
from resolvers.profile import (
    get_users_by_slugs,
    get_current_user,
    get_user_reacted_shouts,
    get_user_roles,
    get_top_authors,
)

# from resolvers.feed import shouts_for_feed, my_candidates
from resolvers.reactions import (
    create_reaction,
    delete_reaction,
    update_reaction,
    reactions_unfollow,
    reactions_follow,
    get_shout_reactions,
)
from resolvers.topics import (
    topic_follow,
    topic_unfollow,
    topics_by_author,
    topics_by_community,
    topics_all,
)
from resolvers.zine import (
    get_shout_by_slug,
    follow,
    unfollow,
    view_shout,
    top_month,
    top_overall,
    recent_published,
    recent_all,
    top_viewed,
    shouts_by_authors,
    shouts_by_topics,
    shouts_by_communities,
)

__all__ = [
    "follow",
    "unfollow",
    # auth
    "login",
    "register",
    "is_email_used",
    "confirm_email",
    "auth_send_link",
    "sign_out",
    # profile
    "get_current_user",
    "get_users_by_slugs",
    "get_user_roles",
    "get_top_authors",
    # zine
    "recent_published",
    "recent_all",
    "shouts_by_topics",
    "shouts_by_authors",
    "shouts_by_communities",
    "get_user_reacted_shouts",
    "top_month",
    "top_overall",
    "top_viewed",
    "view_shout",
    "get_shout_by_slug",
    # editor
    "create_shout",
    "update_shout",
    "delete_shout",
    # collab
    "invite_author",
    "remove_author",
    # topics
    "topics_all",
    "topics_by_community",
    "topics_by_author",
    "topic_follow",
    "topic_unfollow",
    # communities
    "get_community",
    "get_communities",
    "create_community",
    "delete_community",
    # reactions
    "get_shout_reactions",
    "reactions_follow",
    "reactions_unfollow",
    "create_reaction",
    "update_reaction",
    "delete_reaction",
]
