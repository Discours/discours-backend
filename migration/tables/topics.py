from base.orm import local_session
from migration.extract import extract_md
from migration.html2text import html2text
from orm import Topic


def migrate(entry):
    body_orig = entry.get("description", "").replace("&nbsp;", " ")
    topic_dict = {
        "slug": entry["slug"],
        "oid": entry["_id"],
        "title": entry["title"].replace("&nbsp;", " "),
        "body": extract_md(html2text(body_orig)),
    }

    with local_session() as session:
        slug = topic_dict["slug"]
        topic = session.query(Topic).filter(Topic.slug == slug).first() or Topic.create(
            **topic_dict
        )
        if not topic:
            raise Exception("no topic!")
        if topic:
            if len(topic.title) > len(topic_dict["title"]):
                Topic.update(topic, {"title": topic_dict["title"]})
            if len(topic.body) < len(topic_dict["body"]):
                Topic.update(topic, {"body": topic_dict["body"]})
            session.commit()
    # print(topic.__dict__)
    rt = topic.__dict__.copy()
    del rt["_sa_instance_state"]
    return rt
