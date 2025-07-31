from graphql.error import GraphQLError

# TODO: remove traceback from logs for defined exceptions


class BaseHttpError(GraphQLError):
    code = 500
    message = "500 Server error"


class ExpiredTokenError(BaseHttpError):
    code = 401
    message = "401 Expired Token"


class InvalidTokenError(BaseHttpError):
    code = 401
    message = "401 Invalid Token"


class UnauthorizedError(BaseHttpError):
    code = 401
    message = "401 UnauthorizedError"


class ObjectNotExistError(BaseHttpError):
    code = 404
    message = "404 Object Does Not Exist"


class OperationNotAllowedError(BaseHttpError):
    code = 403
    message = "403 Operation Is Not Allowed"


class InvalidPasswordError(BaseHttpError):
    code = 403
    message = "403 Invalid Password"
