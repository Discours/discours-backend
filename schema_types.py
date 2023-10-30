from enum import Enum
from typing import Any, ClassVar, List, Optional, TypedDict

## Scalars

DateTime = Any

MessageStatus = Enum("MessageStatus", "NEW UPDATED DELETED")


ReactionStatus = Enum("ReactionStatus", "NEW UPDATED CHANGED EXPLAINED DELETED")


FollowingEntity = Enum("FollowingEntity", "TOPIC AUTHOR COMMUNITY REACTIONS")


ReactionKind = Enum(
    "ReactionKind",
    "LIKE DISLIKE AGREE DISAGREE PROOF DISPROOF COMMENT QUOTE PROPOSE ASK REMARK FOOTNOTE ACCEPT REJECT",
)


NotificationType = Enum("NotificationType", "NEW_COMMENT NEW_REPLY")


AuthResult = TypedDict(
    "AuthResult",
    {
        "error": Optional[str],
        "token": Optional[str],
        "user": Optional["User"],
    },
)


ChatMember = TypedDict(
    "ChatMember",
    {
        "id": int,
        "slug": str,
        "name": str,
        "userpic": Optional[str],
        "lastSeen": Optional["DateTime"],
        "online": Optional[bool],
    },
)


AuthorStat = TypedDict(
    "AuthorStat",
    {
        "followings": Optional[int],
        "followers": Optional[int],
        "rating": Optional[int],
        "commented": Optional[int],
        "shouts": Optional[int],
    },
)


Author = TypedDict(
    "Author",
    {
        "id": int,
        "slug": str,
        "name": str,
        "userpic": Optional[str],
        "caption": Optional[str],
        "bio": Optional[str],
        "about": Optional[str],
        "links": Optional[List[str]],
        "stat": Optional["AuthorStat"],
        "roles": Optional[List["Role"]],
        "lastSeen": Optional["DateTime"],
        "createdAt": Optional["DateTime"],
    },
)


Result = TypedDict(
    "Result",
    {
        "error": Optional[str],
        "slugs": Optional[List[str]],
        "chat": Optional["Chat"],
        "chats": Optional[List["Chat"]],
        "message": Optional["Message"],
        "messages": Optional[List["Message"]],
        "members": Optional[List["ChatMember"]],
        "shout": Optional["Shout"],
        "shouts": Optional[List["Shout"]],
        "author": Optional["Author"],
        "authors": Optional[List["Author"]],
        "reaction": Optional["Reaction"],
        "reactions": Optional[List["Reaction"]],
        "topic": Optional["Topic"],
        "topics": Optional[List["Topic"]],
        "community": Optional["Community"],
        "communities": Optional[List["Community"]],
    },
)


ReactionUpdating = TypedDict(
    "ReactionUpdating",
    {
        "error": Optional[str],
        "status": Optional["ReactionStatus"],
        "reaction": Optional["Reaction"],
    },
)


Mutation = TypedDict(
    "Mutation",
    {
        "createChat": "CreateChatMutationResult",
        "updateChat": "UpdateChatMutationResult",
        "deleteChat": "DeleteChatMutationResult",
        "createMessage": "CreateMessageMutationResult",
        "updateMessage": "UpdateMessageMutationResult",
        "deleteMessage": "DeleteMessageMutationResult",
        "markAsRead": "MarkAsReadMutationResult",
        "getSession": "GetSessionMutationResult",
        "registerUser": "RegisterUserMutationResult",
        "sendLink": "SendLinkMutationResult",
        "confirmEmail": "ConfirmEmailMutationResult",
        "createShout": "CreateShoutMutationResult",
        "updateShout": "UpdateShoutMutationResult",
        "deleteShout": "DeleteShoutMutationResult",
        "rateUser": "RateUserMutationResult",
        "updateProfile": "UpdateProfileMutationResult",
        "createTopic": "CreateTopicMutationResult",
        "updateTopic": "UpdateTopicMutationResult",
        "destroyTopic": "DestroyTopicMutationResult",
        "createReaction": "CreateReactionMutationResult",
        "updateReaction": "UpdateReactionMutationResult",
        "deleteReaction": "DeleteReactionMutationResult",
        "follow": "FollowMutationResult",
        "unfollow": "UnfollowMutationResult",
        "markNotificationAsRead": "MarkNotificationAsReadMutationResult",
        "markAllNotificationsAsRead": "MarkAllNotificationsAsReadMutationResult",
    },
)


CreateChatParams = TypedDict(
    "CreateChatParams",
    {
        "title": Optional[str],
        "members": List[int],
    },
)


CreateChatMutationResult = ClassVar["Result"]


UpdateChatParams = TypedDict(
    "UpdateChatParams",
    {
        "chat": "ChatInput",
    },
)


UpdateChatMutationResult = ClassVar["Result"]


DeleteChatParams = TypedDict(
    "DeleteChatParams",
    {
        "chatId": str,
    },
)


DeleteChatMutationResult = ClassVar["Result"]


CreateMessageParams = TypedDict(
    "CreateMessageParams",
    {
        "chat": str,
        "body": str,
        "replyTo": Optional[int],
    },
)


CreateMessageMutationResult = ClassVar["Result"]


UpdateMessageParams = TypedDict(
    "UpdateMessageParams",
    {
        "chatId": str,
        "id": int,
        "body": str,
    },
)


UpdateMessageMutationResult = ClassVar["Result"]


DeleteMessageParams = TypedDict(
    "DeleteMessageParams",
    {
        "chatId": str,
        "id": int,
    },
)


DeleteMessageMutationResult = ClassVar["Result"]


MarkAsReadParams = TypedDict(
    "MarkAsReadParams",
    {
        "chatId": str,
        "ids": List[int],
    },
)


MarkAsReadMutationResult = ClassVar["Result"]


GetSessionMutationResult = ClassVar["AuthResult"]


RegisterUserParams = TypedDict(
    "RegisterUserParams",
    {
        "email": str,
        "password": Optional[str],
        "name": Optional[str],
    },
)


RegisterUserMutationResult = ClassVar["AuthResult"]


SendLinkParams = TypedDict(
    "SendLinkParams",
    {
        "email": str,
        "lang": Optional[str],
        "template": Optional[str],
    },
)


SendLinkMutationResult = ClassVar["Result"]


ConfirmEmailParams = TypedDict(
    "ConfirmEmailParams",
    {
        "token": str,
    },
)


ConfirmEmailMutationResult = ClassVar["AuthResult"]


CreateShoutParams = TypedDict(
    "CreateShoutParams",
    {
        "inp": "ShoutInput",
    },
)


CreateShoutMutationResult = ClassVar["Result"]


UpdateShoutParams = TypedDict(
    "UpdateShoutParams",
    {
        "shout_id": int,
        "shout_input": Optional["ShoutInput"],
        "publish": Optional[bool],
    },
)


UpdateShoutMutationResult = ClassVar["Result"]


DeleteShoutParams = TypedDict(
    "DeleteShoutParams",
    {
        "shout_id": int,
    },
)


DeleteShoutMutationResult = ClassVar["Result"]


RateUserParams = TypedDict(
    "RateUserParams",
    {
        "slug": str,
        "value": int,
    },
)


RateUserMutationResult = ClassVar["Result"]


UpdateProfileParams = TypedDict(
    "UpdateProfileParams",
    {
        "profile": "ProfileInput",
    },
)


UpdateProfileMutationResult = ClassVar["Result"]


CreateTopicParams = TypedDict(
    "CreateTopicParams",
    {
        "input": "TopicInput",
    },
)


CreateTopicMutationResult = ClassVar["Result"]


UpdateTopicParams = TypedDict(
    "UpdateTopicParams",
    {
        "input": "TopicInput",
    },
)


UpdateTopicMutationResult = ClassVar["Result"]


DestroyTopicParams = TypedDict(
    "DestroyTopicParams",
    {
        "slug": str,
    },
)


DestroyTopicMutationResult = ClassVar["Result"]


CreateReactionParams = TypedDict(
    "CreateReactionParams",
    {
        "reaction": "ReactionInput",
    },
)


CreateReactionMutationResult = ClassVar["Result"]


UpdateReactionParams = TypedDict(
    "UpdateReactionParams",
    {
        "id": int,
        "reaction": "ReactionInput",
    },
)


UpdateReactionMutationResult = ClassVar["Result"]


DeleteReactionParams = TypedDict(
    "DeleteReactionParams",
    {
        "id": int,
    },
)


DeleteReactionMutationResult = ClassVar["Result"]


FollowParams = TypedDict(
    "FollowParams",
    {
        "what": "FollowingEntity",
        "slug": str,
    },
)


FollowMutationResult = ClassVar["Result"]


UnfollowParams = TypedDict(
    "UnfollowParams",
    {
        "what": "FollowingEntity",
        "slug": str,
    },
)


UnfollowMutationResult = ClassVar["Result"]


MarkNotificationAsReadParams = TypedDict(
    "MarkNotificationAsReadParams",
    {
        "notification_id": int,
    },
)


MarkNotificationAsReadMutationResult = ClassVar["Result"]


MarkAllNotificationsAsReadMutationResult = ClassVar["Result"]


NotificationsQueryResult = TypedDict(
    "NotificationsQueryResult",
    {
        "notifications": List["Notification"],
        "totalCount": int,
        "totalUnreadCount": int,
    },
)


MySubscriptionsQueryResult = TypedDict(
    "MySubscriptionsQueryResult",
    {
        "topics": List["Topic"],
        "authors": List["Author"],
    },
)


Query = TypedDict(
    "Query",
    {
        "loadChats": "LoadChatsQueryResult",
        "loadMessagesBy": "LoadMessagesByQueryResult",
        "loadRecipients": "LoadRecipientsQueryResult",
        "searchRecipients": "SearchRecipientsQueryResult",
        "searchMessages": "SearchMessagesQueryResult",
        "isEmailUsed": "IsEmailUsedQueryResult",
        "signIn": "SignInQueryResult",
        "signOut": "SignOutQueryResult",
        "loadAuthorsBy": "LoadAuthorsByQueryResult",
        "loadShout": "LoadShoutQueryResult",
        "loadShouts": "LoadShoutsQueryResult",
        "loadDrafts": "LoadDraftsQueryResult",
        "loadReactionsBy": "LoadReactionsByQueryResult",
        "userFollowers": "UserFollowersQueryResult",
        "userFollowedAuthors": "UserFollowedAuthorsQueryResult",
        "userFollowedTopics": "UserFollowedTopicsQueryResult",
        "authorsAll": "AuthorsAllQueryResult",
        "getAuthor": "GetAuthorQueryResult",
        "myFeed": "MyFeedQueryResult",
        "markdownBody": "MarkdownBodyQueryResult",
        "getTopic": "GetTopicQueryResult",
        "topicsAll": "TopicsAllQueryResult",
        "topicsRandom": "TopicsRandomQueryResult",
        "topicsByCommunity": "TopicsByCommunityQueryResult",
        "topicsByAuthor": "TopicsByAuthorQueryResult",
        "loadNotifications": "LoadNotificationsQueryResult",
        "loadMySubscriptions": "LoadMySubscriptionsQueryResult",
    },
)


LoadChatsParams = TypedDict(
    "LoadChatsParams",
    {
        "limit": Optional[int],
        "offset": Optional[int],
    },
)


LoadChatsQueryResult = ClassVar["Result"]


LoadMessagesByParams = TypedDict(
    "LoadMessagesByParams",
    {
        "by": "MessagesBy",
        "limit": Optional[int],
        "offset": Optional[int],
    },
)


LoadMessagesByQueryResult = ClassVar["Result"]


LoadRecipientsParams = TypedDict(
    "LoadRecipientsParams",
    {
        "limit": Optional[int],
        "offset": Optional[int],
    },
)


LoadRecipientsQueryResult = ClassVar["Result"]


SearchRecipientsParams = TypedDict(
    "SearchRecipientsParams",
    {
        "query": str,
        "limit": Optional[int],
        "offset": Optional[int],
    },
)


SearchRecipientsQueryResult = ClassVar["Result"]


SearchMessagesParams = TypedDict(
    "SearchMessagesParams",
    {
        "by": "MessagesBy",
        "limit": Optional[int],
        "offset": Optional[int],
    },
)


SearchMessagesQueryResult = ClassVar["Result"]


IsEmailUsedParams = TypedDict(
    "IsEmailUsedParams",
    {
        "email": str,
    },
)


IsEmailUsedQueryResult = bool


SignInParams = TypedDict(
    "SignInParams",
    {
        "email": str,
        "password": Optional[str],
        "lang": Optional[str],
    },
)


SignInQueryResult = ClassVar["AuthResult"]


SignOutQueryResult = ClassVar["AuthResult"]


LoadAuthorsByParams = TypedDict(
    "LoadAuthorsByParams",
    {
        "by": Optional["AuthorsBy"],
        "limit": Optional[int],
        "offset": Optional[int],
    },
)


LoadAuthorsByQueryResult = ClassVar[List["Author"]]


LoadShoutParams = TypedDict(
    "LoadShoutParams",
    {
        "slug": Optional[str],
        "shout_id": Optional[int],
    },
)


LoadShoutQueryResult = ClassVar[Optional["Shout"]]


LoadShoutsParams = TypedDict(
    "LoadShoutsParams",
    {
        "options": Optional["LoadShoutsOptions"],
    },
)


LoadShoutsQueryResult = ClassVar[List["Shout"]]


LoadDraftsQueryResult = ClassVar[List["Shout"]]


LoadReactionsByParams = TypedDict(
    "LoadReactionsByParams",
    {
        "by": "ReactionBy",
        "limit": Optional[int],
        "offset": Optional[int],
    },
)


LoadReactionsByQueryResult = ClassVar[List["Reaction"]]


UserFollowersParams = TypedDict(
    "UserFollowersParams",
    {
        "slug": str,
    },
)


UserFollowersQueryResult = ClassVar[List["Author"]]


UserFollowedAuthorsParams = TypedDict(
    "UserFollowedAuthorsParams",
    {
        "slug": str,
    },
)


UserFollowedAuthorsQueryResult = ClassVar[List["Author"]]


UserFollowedTopicsParams = TypedDict(
    "UserFollowedTopicsParams",
    {
        "slug": str,
    },
)


UserFollowedTopicsQueryResult = ClassVar[List["Topic"]]


AuthorsAllQueryResult = ClassVar[List["Author"]]


GetAuthorParams = TypedDict(
    "GetAuthorParams",
    {
        "slug": str,
    },
)


GetAuthorQueryResult = ClassVar[Optional["Author"]]


MyFeedParams = TypedDict(
    "MyFeedParams",
    {
        "options": Optional["LoadShoutsOptions"],
    },
)


MyFeedQueryResult = ClassVar[Optional[List["Shout"]]]


MarkdownBodyParams = TypedDict(
    "MarkdownBodyParams",
    {
        "body": str,
    },
)


MarkdownBodyQueryResult = str


GetTopicParams = TypedDict(
    "GetTopicParams",
    {
        "slug": str,
    },
)


GetTopicQueryResult = ClassVar[Optional["Topic"]]


TopicsAllQueryResult = ClassVar[List["Topic"]]


TopicsRandomParams = TypedDict(
    "TopicsRandomParams",
    {
        "amount": Optional[int],
    },
)


TopicsRandomQueryResult = ClassVar[List["Topic"]]


TopicsByCommunityParams = TypedDict(
    "TopicsByCommunityParams",
    {
        "community": str,
    },
)


TopicsByCommunityQueryResult = ClassVar[List["Topic"]]


TopicsByAuthorParams = TypedDict(
    "TopicsByAuthorParams",
    {
        "author": str,
    },
)


TopicsByAuthorQueryResult = ClassVar[List["Topic"]]


LoadNotificationsParams = TypedDict(
    "LoadNotificationsParams",
    {
        "params": "NotificationsQueryParams",
    },
)


LoadNotificationsQueryResult = ClassVar["NotificationsQueryResult"]


LoadMySubscriptionsQueryResult = ClassVar[Optional["MySubscriptionsQueryResult"]]


Resource = TypedDict(
    "Resource",
    {
        "id": int,
        "name": str,
    },
)


Operation = TypedDict(
    "Operation",
    {
        "id": int,
        "name": str,
    },
)


Permission = TypedDict(
    "Permission",
    {
        "operation": int,
        "resource": int,
    },
)


Role = TypedDict(
    "Role",
    {
        "id": int,
        "name": str,
        "community": str,
        "desc": Optional[str],
        "permissions": List["Permission"],
    },
)


Rating = TypedDict(
    "Rating",
    {
        "rater": str,
        "value": int,
    },
)


User = TypedDict(
    "User",
    {
        "id": int,
        "username": str,
        "createdAt": "DateTime",
        "lastSeen": Optional["DateTime"],
        "slug": str,
        "name": Optional[str],
        "email": Optional[str],
        "password": Optional[str],
        "oauth": Optional[str],
        "userpic": Optional[str],
        "links": Optional[List[str]],
        "emailConfirmed": Optional[bool],
        "muted": Optional[bool],
        "updatedAt": Optional["DateTime"],
        "ratings": Optional[List["Rating"]],
        "bio": Optional[str],
        "about": Optional[str],
        "communities": Optional[List[int]],
        "oid": Optional[str],
    },
)


Reaction = TypedDict(
    "Reaction",
    {
        "id": int,
        "shout": "Shout",
        "createdAt": "DateTime",
        "createdBy": "User",
        "updatedAt": Optional["DateTime"],
        "deletedAt": Optional["DateTime"],
        "deletedBy": Optional["User"],
        "range": Optional[str],
        "kind": "ReactionKind",
        "body": Optional[str],
        "replyTo": Optional[int],
        "stat": Optional["Stat"],
        "old_id": Optional[str],
        "old_thread": Optional[str],
    },
)


Shout = TypedDict(
    "Shout",
    {
        "id": int,
        "slug": str,
        "body": str,
        "lead": Optional[str],
        "description": Optional[str],
        "createdAt": "DateTime",
        "topics": Optional[List["Topic"]],
        "mainTopic": Optional[str],
        "title": Optional[str],
        "subtitle": Optional[str],
        "authors": Optional[List["Author"]],
        "lang": Optional[str],
        "community": Optional[str],
        "cover": Optional[str],
        "layout": Optional[str],
        "versionOf": Optional[str],
        "visibility": Optional[str],
        "updatedAt": Optional["DateTime"],
        "updatedBy": Optional["User"],
        "deletedAt": Optional["DateTime"],
        "deletedBy": Optional["User"],
        "publishedAt": Optional["DateTime"],
        "media": Optional[str],
        "stat": Optional["Stat"],
    },
)


Stat = TypedDict(
    "Stat",
    {
        "viewed": Optional[int],
        "reacted": Optional[int],
        "rating": Optional[int],
        "commented": Optional[int],
        "ranking": Optional[int],
    },
)


Community = TypedDict(
    "Community",
    {
        "id": int,
        "slug": str,
        "name": str,
        "desc": Optional[str],
        "pic": str,
        "createdAt": "DateTime",
        "createdBy": "User",
    },
)


Collection = TypedDict(
    "Collection",
    {
        "id": int,
        "slug": str,
        "title": str,
        "desc": Optional[str],
        "amount": Optional[int],
        "publishedAt": Optional["DateTime"],
        "createdAt": "DateTime",
        "createdBy": "User",
    },
)


TopicStat = TypedDict(
    "TopicStat",
    {
        "shouts": int,
        "followers": int,
        "authors": int,
    },
)


Topic = TypedDict(
    "Topic",
    {
        "id": int,
        "slug": str,
        "title": Optional[str],
        "body": Optional[str],
        "pic": Optional[str],
        "stat": Optional["TopicStat"],
        "oid": Optional[str],
    },
)


Token = TypedDict(
    "Token",
    {
        "createdAt": "DateTime",
        "expiresAt": Optional["DateTime"],
        "id": int,
        "ownerId": int,
        "usedAt": Optional["DateTime"],
        "value": str,
    },
)


Message = TypedDict(
    "Message",
    {
        "author": int,
        "chatId": str,
        "body": str,
        "createdAt": int,
        "id": int,
        "replyTo": Optional[int],
        "updatedAt": Optional[int],
        "seen": Optional[bool],
    },
)


Chat = TypedDict(
    "Chat",
    {
        "id": str,
        "createdAt": int,
        "createdBy": int,
        "updatedAt": int,
        "title": Optional[str],
        "description": Optional[str],
        "users": Optional[List[int]],
        "members": Optional[List["ChatMember"]],
        "admins": Optional[List[int]],
        "messages": Optional[List["Message"]],
        "unread": Optional[int],
        "private": Optional[bool],
    },
)


Notification = TypedDict(
    "Notification",
    {
        "id": int,
        "shout": Optional[int],
        "reaction": Optional[int],
        "type": "NotificationType",
        "createdAt": "DateTime",
        "seen": bool,
        "data": Optional[str],
        "occurrences": int,
    },
)


ShoutInput = TypedDict(
    "ShoutInput",
    {
        "slug": Optional[str],
        "title": Optional[str],
        "body": Optional[str],
        "lead": Optional[str],
        "description": Optional[str],
        "layout": Optional[str],
        "media": Optional[str],
        "authors": Optional[List[str]],
        "topics": Optional[List["TopicInput"]],
        "community": Optional[int],
        "mainTopic": Optional["TopicInput"],
        "subtitle": Optional[str],
        "cover": Optional[str],
    },
)


ProfileInput = TypedDict(
    "ProfileInput",
    {
        "slug": Optional[str],
        "name": Optional[str],
        "userpic": Optional[str],
        "links": Optional[List[str]],
        "bio": Optional[str],
        "about": Optional[str],
    },
)


TopicInput = TypedDict(
    "TopicInput",
    {
        "id": Optional[int],
        "slug": str,
        "title": Optional[str],
        "body": Optional[str],
        "pic": Optional[str],
    },
)


ReactionInput = TypedDict(
    "ReactionInput",
    {
        "kind": "ReactionKind",
        "shout": int,
        "range": Optional[str],
        "body": Optional[str],
        "replyTo": Optional[int],
    },
)


ChatInput = TypedDict(
    "ChatInput",
    {
        "id": str,
        "title": Optional[str],
        "description": Optional[str],
    },
)


MessagesBy = TypedDict(
    "MessagesBy",
    {
        "author": Optional[str],
        "body": Optional[str],
        "chat": Optional[str],
        "order": Optional[str],
        "days": Optional[int],
        "stat": Optional[str],
    },
)


AuthorsBy = TypedDict(
    "AuthorsBy",
    {
        "lastSeen": Optional["DateTime"],
        "createdAt": Optional["DateTime"],
        "slug": Optional[str],
        "name": Optional[str],
        "topic": Optional[str],
        "order": Optional[str],
        "days": Optional[int],
        "stat": Optional[str],
    },
)


LoadShoutsFilters = TypedDict(
    "LoadShoutsFilters",
    {
        "title": Optional[str],
        "body": Optional[str],
        "topic": Optional[str],
        "author": Optional[str],
        "layout": Optional[str],
        "excludeLayout": Optional[str],
        "visibility": Optional[str],
        "days": Optional[int],
        "reacted": Optional[bool],
    },
)


LoadShoutsOptions = TypedDict(
    "LoadShoutsOptions",
    {
        "filters": Optional["LoadShoutsFilters"],
        "with_author_captions": Optional[bool],
        "limit": int,
        "offset": Optional[int],
        "order_by": Optional[str],
        "order_by_desc": Optional[bool],
    },
)


ReactionBy = TypedDict(
    "ReactionBy",
    {
        "shout": Optional[str],
        "shouts": Optional[List[str]],
        "search": Optional[str],
        "comment": Optional[bool],
        "topic": Optional[str],
        "createdBy": Optional[str],
        "days": Optional[int],
        "sort": Optional[str],
    },
)


NotificationsQueryParams = TypedDict(
    "NotificationsQueryParams",
    {
        "limit": Optional[int],
        "offset": Optional[int],
    },
)
