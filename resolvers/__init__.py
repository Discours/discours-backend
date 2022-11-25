from resolvers.auth import (
    login,
    sign_out,
    is_email_used,
    register_by_email,
    confirm_email,
    auth_send_link,
    get_current_user,
)

from resolvers.create.collab import remove_author, invite_author
from resolvers.create.migrate import markdown_body
from resolvers.create.editor import create_shout, delete_shout, update_shout

from resolvers.zine.profile import (
    load_authors_by,
    rate_user,
    update_profile,
    get_authors_all
)

from resolvers.zine.reactions import (
    create_reaction,
    delete_reaction,
    update_reaction,
    reactions_unfollow,
    reactions_follow,
    load_reactions_by
)
from resolvers.zine.topics import (
    topic_follow,
    topic_unfollow,
    topics_by_author,
    topics_by_community,
    topics_all,
    get_topic
)

from resolvers.zine.following import (
    follow,
    unfollow
)

from resolvers.zine.load import (
    load_shout,
    load_shouts_by
)

from resolvers.inbox.chats import (
    create_chat,
    delete_chat,
    update_chat,
    invite_to_chat
)
from resolvers.inbox.messages import (
    create_message,
    delete_message,
    update_message,
    message_generator,
    mark_as_read
)
from resolvers.inbox.load import (
    load_chats,
    load_messages_by,
    load_recipients
)
from resolvers.inbox.search import search_recipients

__all__ = [
    # auth
    "login",
    "register_by_email",
    "is_email_used",
    "confirm_email",
    "auth_send_link",
    "sign_out",
    "get_current_user",
    # zine.profile
    "load_authors_by",
    "rate_user",
    "update_profile",
    "get_authors_all",
    # zine.load
    "load_shout",
    "load_shouts_by",
    # zine.following
    "follow",
    "unfollow",
    # create.editor
    "create_shout",
    "update_shout",
    "delete_shout",
    # create.migrate
    "markdown_body",
    # create.collab
    "invite_author",
    "remove_author",
    # zine.topics
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
    # inbox
    "load_chats",
    "load_messages_by",
    "invite_to_chat",
    "create_chat",
    "delete_chat",
    "update_chat",
    "create_message",
    "delete_message",
    "update_message",
    "message_generator",
    "mark_as_read",
    "load_recipients",
    "search_recipients"
]
