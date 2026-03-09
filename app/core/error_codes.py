"""
统一错误码定义
"""
from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    VALIDATION_ERROR = 422
    INTERNAL_SERVER_ERROR = 500
    
    BUSINESS_ERROR = 1000
    USER_NOT_FOUND = 1001
    USER_ALREADY_EXISTS = 1002
    INVALID_CREDENTIALS = 1003
    CAPTCHA_EXPIRED = 1004
    CAPTCHA_INVALID = 1005
    EMAIL_CODE_EXPIRED = 1006
    EMAIL_CODE_INVALID = 1007
    TEMP_TOKEN_INVALID = 1008
    FILE_NOT_FOUND = 1009
    CONVERSATION_NOT_FOUND = 1010
    CONVERSATION_ARCHIVED = 1011
    PERMISSION_DENIED = 1012


def get_error_code_by_string(code_str: str) -> int:
    """
    将字符串错误码转换为数字错误码
    
    Args:
        code_str: 字符串错误码，如 "HTTP_404", "VALIDATION_ERROR"
        
    Returns:
        对应的数字错误码，如果找不到则返回 BUSINESS_ERROR
    """
    if code_str.startswith("HTTP_"):
        try:
            status_code = int(code_str.replace("HTTP_", ""))
            return status_code
        except ValueError:
            pass
    
    code_mapping = {
        "VALIDATION_ERROR": ErrorCode.VALIDATION_ERROR,
        "INTERNAL_SERVER_ERROR": ErrorCode.INTERNAL_SERVER_ERROR,
        "BUSINESS_ERROR": ErrorCode.BUSINESS_ERROR,
        "USER_NOT_FOUND": ErrorCode.USER_NOT_FOUND,
        "USER_ALREADY_EXISTS": ErrorCode.USER_ALREADY_EXISTS,
        "INVALID_CREDENTIALS": ErrorCode.INVALID_CREDENTIALS,
        "CAPTCHA_EXPIRED": ErrorCode.CAPTCHA_EXPIRED,
        "CAPTCHA_INVALID": ErrorCode.CAPTCHA_INVALID,
        "EMAIL_CODE_EXPIRED": ErrorCode.EMAIL_CODE_EXPIRED,
        "EMAIL_CODE_INVALID": ErrorCode.EMAIL_CODE_INVALID,
        "TEMP_TOKEN_INVALID": ErrorCode.TEMP_TOKEN_INVALID,
        "FILE_NOT_FOUND": ErrorCode.FILE_NOT_FOUND,
        "CONVERSATION_NOT_FOUND": ErrorCode.CONVERSATION_NOT_FOUND,
        "CONVERSATION_ARCHIVED": ErrorCode.CONVERSATION_ARCHIVED,
        "PERMISSION_DENIED": ErrorCode.PERMISSION_DENIED,
    }
    
    return code_mapping.get(code_str, ErrorCode.BUSINESS_ERROR)

