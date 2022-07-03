import json
import re
import base64

from migration.html2text import html2text

TOOLTIP_REGEX = r'(\/\/\/(.+)\/\/\/)'

s3 = 'https://discours-io.s3.amazonaws.com/'
cdn = 'https://assets.discours.io'
retopics = json.loads(open('migration/tables/replacements.json', 'r').read())

def replace_tooltips(body):
	newbody = body
	matches = list(re.finditer(TOOLTIP_REGEX, body, re.IGNORECASE | re.MULTILINE))[1:]
	for match in matches:
		newbody = body.replace(match.group(1), '<Tooltip text="' + match.group(2) + '" />') # FIXME: doesn't work
	if len(matches) > 0: 
		print('[extract] found %d tooltips' % len(matches))
	return newbody


def place_tooltips(body):
	parts = body.split('///')
	l = len(parts)
	newparts = list(parts)
	if l & 1:
		if l > 1: 
			i = 1
			print('[extract] found %d tooltips' % (l-1))
			for part in parts[1:]:
				if i & 1: 
					# print('[extract] tooltip: ' + part)
					if 'a class="footnote-url" href=' in part:
						fn = 'a class="footnote-url" href="'
						link = part.split(fn,1)[1].split('"', 1)[0]
						extracted_part = part.split(fn,1)[0] + ' ' + part.split('/', 1)[-1]
						newparts[i] = '<Tooltip' + (' link="' + link + '" ' if link else '') + '>' + extracted_part + '</Tooltip>'
					else:
						newparts[i] = '<Tooltip>%s</Tooltip>' % part
					# print('[extract] tooltip: ' + newparts[i])
				else:
					# print('[extract] pass: ' + part[:10] + '..')
					newparts[i] = part
				i += 1
			
	return ''.join(newparts)

IMG_REGEX = r"\!\[(.*?)\]\((data\:image\/(png|jpeg|jpg);base64\,((?:[A-Za-z\d+\/]{4})*(?:[A-Za-z\d+\/]{3}=|[A-Za-z\d+\/]{2}==)))\)"
public = '../discoursio-web/public'
cache = {}


def reextract_images(body, oid):
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


def extract_images(body, oid):
	newbody = ''
	body = body.replace(' [](data:image', '![](data:image').replace('\n[](data:image', '![](data:image')
	oldparts = body.split(sep)
	newparts = list(oldparts)
	# print()
	if len(oldparts) > 1: 
		print('[extract] images for %s' % oid)
		print('[extract] %d candidates' % (len(oldparts)-1))
		i = 0
		for current in oldparts:
			next = ''
			try: next = oldparts[i+1]
			except: newbody += current
			start = oldparts.index(current) == 0
			end = not next
			if end:
				continue
			else: # start or between
				for mime in IMAGES.keys():
					if mime in current[-15:]:
						print('[extract] ' + current[-15:])
						if ')' in next: 
							b64encoded = next.split(')')[0]
						print('[extract] '+str(i+1)+': %d bytes' % len(b64encoded))
						ext = IMAGES[mime]
						print('[extract] type: ' + mime)
						name = oid + '-' + str(i)
						print('[extract] name: ' + name)
						link = '/upload/image-' + name + '.' + ext
						print('[extract] link: ' + link)
						if b64encoded:
							if b64encoded not in cache:
								content = base64.b64decode(b64encoded + '==')
								open(public + link, 'wb').write(content)
								cache[b64encoded] = name
							else:
								print('[extract] cached: ' + cache[b64encoded])
								name = cache[b64encoded]
								link = cdn + '/upload/image-' + name + '.' + ext
							newparts[i] = current.split('![](' + mime)[0] + '![](' + link + ')'
							newparts[i+1] = next.replace(b64encoded + ')', '')
						else:
							print('[extract] ERROR: no b64encoded')
							# print(current[-15:])
				i += 1
	newbody = ''.join(newparts)
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
	newbody = extract_images(body, oid)
	newbody = cleanup(newbody)
	newbody = place_tooltips(newbody)
	return newbody

def prepare_body(entry):
	# body modifications
	body = ''
	body_orig = entry.get('body', '')
	if not body_orig: body_orig = ''

	if entry.get('type') == 'Literature':
		for m in entry.get('media', []):
			t = m.get('title', '')
			if t: body_orig += '<h5>' + t + '</h5>\n'
			body_orig += (m.get('body', '') or '')
			body_orig += '\n' + m.get('literatureBody', '') + '\n'

	elif entry.get('type') == 'Video':
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

	elif entry.get('type') == 'Music':
		for m in entry.get('media', []):
			artist = m.get('performer')
			trackname = ''
			if artist: trackname += artist + ' - '
			if 'title' in m: trackname += m.get('title','')
			body += '<MusicPlayer src=\"' + m.get('fileUrl','') + '\" title=\"' + trackname + '\" />\n' 
			body += extract(html2text(m.get('body', '')), entry['_id'])
		body = 'import MusicPlayer from \'$/components/Article/MusicPlayer\'\n\n' + body + '\n'

	elif entry.get('type') == 'Image':
		cover = ''
		if 'thumborId' in entry: cover = cdn + '/unsafe/1600x/' + entry['thumborId']
		if not cover and 'image' in entry:
			cover = entry['image'].get('url', '')
			if 'cloudinary' in cover: cover = ''
		images = {}
		for m in entry.get('media', []):
			t = m.get('title', '')
			if t: body += '#### ' + t + '\n'
			u = m.get('image', {}).get('url', '')
			if 'cloudinary' in u:
				u = m.get('thumborId')
				if not u: u = cover
			u = str(u)
			if u not in images.keys():
				if u.startswith('production'): u = s3 + u 
				body += '![' + m.get('title','').replace('\n', ' ') + '](' + u + ')\n' # TODO: gallery here
				images[u] = u
			body += extract(html2text(m.get('body', '')), entry['_id']) + '\n'

	if not body_orig:
		print('[prepare] using body history...')
		# print(entry.get('bodyHistory', ''))
		try: 
			for up in entry.get('bodyHistory', []):
				body_orig = up.get('text', '') or ''
				if body_orig: break
		except: pass

	# body_html = str(BeautifulSoup(body_orig, features="html.parser"))
	body += extract(html2text(body_orig), entry['_id'])
	
	# replace some topics
	for oldtopicslug, newtopicslug in retopics.items():
		body.replace(oldtopicslug, newtopicslug)
	
	return body
