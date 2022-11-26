import base64
import os
import re
import uuid

from bs4 import BeautifulSoup


TOOLTIP_REGEX = r"(\/\/\/(.+)\/\/\/)"
contentDir = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "..", "..", "discoursio-web", "content"
)
s3 = "https://discours-io.s3.amazonaws.com/"
cdn = "https://assets.discours.io"


def replace_tooltips(body):
    # change if you prefer regexp
    newbody = body
    matches = list(re.finditer(TOOLTIP_REGEX, body, re.IGNORECASE | re.MULTILINE))[1:]
    for match in matches:
        newbody = body.replace(
            match.group(1), '<Tooltip text="' + match.group(2) + '" />'
        )  # NOTE: doesn't work
    if len(matches) > 0:
        print("[extract] found %d tooltips" % len(matches))
    return newbody


def place_tooltips(body):
    parts = body.split("&&&")
    lll = len(parts)
    newparts = list(parts)
    placed = False
    if lll & 1:
        if lll > 1:
            i = 1
            print("[extract] found %d tooltips" % (lll - 1))
            for part in parts[1:]:
                if i & 1:
                    placed = True
                    if 'a class="footnote-url" href=' in part:
                        print("[extract] footnote: " + part)
                        fn = 'a class="footnote-url" href="'
                        link = part.split(fn, 1)[1].split('"', 1)[0]
                        extracted_part = (
                            part.split(fn, 1)[0] + " " + part.split("/", 1)[-1]
                        )
                        newparts[i] = (
                            "<Tooltip"
                            + (' link="' + link + '" ' if link else "")
                            + ">"
                            + extracted_part
                            + "</Tooltip>"
                        )
                    else:
                        newparts[i] = "<Tooltip>%s</Tooltip>" % part
                        # print('[extract] ' + newparts[i])
                else:
                    # print('[extract] ' + part[:10] + '..')
                    newparts[i] = part
                i += 1
    return ("".join(newparts), placed)


IMG_REGEX = r"\!\[(.*?)\]\((data\:image\/(png|jpeg|jpg);base64\,((?:[A-Za-z\d+\/]{4})*(?:[A-Za-z\d+\/]{3}="
IMG_REGEX += r"|[A-Za-z\d+\/]{2}==)))\)"

parentDir = "/".join(os.getcwd().split("/")[:-1])
public = parentDir + "/discoursio-web/public"
cache = {}


def reextract_images(body, oid):
    # change if you prefer regexp
    matches = list(re.finditer(IMG_REGEX, body, re.IGNORECASE | re.MULTILINE))[1:]
    i = 0
    for match in matches:
        print("[extract] image " + match.group(1))
        ext = match.group(3)
        name = oid + str(i)
        link = public + "/upload/image-" + name + "." + ext
        img = match.group(4)
        title = match.group(1)  # NOTE: this is not the title
        if img not in cache:
            content = base64.b64decode(img + "==")
            print(str(len(img)) + " image bytes been written")
            open("../" + link, "wb").write(content)
            cache[img] = name
            i += 1
        else:
            print("[extract] image cached " + cache[img])
        body.replace(
            str(match), "![" + title + "](" + cdn + link + ")"
        )  # WARNING: this does not work
    return body


IMAGES = {
    "data:image/png": "png",
    "data:image/jpg": "jpg",
    "data:image/jpeg": "jpg",
}

b64 = ";base64,"


def extract_imageparts(bodyparts, prefix):
    # recursive loop
    newparts = list(bodyparts)
    for current in bodyparts:
        i = bodyparts.index(current)
        for mime in IMAGES.keys():
            if mime == current[-len(mime) :] and (i + 1 < len(bodyparts)):
                print("[extract] " + mime)
                next = bodyparts[i + 1]
                ext = IMAGES[mime]
                b64end = next.index(")")
                b64encoded = next[:b64end]
                name = prefix + "-" + str(len(cache))
                link = "/upload/image-" + name + "." + ext
                print("[extract] name: " + name)
                print("[extract] link: " + link)
                print("[extract] %d bytes" % len(b64encoded))
                if b64encoded not in cache:
                    try:
                        content = base64.b64decode(b64encoded + "==")
                        open(public + link, "wb").write(content)
                        print(
                            "[extract] "
                            + str(len(content))
                            + " image bytes been written"
                        )
                        cache[b64encoded] = name
                    except Exception:
                        raise Exception
                        # raise Exception('[extract] error decoding image %r' %b64encoded)
                else:
                    print("[extract] cached link " + cache[b64encoded])
                    name = cache[b64encoded]
                    link = cdn + "/upload/image-" + name + "." + ext
                newparts[i] = (
                    current[: -len(mime)]
                    + current[-len(mime) :]
                    + link
                    + next[-b64end:]
                )
                newparts[i + 1] = next[:-b64end]
                break
    return (
        extract_imageparts(
            newparts[i] + newparts[i + 1] + b64.join(bodyparts[(i + 2) :]), prefix
        )
        if len(bodyparts) > (i + 1)
        else "".join(newparts)
    )


def extract_dataimages(parts, prefix):
    newparts = list(parts)
    for part in parts:
        i = parts.index(part)
        if part.endswith("]("):
            [ext, rest] = parts[i + 1].split(b64)
            name = prefix + "-" + str(len(cache))
            if ext == "/jpeg":
                ext = "jpg"
            else:
                ext = ext.replace("/", "")
            link = "/upload/image-" + name + "." + ext
            print("[extract] filename: " + link)
            b64end = rest.find(")")
            if b64end != -1:
                b64encoded = rest[:b64end]
                print("[extract] %d text bytes" % len(b64encoded))
                # write if not cached
                if b64encoded not in cache:
                    try:
                        content = base64.b64decode(b64encoded + "==")
                        open(public + link, "wb").write(content)
                        print("[extract] " + str(len(content)) + " image bytes")
                        cache[b64encoded] = name
                    except Exception:
                        raise Exception
                        # raise Exception('[extract] error decoding image %r' %b64encoded)
                else:
                    print("[extract] 0 image bytes, cached for " + cache[b64encoded])
                    name = cache[b64encoded]

                # update link with CDN
                link = cdn + "/upload/image-" + name + "." + ext

                # patch newparts
                newparts[i + 1] = link + rest[b64end:]
            else:
                raise Exception("cannot find the end of base64 encoded string")
        else:
            print("[extract] dataimage skipping part " + str(i))
            continue
    return "".join(newparts)


di = "data:image"


def extract_md_images(body, oid):
    newbody = ""
    body = (
        body.replace("\n! [](" + di, "\n ![](" + di)
        .replace("\n[](" + di, "\n![](" + di)
        .replace(" [](" + di, " ![](" + di)
    )
    parts = body.split(di)
    if len(parts) > 1:
        newbody = extract_dataimages(parts, oid)
    else:
        newbody = body
    return newbody


def cleanup(body):
    newbody = (
        body.replace("<", "")
        .replace(">", "")
        .replace("{", "(")
        .replace("}", ")")
        .replace("…", "...")
        .replace(" __ ", " ")
        .replace("_ _", " ")
        .replace("****", "")
        .replace("\u00a0", " ")
        .replace("\u02c6", "^")
        .replace("\u00a0", " ")
        .replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\u200c", "")
    )  # .replace('\u2212', '-')
    return newbody


def extract_md(body, oid=""):
    newbody = body
    if newbody:
        uid = oid or uuid.uuid4()
        newbody = extract_md_images(newbody, uid)
        if not newbody:
            raise Exception("extract_images error")

        newbody = cleanup(newbody)
        if not newbody:
            raise Exception("cleanup error")

        newbody, placed = place_tooltips(newbody)
        if not newbody:
            raise Exception("place_tooltips error")

        if placed:
            newbody = "import Tooltip from '$/components/Article/Tooltip'\n\n" + newbody
    return newbody


def extract_media(entry):
    ''' normalized media extraction method '''
    # media [ { title pic url body } ]}
    kind = entry.get("layout")
    media = []
    for m in entry.get("media", []):
        # title
        title = m.get("title", "").replace("\n", " ").replace("&nbsp;", " ")
        artist = m.get("performer") or m.get("artist")
        if artist:
            title = artist + " - " + title

        # pic
        url = m.get("fileUrl") or m.get("url", "")
        pic = ""
        if "thumborId" in m:
            pic = cdn + "/unsafe/1600x/" + m["thumborId"]

        # url
        if not url:
            if kind == "Image":
                url = pic
            elif "youtubeId" in m:
                url = "https://youtube.com/?watch=" + m["youtubeId"]
            elif "vimeoId" in m:
                url = "https://vimeo.com/" + m["vimeoId"]
            else:
                print("[extract] media is not supported")
        # body
        body = m.get("body") or m.get("literatureBody")

        media.append({
            "url": url,
            "pic": pic,
            "title": title,
            "body": body
        })
    return media


def prepare_html_body(entry):
    # body modifications
    body = ""
    kind = entry.get("type")
    addon = ""
    if kind == "Video":
        addon = ""
        for m in entry.get("media", []):
            if "youtubeId" in m:
                addon += '<iframe width="420" height="345" src="http://www.youtube.com/embed/'
                addon += m["youtubeId"]
                addon += '?autoplay=1" frameborder="0" allowfullscreen></iframe>\n'
            elif "vimeoId" in m:
                addon += '<iframe src="https://player.vimeo.com/video/'
                addon += m["vimeoId"]
                addon += ' width="420" height="345" frameborder="0" allow="autoplay; fullscreen"'
                addon += " allowfullscreen></iframe>"
            else:
                print("[extract] media is not supported")
                print(m)
        body += addon

    elif kind == "Music":
        addon = ""
        for m in entry.get("media", []):
            artist = m.get("performer")
            trackname = ""
            if artist:
                trackname += artist + " - "
            if "title" in m:
                trackname += m.get("title", "")
            addon += "<figure><figcaption>"
            addon += trackname
            addon += '</figcaption><audio controls src="'
            addon += m.get("fileUrl", "")
            addon += '"></audio></figure>'
        body += addon

    body = extract_html(entry)
    # if body_orig: body += extract_md(html2text(body_orig), entry['_id'])
    if not body:
        print("[extract] empty HTML body")
    return body


def extract_html(entry):
    body_orig = (entry.get("body") or "").replace('\(', '(').replace('\)', ')')
    if not body_orig:
        print("[extract] empty HTML body")
    body_html = str(BeautifulSoup(body_orig, features="html.parser"))
    return body_html
