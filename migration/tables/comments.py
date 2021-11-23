from dateutil.parser import parse as date_parse
import json
import datetime
from os.path import abspath
from orm import Shout, Comment, CommentRating, User
from orm.base import local_session
from migration.html2text import html2text

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
        ratings: [CommentRating]
        views: Int
        old_id: String
        old_thread: String
    }
    '''
    with local_session() as session:
        shout = session.query(Shout).filter(Shout.old_id == entry['_id']).first()
        if not shout: shout = session.query(Shout).first()
        author = session.query(User).filter(User.old_id == entry['_id']).first()
        comment_dict = {
            'old_id': entry['_id'],
            'author': author.id if author else 0,
            'createdAt': date_parse(entry['createdAt']),
            'body': html2text(entry['body']),
            'shout': shout.id
        }
        #TODO save as CommentRating
        #if 'rating' in entry:
        #  comment_dict['rating'] = entry['rating']
        if entry.get('deleted'):
          comment_dict['deletedAt'] = date_parse(entry['updatedAt'])
          comment_dict['deletedBy'] = str(entry['updatedBy'])
        if entry.get('updatedAt'):
          comment_dict['updatedAt'] = date_parse(entry['updatedAt'])
          # comment_dict['updatedBy'] = str(entry.get('updatedBy', 0)) invalid keyword for Comment
        if 'thread' in entry:
          comment_dict['old_thread'] = entry['thread']
        # print(comment_dict)
        comment = Comment.create(**comment_dict)
        comment_dict['id'] = comment.id
        comment_dict['ratings'] = []
        # print(comment)
        for comment_rating_old in entry.get('ratings',[]):
            rater = session.query(User).filter(User.old_id == comment_rating_old['createdBy']).first()
            if rater and comment:
              comment_rating_dict = {
                  'value': comment_rating_old['value'],
                  'createdBy': rater.id,
                  'comment_id': comment.id
              }
              cts = comment_rating_old.get('createdAt')
              if cts: comment_rating_dict['createdAt'] = date_parse(cts)
              try:
                comment_rating = CommentRating.create(**comment_rating_dict)
                # comment_rating_dict['id'] = comment_rating.id
                comment_dict['ratings'].append(comment_rating_dict)
              except Exception as e:
                print(comment_rating_dict)
                raise e
        return comment_dict
