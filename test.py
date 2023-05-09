from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ai.preprocess import get_clear_text
from base.orm import local_session
from orm import Shout, Topic

if __name__ == "__main__":
    with local_session() as session:
        q = select(Shout).options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        ).where(
            Shout.deletedAt.is_(None)
        )

        for [shout] in session.execute(q).unique():
            print(shout.topics)
            # clear_shout_body = get_clear_text(shout.body)
            # print(clear_shout_body)
            #

        topics_q = select(Topic)
        for [topic] in session.execute(topics_q):
            print(topic.body)

