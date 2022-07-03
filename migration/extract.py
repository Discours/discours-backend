import re
import base64

TOOLTIP_REGEX = r'(\/\/\/(.+)\/\/\/)'


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
						newparts[i] = '<Tooltip text="' + extracted_part + '" link="' + link + '" />'
					else:
						newparts[i] = '<Tooltip text="%s" />' % part
					# print('[extract] tooltip: ' + newparts[i])
				else:
					# print('[extract] pass: ' + part[:10] + '..')
					newparts[i] = part
				i += 1
			
	return ''.join(newparts)

IMG_REGEX = r"\!\[(.*?)\]\((data\:image\/(png|jpeg|jpg);base64\,((?:[A-Za-z\d+\/]{4})*(?:[A-Za-z\d+\/]{3}=|[A-Za-z\d+\/]{2}==)))\)"
public = '../discoursio-web/public'
cdn = 'https://assets.discours.io'
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
	print()
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
				# print('[extract_images] have next')
				for mime in IMAGES.keys():
					if mime in current[-15:]:
						# print('[extract_images] found proper mime type')
						print('[extract] ' + current[-15:])
						if ')' in next: 
							b64encoded = next.split(')')[0]
						print('[extract] '+str(i+1)+': %d bytes' % len(b64encoded))
						# print(meta)
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
							print('[extract] not b64encoded')
							print(current[-15:])
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