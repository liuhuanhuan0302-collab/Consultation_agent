"""后台路由共用的限流器与工具函数。"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def escape_csv_cell(value: object | None) -> object | None:
    """将可能被 Excel 解释为公式的客户输入强制导出为文本。"""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value
