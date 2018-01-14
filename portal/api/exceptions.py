from rest_framework.exceptions import APIException


class TargetException(APIException):
    status_code = 403
    default_code = "Bad request"
    default_detail = "Somethingw went wrong"