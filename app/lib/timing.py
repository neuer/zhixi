"""通用计时辅助函数。"""

import time


def elapsed_ms(start: float) -> int:
    """计算自 start（time.monotonic() 返回值）以来的耗时毫秒数。"""
    return int((time.monotonic() - start) * 1000)
