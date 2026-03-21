"""JSON 输出校验与修复 — AI 返回 JSON 的三级解析和 schema 验证（US-018）。

三级解析策略：
  1. 直接 json.loads()
  2. 清理后重试（去 markdown 包裹、提取 JSON 子串、补括号）
  3. 抛出 JsonValidationError
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# JSON Schema 类型到 Python 类型映射
_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "array": (list,),
    "object": (dict,),
    "boolean": (bool,),
}


class JsonValidationError(Exception):
    """JSON 校验失败，附带原始响应文本。"""

    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


def validate_and_fix(raw_text: str, schema: dict) -> dict:
    """三级解析 + schema 校验。

    Args:
        raw_text: AI 返回的原始文本
        schema: JSON Schema（含 required 和 properties）

    Returns:
        解析并校验通过的字典

    Raises:
        JsonValidationError: 三级解析全部失败或 schema 校验不通过
    """
    data = _parse_json(raw_text)
    _validate_schema(data, schema, raw_text)
    return data


def _parse_json(raw_text: str) -> dict:
    """三级 JSON 解析。"""
    # 第一级：直接解析
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # 第二级：清理后重试
    cleaned = _extract_json(raw_text)
    if cleaned:
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                logger.info("JSON 清理后解析成功")
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        # 尝试补全括号
        fixed = _fix_brackets(cleaned)
        if fixed != cleaned:
            try:
                data = json.loads(fixed)
                if isinstance(data, dict):
                    logger.info("JSON 补全括号后解析成功")
                    return data
            except (json.JSONDecodeError, ValueError):
                pass

    # 第三级：失败
    raise JsonValidationError(
        f"无法解析 JSON：{raw_text[:100]}...",
        raw_response=raw_text,
    )


def _extract_json(text: str) -> str:
    """从文本中提取 JSON 子串。"""
    # 去除 markdown 代码块包裹
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if md_match:
        return md_match.group(1).strip()

    # 提取第一个 { 到最后一个 } 之间的内容
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0)

    # 提取第一个 [ 到最后一个 ] 之间的内容
    bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
    if bracket_match:
        return bracket_match.group(0)

    return text.strip()


def _fix_brackets(text: str) -> str:
    """补全未闭合的括号，使用栈追踪嵌套顺序。"""
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append("}" if ch == "{" else "]")
        elif ch in ("}", "]") and stack and stack[-1] == ch:
            stack.pop()
    return text + "".join(reversed(stack))


def _validate_schema(data: dict, schema: dict, raw_text: str) -> None:
    """校验必需字段存在且类型正确。"""
    raw_required = schema.get("required", [])
    required_fields: list[str] = list(raw_required) if isinstance(raw_required, list) else []
    raw_props = schema.get("properties", {})
    properties: dict[str, dict] = raw_props if isinstance(raw_props, dict) else {}

    for field in required_fields:
        if field not in data:
            raise JsonValidationError(
                f"缺少必需字段: {field}",
                raw_response=raw_text,
            )

    for field, field_schema in properties.items():
        if field not in data or data[field] is None:
            continue

        expected_type = field_schema.get("type")
        if not isinstance(expected_type, str):
            continue

        python_types = _TYPE_MAP.get(expected_type)
        if not python_types:
            continue

        if not isinstance(data[field], python_types):
            raise JsonValidationError(
                f"字段 '{field}' 类型错误: 期望 {expected_type}，实际 {type(data[field]).__name__}",
                raw_response=raw_text,
            )
