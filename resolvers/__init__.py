from cache.triggers import events_register
from resolvers.admin import (
    admin_get_roles,
    admin_get_users,
)
from resolvers.auth import (
    confirm_email,
    get_current_user,
    login,
    register_by_email,
    send_link,
)
from resolvers.author import (  # search_authors,
    get_author,
    get_author_followers,
    get_author_follows,
    get_author_follows_authors,
    get_author_follows_topics,
    get_authors_all,
    load_authors_by,
    load_authors_search,
    update_author,
)
from resolvers.collection import get_collection, get_collections_all, get_collections_by_author
from resolvers.community import get_communities_all, get_community
from resolvers.draft import (
    create_draft,
    delete_draft,
    load_drafts,
    publish_draft,
    unpublish_draft,
    update_draft,
)
from resolvers.editor import (
    # delete_shout,
    unpublish_shout,
    # update_shout,
)
from resolvers.feed import (
    load_shouts_authored_by,
    load_shouts_coauthored,
    load_shouts_discussed,
    load_shouts_feed,
    load_shouts_followed_by,
    load_shouts_with_topic,
)
from resolvers.follower import follow, get_shout_followers, unfollow
from resolvers.notifier import (
    load_notifications,
    notification_mark_seen,
    notifications_seen_after,
    notifications_seen_thread,
)
from resolvers.rating import get_my_rates_comments, get_my_rates_shouts, rate_author
from resolvers.reaction import (
    create_reaction,
    delete_reaction,
    load_comment_ratings,
    load_comments_branch,
    load_reactions_by,
    load_shout_comments,
    load_shout_ratings,
    update_reaction,
)
from resolvers.reader import (
    get_shout,
    load_shouts_by,
    load_shouts_random_top,
    load_shouts_search,
    load_shouts_unrated,
)
from resolvers.topic import (
    get_topic,
    get_topic_authors,
    get_topic_followers,
    get_topics_all,
    get_topics_by_author,
    get_topics_by_community,
)

events_register()

__all__ = [
    "admin_get_roles",
    # admin
    "admin_get_users",
    "confirm_email",
    "create_draft",
    # reaction
    "create_reaction",
    "delete_draft",
    "delete_reaction",
    # "delete_shout",
    # "update_shout",
    # follower
    "follow",
    # author
    "get_author",
    "get_author_followers",
    "get_author_follows",
    "get_author_follows_authors",
    "get_author_follows_topics",
    "get_authors_all",
    "get_collection",
    "get_collections_all",
    "get_collections_by_author",
    "get_communities_all",
    # "search_authors",
    # community
    "get_community",
    # auth
    "get_current_user",
    "get_my_rates_comments",
    "get_my_rates_shouts",
    # reader
    "get_shout",
    "get_shout_followers",
    # topic
    "get_topic",
    "get_topic_authors",
    "get_topic_followers",
    "get_topics_all",
    "get_topics_by_author",
    "get_topics_by_community",
    "load_authors_by",
    "load_authors_search",
    "load_comment_ratings",
    "load_comments_branch",
    # draft
    "load_drafts",
    # notifier
    "load_notifications",
    "load_reactions_by",
    "load_shout_comments",
    "load_shout_ratings",
    "load_shouts_authored_by",
    "load_shouts_by",
    "load_shouts_coauthored",
    "load_shouts_discussed",
    # feed
    "load_shouts_feed",
    "load_shouts_followed_by",
    "load_shouts_random_top",
    "load_shouts_search",
    "load_shouts_unrated",
    "load_shouts_with_topic",
    "login",
    "notification_mark_seen",
    "notifications_seen_after",
    "notifications_seen_thread",
    "publish_draft",
    # rating
    "rate_author",
    "register_by_email",
    "send_link",
    "unfollow",
    "unpublish_draft",
    "unpublish_shout",
    "update_author",
    "update_draft",
    "update_reaction",
]
