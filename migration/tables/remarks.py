from base.orm import local_session
from migration.extract import extract_md
from migration.html2text import html2text
from orm.remark import Remark


def migrate(entry):
    print(entry)
    break
    remark = {
        "slug": entry["slug"],
        "oid": entry["_id"],
        "body": extract_md(html2text(
            entry['body'] + entry['textAfter'] or '' + \
            entry['textBefore'] or '' + \
            entry['textSelected'] or ''
        ), entry["_id"])
    }

    with local_session() as session:
        slug = remark["slug"]
        rmrk = session.query(Remark).filter(Remark.slug == slug).first() or Remark.create(
            **tooltip
        )
        if not rmrk:
            raise Exception("no rmrk!")
        if rmrk:
            Remark.update(rmrk, remark)
            session.commit()
    rt = tt.__dict__.copy()
    del rt["_sa_instance_state"]
    return rt
