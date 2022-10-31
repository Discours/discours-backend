from graphql.error import GraphQLError


class BaseHttpException(GraphQLError):
    code = 500
    message = "500 Server error"


class ExpiredToken(BaseHttpException):
    code = 403
    message = "403 Expired Token"


class InvalidToken(BaseHttpException):
    code = 403
    message = "403 Invalid Token"


class Unauthorized(BaseHttpException):
    code = 401
    message = "401 Unauthorized"


class ObjectNotExist(BaseHttpException):
    code = 404
    message = "404 Object Does Not Exist"


class OperationNotAllowed(BaseHttpException):
    code = 403
    message = "403 Operation Is Not Allowed"


class InvalidPassword(BaseHttpException):
    code = 403
    message = "403 Invalid Password"
