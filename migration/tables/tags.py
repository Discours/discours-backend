import json

from os.path import abspath
from datetime import datetime

users_dict = json.loads(open(abspath('migration/data/users.dict.json')).read())
users_dict['0'] = {
    'id': 9999999,
    'slug': 'discours.io',
    'name': 'Дискурс',
    'userpic': 'https://discours.io/images/logo-mini.svg',
    'createdAt': '2016-03-05 22:22:00.350000'
    }

ts = datetime.now()

def migrate(entry):
    '''
    type Topic {
        slug: String! # ID
        createdBy: Int! # User
        createdAt: DateTime!
        title: String
        parents: [String] # NOTE: topic can have parent topics
        children: [String] # and children
    }
    '''
    creator = users_dict.get(entry['createdBy'], users_dict['0'])
    return {
        'slug': entry['slug'],
        'createdBy': creator['id'], # NOTE: uses an old user id
        'createdAt': entry['createdAt'],
        'title': entry['title'].lower(),
        'parents': [],
        'children': []
    }