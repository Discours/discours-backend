import datetime
import json
from os.path import abspath
from orm import Shout
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
        return {
            'old_id': entry['_id'],
            'old_thread': entry['thread'],
            'createdBy': users_dict[entry['createdBy']],
            'createdAt': entry['createdAt'],
            'body': html2text(entry['body']),
            'shout': shout_id,
            'rating': entry['rating'],
            'ratings': [] # TODO: ratings in comments
        }
    return None
