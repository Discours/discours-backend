from base.orm import local_session
from migration.extract import extract_md
from migration.html2text import html2text
from orm.remark import Remark


def migrate(entry, storage):
    post_oid = entry['contentItem']
    print(post_oid)
    shout_dict = storage['shouts']['by_oid'].get(post_oid)
    remark = {
        "shout": shout_dict['id'],
        "body": extract_md(
            html2text(entry['body']),
            entry['_id']
        ),
        "desc": extract_md(
            html2text(
                entry['textAfter'] or '' + \
                entry['textBefore'] or '' + \
                entry['textSelected'] or ''
            ),
            entry["_id"]
        )
    }

    with local_session() as session:
        rmrk = Remark.create(**remark)
        session.commit()
        del rmrk["_sa_instance_state"]
        return rmrk
