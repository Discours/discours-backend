from datetime import datetime
from dateutil.parser import parse as date_parse
from orm import Comment, CommentRating, User
from orm.base import local_session
from migration.html2text import html2text
from orm.shout import Shout

ts = datetime.now()

def migrate(entry, storage):
	'''
	{
	  "_id": "hdtwS8fSyFLxXCgSC",
	  "body": "<p>",
	  "contentItem": "mnK8KsJHPRi8DrybQ",
	  "createdBy": "bMFPuyNg6qAD2mhXe",
	  "thread": "01/",
	  "createdAt": "2016-04-19 04:33:53+00:00",
	  "ratings": [
		{ "createdBy": "AqmRukvRiExNpAe8C", "value": 1 },
		{ "createdBy": "YdE76Wth3yqymKEu5", "value": 1 }
	  ],
	  "rating": 2,
	  "updatedAt": "2020-05-27 19:22:57.091000+00:00",
	  "updatedBy": "0"
	}

	->

	type Comment {
		id: Int!
		createdBy: User!
		body: String!
		replyTo: Comment!
		createdAt: DateTime!
		updatedAt: DateTime
		shout: Shout!
		deletedAt: DateTime
		deletedBy: User
		ratings: [CommentRating]
		views: Int
	}
	'''
	if entry.get('deleted'): return
	comment_dict = {}
	# FIXME: comment_dict['createdAt'] = ts if not entry.get('createdAt') else date_parse(entry.get('createdAt'))
	# print('[migration] comment original date %r' % entry.get('createdAt'))
	# print('[migration] comment date %r ' % comment_dict['createdAt'])
	comment_dict['body'] = html2text(entry.get('body', ''))
	comment_dict['oid'] = entry['_id']
	if entry.get('createdAt'): comment_dict['createdAt'] = date_parse(entry.get('createdAt'))
	shout_oid = entry.get('contentItem')
	if not shout_oid in storage['shouts']['by_oid']: 
		print('[migration] no shout for comment', entry)
	else:
		with local_session() as session:
			author = session.query(User).filter(User.oid == entry['createdBy']).first()
			shout_dict = storage['shouts']['by_oid'][shout_oid]
			if shout_dict:
				comment_dict['shout'] = shout_dict['oid']
				comment_dict['createdBy'] = author.slug if author else 'discours'
				# FIXME if entry.get('deleted'): comment_dict['deletedAt'] = date_parse(entry['updatedAt']) or ts
				# comment_dict['deletedBy'] = session.query(User).filter(User.oid == (entry.get('updatedBy') or dd['oid'])).first()
				# FIXME if entry.get('updatedAt'): comment_dict['updatedAt'] = date_parse(entry['updatedAt']) or ts
				#for [k, v] in comment_dict.items():
				#	if not v: del comment_dict[f]
				#	if k.endswith('At'):
				#		try: comment_dict[k] = datetime(comment_dict[k])
				#		except: print(k)
				#	# print('[migration] comment keys:', f)

				comment = Comment.create(**comment_dict)
				
				comment_dict['id'] = comment.id
				comment_dict['ratings'] = []
				comment_dict['oid'] = entry['_id']
				# print(comment)
				for comment_rating_old in entry.get('ratings',[]):
					rater = session.query(User).filter(User.oid == comment_rating_old['createdBy']).first()
					if rater and comment:
						comment_rating_dict = {
							'value': comment_rating_old['value'],
							'createdBy': rater.slug,
							'comment_id': comment.id
						}
						cts = comment_rating_old.get('createdAt')
						if cts: comment_rating_dict['createdAt'] = date_parse(cts)
						try:
							CommentRating.create(**comment_rating_dict)
							comment_dict['ratings'].append(comment_rating_dict)
						except Exception as e:
							print('[migration] comment rating error: %r' % comment_rating_dict)
							raise e
			else:
				print('[migration] error: cannot find shout for comment %r' % comment_dict)
		return comment_dict

def migrate_2stage(cmt, old_new_id):
	reply_oid = cmt.get('replyTo')
	if not reply_oid: return
	new_id = old_new_id.get(cmt['_id'])
	if not new_id: return
	with local_session() as session:
		comment = session.query(Comment).filter(Comment.id == new_id).first()
		comment.replyTo = old_new_id.get(reply_oid)
		session.commit()
