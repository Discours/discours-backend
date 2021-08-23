from orm import User, Role
import frontmatter
from dateutil.parser import parse
from migration.html2text import html2text
# from migration.html2md import Converter
# markdown = Converter()
counter = 0


def add(data):
    data.emailConfirmed = False
    user = User.create(**data)
    return user

def migrate(entry):
        '''
        
        type User {
            username: String! # email
            createdAt: DateTime!
            email: String
            password: String
            oauth: String # provider:token
            viewname: String # to display
            userpic: String
            links: [String]
            emailConfirmed: Boolean # should contain all emails too
            id: Int!
            muted: Boolean
            rating: Int
            roles: [Role]
            updatedAt: DateTime
            wasOnlineAt: DateTime
            ratings: [Rating]
            slug: String
            bio: String
            notifications: [Int] 
        }

        '''
        res = {}
        res['old_id'] = entry['_id']
        res['password'] = entry['services']['password'].get('bcrypt', '')
        res['username'] = entry['emails'][0]['address']
        res['email'] = res['username']
        res['wasOnlineAt'] = parse(entry.get('loggedInAt', entry['createdAt']))
        res['emailConfirmed'] = entry['emails'][0]['verified']
        res['createdAt'] = parse(entry['createdAt'])
        res['rating'] = entry['rating'] # number
        res['roles'] = [] # entry['roles'] # roles without org is for discours.io
        res['ratings'] = [] # entry['ratings']
        res['notifications'] = []
        res['links'] = []
        res['muted'] = False
        res['bio'] = html2text(entry.get('bio', ''))
        if entry['profile']:
            res['slug'] = entry['profile'].get('path')
            res['userpic'] = entry['profile'].get('image', {'thumborId': ''}).get('thumborId', '') # adding 'https://assets.discours.io/unsafe/1600x' in web ui
            fn = entry['profile'].get('firstName', '')
            ln = entry['profile'].get('lastName', '')
            viewname = res['slug'] if res['slug'] else 'anonymous'
            viewname = fn if fn else viewname
            viewname = (viewname + ' ' + ln) if ln else viewname
            viewname = entry['profile']['path'] if len(viewname) < 2 else viewname
            res['viewname'] = viewname
            fb = entry['profile'].get('facebook', False)
            if fb:
                res['links'].append(fb)
            vk = entry['profile'].get('vkontakte', False)
            if vk:
                res['links'].append(vk)
            tr = entry['profile'].get('twitter', False)
            if tr:
                res['links'].append(tr)
            ws = entry['profile'].get('website', False)
            if ws:
                res['links'].append(ws)
            if not res['slug']:
                res['slug'] = res['links'][0].split('/')[-1]
        if not res['slug']:
            res['slug'] = res['email'].split('@')[0]
        else:
            old = res['old_id']
            del res['old_id']
            user = User.create(**res.copy())
            res['id'] = user.id
            res['old_id'] = old
            return res