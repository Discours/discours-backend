from dateutil.parser import parse as date_parse
import json
from os.path import abspath
from orm import Shout, Comment, CommentRating, User
from orm.base import local_session
from migration.html2text import html2text

users_dict = json.loads(open(abspath('migration/data/users.dict.json')).read())
topics_dict = json.loads(open(abspath('migration/data/topics.dict.json')).read()) # old_id keyed

def migrate(entry):
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
        author: Int!
        body: String!
        replyTo: Int!
        createdAt: DateTime!
        updatedAt: DateTime
        shout: Int!
        deletedAt: DateTime
        deletedBy: Int
        rating: Int
        ratigns: [Rating]
        views: Int
        old_id: String
    }
    '''
    with local_session() as session:
        shout_id = session.query(Shout).filter(Shout.old_id == entry['_id']).first()
        author_dict = users_dict[entry['createdBy']]
        print(author_dict)
        author_id = author_dict['id']
        comment_dict = {
            'old_id': entry['_id'],
            'author': author_id,
            'createdAt': date_parse(entry['createdAt']),
            'body': html2text(entry['body']),
            'shout': shout_id
        }
        if 'rating' in entry:
          comment_dict['rating'] = entry['rating']
        if 'deleted' in entry:
          comment_dict['deleted'] = entry['deleted']
        if 'thread' in entry:
          comment_dict['old_thread'] = entry['thread']
        print(entry.keys())
        comment = Comment.create(**comment_dict)
        
        for comment_rating_old in entry.get('ratings',[]):
            rater_id = session.query(User).filter(User.old_id == comment_rating_old['createdBy']).first()
            comment_rating_dict = {
                'value': cr['value'],
                'createdBy': rater_id,
                'createdAt': date_parse(comment_rating_old['createdAt']) or ts
            }
            comment_rating = CommentRating.create(**comment_rating_dict)
            comment['ratings'].append(comment_rating)
        return comment
