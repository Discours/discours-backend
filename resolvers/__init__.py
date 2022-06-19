from resolvers.auth import login, sign_out, is_email_used, register, confirm, auth_forget, auth_reset
from resolvers.zine import get_shout_by_slug, subscribe, unsubscribe, view_shout, rate_shout, \
	top_month, top_overall, recent_published, recent_all, top_viewed, \
		shouts_by_authors, shouts_by_topics, shouts_by_communities
from resolvers.profile import get_users_by_slugs, get_current_user, shouts_reviewed, shouts_subscribed
from resolvers.topics import topic_subscribe, topic_unsubscribe, topics_by_author, \
	topics_by_community, topics_by_slugs
from resolvers.comments import create_comment, delete_comment, update_comment, rate_comment
from resolvers.collab import get_shout_proposals, create_proposal, delete_proposal, \
	update_proposal, rate_proposal, decline_proposal, disable_proposal, accept_proposal
from resolvers.editor import create_shout, delete_shout, update_shout
from resolvers.community import create_community, delete_community, get_community, get_communities

__all__ = [
	# auth
	"login",
	"register",
	"is_email_used",
	"confirm",
	"auth_forget",
	"auth_reset"
	
	# profile
	"get_current_user",
	"get_users_by_slugs",
	
	# zine
	"recent_published",
	"recent_all",
	"shouts_by_topics",
	"shouts_by_authors",
	"shouts_by_communities",
	"shouts_subscribed",
	"shouts_reviewed",
	"top_month",
	"top_overall",
	"top_viewed",
	"rate_shout",
	"view_shout",
	"get_shout_by_slug",
	
	# editor
	"create_shout",
	"update_shout",
	"delete_shout",
	
	# topics 
	"topics_by_slugs",
	"topics_by_community",
	"topics_by_author",
	"topic_subscribe",
	"topic_unsubscribe",
	
	# communities
	"get_community",
	"get_communities",
	"create_community",
	"delete_community",
	
	# comments
	"get_shout_comments",
	"create_comment",
	"update_comment",
	"delete_comment",
	
	# collab
	"get_shout_proposals",
	"create_proposal",
	"update_proposal",
	"disable_proposal",
	"accept_proposal",
	"decline_proposal",
	"delete_proposal"
	]
