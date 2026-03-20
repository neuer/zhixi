"""Token 估算器 — 分批处理策略的基础组件（US-020）。

根据验收标准的规则估算文本 token 数：
- 中文字符：1.5 字/token
- 非中文字符：4 字符/token
"""

import json
import math

# Prompt 模板固定开销（GLOBAL_ANALYSIS_PROMPT 去掉 {tweets_json} 后的 token 数估算）
_PROMPT_OVERHEAD_TOKENS = 600


def _is_cjk(char: str) -> bool:
    """判断字符是否为 CJK 统一汉字。"""
    cp = ord(char)
    return (
        0x4E00 <= cp <= 0x9FFF  # CJK 统一汉字
        or 0x3400 <= cp <= 0x4DBF  # CJK 扩展 A
        or 0xF900 <= cp <= 0xFAFF  # CJK 兼容
        or 0x20000 <= cp <= 0x2A6DF  # CJK 扩展 B
    )


def estimate_tokens_for_text(text: str) -> int:
    """估算文本的 token 数。

    中文字符按 1/1.5 token 计算，其他字符按 1/4 token 计算。
    结果向上取整。
    """
    if not text:
        return 0

    cjk_count = 0
    other_count = 0
    for char in text:
        if _is_cjk(char):
            cjk_count += 1
        else:
            other_count += 1

    return math.ceil(cjk_count / 1.5 + other_count / 4)


def estimate_tokens_for_tweet(serialized_tweet: dict[str, object]) -> int:
    """估算单条序列化推文的 token 数。

    将 dict 转为 JSON 字符串后调用 estimate_tokens_for_text，
    包含 JSON 格式开销（括号、引号、键名等）。
    """
    text = json.dumps(serialized_tweet, ensure_ascii=False)
    return estimate_tokens_for_text(text)


def estimate_total_tokens(serialized_tweets: list[dict[str, object]]) -> int:
    """估算推文列表的总 token 数（含 Prompt 模板开销）。

    将整个列表转为 JSON 字符串估算数据部分 token，
    加上 GLOBAL_ANALYSIS_PROMPT 模板本身的固定开销。
    """
    text = json.dumps(serialized_tweets, ensure_ascii=False)
    return estimate_tokens_for_text(text) + _PROMPT_OVERHEAD_TOKENS
