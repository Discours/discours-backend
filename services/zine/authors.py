from base.orm import local_session
from orm.user import User
from orm.shout import ShoutAuthor
from timeit import default_timer as timer

class AuthorsStorage:
    @staticmethod
    async def get_all_authors():
        with local_session() as session:
            # start = timer()
            query = session.query(User).join(ShoutAuthor)
            # print(str(query))
            result = query.all()
            # end = timer()
            # print(end - start)
            return result
