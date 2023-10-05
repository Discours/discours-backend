from starlette.exceptions import HTTPException


# TODO: remove traceback from logs for defined exceptions


class BaseHttpException(HTTPException):
    states_code = 500
    detail = "500 Server error"


class ExpiredToken(BaseHttpException):
    states_code = 401
    detail = "401 Expired Token"


class InvalidToken(BaseHttpException):
    states_code = 401
    detail = "401 Invalid Token"


class Unauthorized(BaseHttpException):
    states_code = 401
    detail = "401 Unauthorized"


class ObjectNotExist(BaseHttpException):
    code = 404
    detail = "404 Object Does Not Exist"


class OperationNotAllowed(BaseHttpException):
    states_code = 403
    detail = "403 Operation Is Not Allowed"


class InvalidPassword(BaseHttpException):
    states_code = 403
    message = "403 Invalid Password"
