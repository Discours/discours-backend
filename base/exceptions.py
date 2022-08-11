from graphql import GraphQLError


class BaseHttpException(GraphQLError):
    code = 500
    message = "500 Server error"


class InvalidToken(BaseHttpException):
    code = 403
    message = "403 Invalid Token"


class ObjectNotExist(BaseHttpException):
    code = 404
    message = "404 Object Does Not Exist"


class OperationNotAllowed(BaseHttpException):
    code = 403
    message = "403 Operation is not allowed"


class InvalidPassword(BaseHttpException):
    code = 401
    message = "401 Invalid Password"
