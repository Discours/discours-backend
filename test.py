from sqlalchemy import select
from ai.preprocess import get_clear_text
from base.orm import local_session
from orm import Shout

if __name__ == "__main__":
    with local_session() as session:
        q = select(Shout)
        for [shout] in session.execute(q):
            clear_shout_body = get_clear_text(shout.body)
            print(clear_shout_body)
