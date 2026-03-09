"""
业务异常定义
"""
from typing import Any, Optional


class BusinessException(Exception):
    """
    业务异常基类
    
    示例：
        raise BusinessException("用户不存在", "USER_NOT_FOUND", status_code=422)
    """
    
    def __init__(
        self,
        message: str,
        code: str = "BUSINESS_ERROR",
        status_code: int = 400,
        data: Optional[Any] = None
    ):
        """
        初始化业务异常
        
        Args:
            message: 错误信息（必填）
            code: 业务错误码，默认 "BUSINESS_ERROR"
            status_code: HTTP 状态码，默认 400
            data: 附加数据，可选
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data
        super().__init__(self.message)

