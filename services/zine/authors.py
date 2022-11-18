from base.orm import local_session
from orm.user import User
from orm.shout import ShoutAuthor


class AuthorsStorage:
    @staticmethod
    async def get_all_authors():
        with local_session() as session:
            query = session.query(User).join(ShoutAuthor)
            result = query.all()
            return result
