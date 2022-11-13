from resolvers.auth import (
    login,
    sign_out,
    is_email_used,
    register_by_email,
    confirm_email,
    auth_send_link,
    get_current_user,
)
from resolvers.collab import remove_author, invite_author
from resolvers.community import (
    create_community,
    delete_community,
    get_community,
    get_communities,
)

from resolvers.migrate import markdown_body

# from resolvers.collab import invite_author, remove_author
from resolvers.editor import create_shout, delete_shout, update_shout
from resolvers.profile import (
    get_users_by_slugs,
    get_user_reacted_shouts,
    get_user_roles,
    get_top_authors,
    get_author
)

# from resolvers.feed import shouts_for_feed, my_candidates
from resolvers.reactions import (
    create_reaction,
    delete_reaction,
    update_reaction,
    reactions_unfollow,
    reactions_follow,
)
from resolvers.topics import (
    topic_follow,
    topic_unfollow,
    topics_by_author,
    topics_by_community,
    topics_all,
    get_topic
)

from resolvers.zine import (
    get_shout_by_slug,
    follow,
    unfollow,
    increment_view,
    top_month,
    top_overall,
    recent_published,
    recent_all,
    recent_commented,
    recent_reacted,
    shouts_by_authors,
    shouts_by_topics,
    shouts_by_layout_recent,
    shouts_by_layout_top,
    shouts_by_layout_topmonth,
    shouts_by_communities,
)

from resolvers.inbox.chats import load_chats, \
    create_chat, delete_chat, update_chat, \
    invite_to_chat, enter_chat
from resolvers.inbox.messages import load_chat_messages, \
    create_message, delete_message, update_message, \
    message_generator, mark_as_read
from resolvers.inbox.search import search_users, \
    search_messages, search_chats

__all__ = [
    "follow",
    "unfollow",
    # auth
    "login",
    "register_by_email",
    "is_email_used",
    "confirm_email",
    "auth_send_link",
    "sign_out",
    "get_current_user",
    # profile
    "get_users_by_slugs",
    "get_user_roles",
    "get_top_authors",
    "get_author",
    # zine
    "recent_published",
    "recent_commented",
    "recent_reacted",
    "recent_all",
    "shouts_by_topics",
    "shouts_by_layout_recent",
    "shouts_by_layout_topmonth",
    "shouts_by_layout_top",
    "shouts_by_authors",
    "shouts_by_communities",
    "get_user_reacted_shouts",
    "top_month",
    "top_overall",
    "increment_view",
    "get_shout_by_slug",
    # editor
    "create_shout",
    "update_shout",
    "delete_shout",
    # migrate
    "markdown_body",
    # collab
    "invite_author",
    "remove_author",
    # topics
    "topics_all",
    "topics_by_community",
    "topics_by_author",
    "topic_follow",
    "topic_unfollow",
    "get_topic",
    # communities
    "get_community",
    "get_communities",
    "create_community",
    "delete_community",
    # reactions
    "reactions_follow",
    "reactions_unfollow",
    "create_reaction",
    "update_reaction",
    "delete_reaction",
    # inbox
    "create_chat",
    "delete_chat",
    "update_chat",
    "load_chats",
    "create_message",
    "delete_message",
    "update_message",
    "load_chat_messages",
    "message_generator",
    "mark_as_read",
    "search_users",
    "search_chats",
    "search_messages",
    "enter_chat",
    "invite_to_chat"
]
