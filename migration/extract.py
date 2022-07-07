import os
import re
import base64
import sys
from migration.html2text import html2text

TOOLTIP_REGEX = r'(\/\/\/(.+)\/\/\/)'
contentDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', 'discoursio-web', 'content')
s3 = 'https://discours-io.s3.amazonaws.com/'
cdn = 'https://assets.discours.io'

def replace_tooltips(body): 
	# FIXME: if you prefer regexp
	newbody = body
	matches = list(re.finditer(TOOLTIP_REGEX, body, re.IGNORECASE | re.MULTILINE))[1:]
	for match in matches:
		newbody = body.replace(match.group(1), '<Tooltip text="' + match.group(2) + '" />') # FIXME: doesn't work
	if len(matches) > 0: 
		print('[extract] found %d tooltips' % len(matches))
	return newbody


def place_tooltips(body):
	parts = body.split('&&&')
	l = len(parts)
	newparts = list(parts)
	placed = False
	if l & 1:
		if l > 1: 
			i = 1
			print('[extract] found %d tooltips' % (l-1))
			for part in parts[1:]:
				if i & 1: 
					# print([ len(p) for p in parts ])
					# print('[extract] tooltip: ' + part)
					if 'a class="footnote-url" href=' in part:
						print('[extract] footnote: ' + part)
						fn = 'a class="footnote-url" href="'
						link = part.split(fn,1)[1].split('"', 1)[0]
						extracted_part = part.split(fn,1)[0] + ' ' + part.split('/', 1)[-1]
						newparts[i] = '<Tooltip' + (' link="' + link + '" ' if link else '') + '>' + extracted_part + '</Tooltip>'
					else:
						newparts[i] = '<Tooltip>%s</Tooltip>' % part
				else:
					# print('[extract] pass: ' + part[:10] + '..')
					newparts[i] = part
				i += 1
			placed = True
	return (''.join(newparts), placed)

IMG_REGEX = r"\!\[(.*?)\]\((data\:image\/(png|jpeg|jpg);base64\,((?:[A-Za-z\d+\/]{4})*(?:[A-Za-z\d+\/]{3}=|[A-Za-z\d+\/]{2}==)))\)"
public = '../discoursio-web/public'
cache = {}


def reextract_images(body, oid): 
	# FIXME: if you prefer regexp
	matches = list(re.finditer(IMG_REGEX, body, re.IGNORECASE | re.MULTILINE))[1:]
	i = 0
	for match in matches:
		print('[extract] image ' + match.group(1))
		ext = match.group(3)
		name = oid + str(i)
		link = public + '/upload/image-' + name + '.' + ext
		img = match.group(4)
		title = match.group(1) # FIXME: this is not the title
		if img not in cache:
			content = base64.b64decode(img + '==')
			print(str(len(img)) + ' image bytes been written')
			open('../' + link, 'wb').write(content)
			cache[img] = name
			i += 1
		else:
			print('[extract] image cached ' + cache[img])
		body.replace(str(match), '![' + title + '](' + cdn + link + ')') # FIXME: this does not work
	return body

IMAGES = {
	'data:image/png': 'png',
	'data:image/jpg': 'jpg',
	'data:image/jpeg': 'jpg',
}

sep = ';base64,'

def extract_imageparts(bodyparts, prefix):
	# recursive loop
	for current in bodyparts:
		i = bodyparts.index(current)
		for mime in IMAGES.keys():
			if mime == current[-len(mime):] and (i + 1 < len(bodyparts)):
				print('[extract] ' + mime)
				next = bodyparts[i+1]
				ext = IMAGES[mime]
				b64end = next.index(')')
				b64encoded = next[:b64end]
				name = prefix + '-' + str(len(cache))
				link = '/upload/image-' + name + '.' + ext
				print('[extract] name: ' + name)
				print('[extract] link: ' + link)
				print('[extract] %d bytes' % len(b64encoded))
				if b64encoded not in cache:
					try:
						content = base64.b64decode(b64encoded + '==')
						open(public + link, 'wb').write(content)
						print('[extract] ' +str(len(content)) + ' image bytes been written')
						cache[b64encoded] = name
					except:
						raise Exception
						# raise Exception('[extract] error decoding image %r' %b64encoded)
				else:
					print('[extract] cached: ' + cache[b64encoded])
					name = cache[b64encoded]
					link = cdn + '/upload/image-' + name + '.' + ext
				bodyparts[i] = current[:-len(mime)] + current[-len(mime):] + link + next[-b64end:]
				bodyparts[i+1] = next[:-b64end]
				break
	return extract_imageparts(sep.join(bodyparts[i+1:]), prefix) \
		if len(bodyparts) > (i + 1) else ''.join(bodyparts)

def extract_images(body, oid):
	newbody = ''
	body = body\
		.replace(' [](data:image', '![](data:image')\
		.replace('\n[](data:image', '![](data:image')
	parts = body.split(sep)
	i = 0
	if len(parts) > 1: newbody = extract_imageparts(parts, oid)
	else: newbody = body
	return newbody


def cleanup(body):
	newbody = body\
		.replace('<', '').replace('>', '')\
		.replace('{', '(').replace('}', ')')\
		.replace('…', '...')\
		.replace(' __ ', ' ')\
		.replace('_ _', ' ')\
		.replace('****',  '')\
		.replace('\u00a0', ' ')\
		.replace('\u02c6', '^')\
		.replace('\u00a0',' ')\
		.replace('\ufeff', '')\
		.replace('\u200b', '')\
		.replace('\u200c', '')\
		# .replace('\u2212', '-')
	return newbody

def extract(body, oid):
	if body:
		newbody = extract_images(body, oid)
		if not newbody: raise Exception('extract_images error')
		newbody = cleanup(newbody)
		if not newbody: raise Exception('cleanup error')
		newbody, placed = place_tooltips(newbody)
		if not newbody: raise Exception('place_tooltips error')
		if placed:
			newbody = 'import Tooltip from \'$/components/Article/Tooltip\'\n\n' + newbody
		return newbody
	return body

def prepare_body(entry):
	# print('[migration] preparing body %s' % entry.get('slug',''))
	# body modifications
	body = ''
	body_orig = entry.get('body', '')
	if not body_orig: body_orig = ''

	if entry.get('type') == 'Literature':
		print('[extract] literature')
		for m in entry.get('media', []):
			t = m.get('title', '')
			if t: body_orig += '<h5>' + t + '</h5>\n'
			body_orig += (m.get('body') or '').replace((m.get('literatureBody') or ''), '') + m.get('literatureBody', '') + '\n'

	elif entry.get('type') == 'Video':
		print('[extract] embedding video')
		providers = set([])
		video_url = ''
		require = False
		for m in entry.get('media', []):
			yt = m.get('youtubeId', '')
			vm = m.get('vimeoId', '')
			if yt:
				require = True
				providers.add('YouTube')
				video_url = 'https://www.youtube.com/watch?v=' + yt
				body += '<YouTube youtubeId=\'' + yt + '\' />\n'
			if vm:
				require = True
				providers.add('Vimeo')
				video_url = 'https://vimeo.com/' + vm
				body += '<Vimeo vimeoId=\''  + vm + '\' />\n'
			body += extract(html2text(m.get('body', '')), entry['_id'])
			if video_url == '#': print(entry.get('media', 'UNKNOWN MEDIA PROVIDER!'))
		if require: body = 'import { ' + ','.join(list(providers)) + ' } from \'solid-social\'\n\n' + body + '\n'
		# already body_orig = entry.get('body', '')

	elif entry.get('type') == 'Music':
		print('[extract] music album')
		for m in entry.get('media', []):
			artist = m.get('performer')
			trackname = ''
			if artist: trackname += artist + ' - '
			if 'title' in m: trackname += m.get('title','')
			body += '<MusicPlayer src=\"' + m.get('fileUrl','') + '\" title=\"' + trackname + '\" />\n' 
			body += extract(html2text(m.get('body', '')), entry['_id'])
		body = 'import MusicPlayer from \'$/components/Article/MusicPlayer\'\n\n' + body + '\n'
		# already body_orig = entry.get('body', '')

	elif entry.get('type') == 'Image':
		print('[extract] image gallery')
		cover = ''
		if 'thumborId' in entry: cover = cdn + '/unsafe/1600x/' + entry['thumborId']
		if not cover:
			if 'image' in entry: cover = entry['image'].get('url', '')
			if 'cloudinary' in cover: cover = ''
		else:
			print('[migration] cover: ' + cover)
		images = {}
		for m in entry.get('media', []):
			b = ''
			title = m.get('title','').replace('\n', ' ').replace('&nbsp;', ' ')
			u = m.get('image', {}).get('url', '') or m.get('thumborId') or cover
			u = str(u)
			b += '<h4>' + title + '</h4>\n' + body_orig
			if not u.startswith('http'): u = s3 + u
			if not u: print('[extract] no image for ' + str(m))
			if 'cloudinary' in u: u = 'img/lost.svg'
			if u not in images.keys():
				# print('[extract] image: ' + u)
				images[u] = title
				b += '<img src=\"' + u + '\" alt=\"'+ title +'\" />\n'
			b += m.get('body', '') + '\n'
			body += extract(html2text(b), entry['_id'])

	elif not body_orig:
		for up in entry.get('bodyHistory', []) or []:
			body_orig = up.get('text', '') or ''
			if body_orig:
				print('[extract] body from history!')
				break
			if not body and not body_orig: print('[extract] error: EMPTY BODY')

	# body_html = str(BeautifulSoup(body_orig, features="html.parser"))
	# print('[extract] adding original body')
	if body_orig: body += extract(html2text(body_orig), entry['_id'])
	if entry['slug'] in sys.argv: 
		open(contentDir + '/' + entry['slug'] + '.html', 'w')\
			.write(entry.get('body',''))
	return body
