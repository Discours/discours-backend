from orm import User, Role
import frontmatter
from dateutil.parser import parse
from migration.html2text import html2text
# from migration.html2md import Converter
# markdown = Converter()
counter = 0

def migrate(entry, limit=668):
  '''

  type User {
      username: String! # email
      createdAt: DateTime!
      email: String
      password: String
      oauth: String # provider:token
      name: String # to display
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
  res['roles'] = [] # entry['roles'] # roles by community
  res['ratings'] = [] # entry['ratings']
  res['notifications'] = []
  res['links'] = []
  res['muted'] = False
  res['bio'] = html2text(entry.get('bio', ''))
  if entry['profile']:
      res['slug'] = entry['profile'].get('path')
      try:
        res['userpic'] = 'https://assets.discours.io/unsafe/100x/' + entry['profile']['thumborId']
      except KeyError:
        try:
          res['userpic'] = entry['profile']['image']['url']
        except KeyError:
          res['userpic'] = ''
      fn = entry['profile'].get('firstName', '')
      ln = entry['profile'].get('lastName', '')
      name = res['slug'] if res['slug'] else 'anonymous'
      name = fn if fn else name
      name = (name + ' ' + ln) if ln else name
      name = entry['profile']['path'] if len(name) < 2 else name
      res['name'] = name
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
      user = User.create(**res.copy())
      res['id'] = user.id
      return res
