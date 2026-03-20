"""JSON 输出校验与修复测试（US-018 + US-048）。"""

import pytest

from app.processor.json_validator import JsonValidationError, validate_and_fix

SIMPLE_SCHEMA = {
    "required": ["title", "translation", "comment"],
    "properties": {
        "title": {"type": "string"},
        "translation": {"type": "string"},
        "comment": {"type": "string"},
    },
}

NESTED_SCHEMA = {
    "required": ["filtered_ids", "topics"],
    "properties": {
        "filtered_ids": {"type": "array", "items": {"type": "string"}},
        "topics": {"type": "array"},
    },
}

NUMERIC_SCHEMA = {
    "required": ["score", "count"],
    "properties": {
        "score": {"type": "number"},
        "count": {"type": "integer"},
    },
}


class TestValidJSON:
    """第一级：直接 json.loads 成功。"""

    def test_normal_json(self):
        raw = '{"title": "测试标题", "translation": "翻译", "comment": "点评"}'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert result["title"] == "测试标题"
        assert result["translation"] == "翻译"
        assert result["comment"] == "点评"

    def test_nested_json(self):
        raw = '{"filtered_ids": ["id1", "id2"], "topics": [{"type": "single"}]}'
        result = validate_and_fix(raw, NESTED_SCHEMA)
        assert len(result["filtered_ids"]) == 2
        assert len(result["topics"]) == 1

    def test_numeric_types(self):
        raw = '{"score": 85.5, "count": 10}'
        result = validate_and_fix(raw, NUMERIC_SCHEMA)
        assert result["score"] == 85.5
        assert result["count"] == 10


class TestMarkdownWrapped:
    """第二级：去除 markdown 包裹。"""

    def test_json_code_block(self):
        raw = '```json\n{"title": "标题", "translation": "翻译", "comment": "点评"}\n```'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert result["title"] == "标题"

    def test_code_block_no_lang(self):
        raw = '```\n{"title": "标题", "translation": "翻译", "comment": "点评"}\n```'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert result["title"] == "标题"


class TestExtraText:
    """第二级：去除前后多余文字。"""

    def test_prefix_text(self):
        raw = 'Here is the result:\n{"title": "标题", "translation": "翻译", "comment": "点评"}'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert result["title"] == "标题"

    def test_suffix_text(self):
        raw = '{"title": "标题", "translation": "翻译", "comment": "点评"}\nHope this helps!'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert result["title"] == "标题"

    def test_both_prefix_and_suffix(self):
        raw = 'Output:\n{"title": "标题", "translation": "翻译", "comment": "点评"}\nDone.'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert result["title"] == "标题"


class TestMissingBracket:
    """第二级：补全缺失括号。"""

    def test_missing_closing_brace(self):
        raw = '{"title": "标题", "translation": "翻译", "comment": "点评"'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert result["title"] == "标题"

    def test_missing_closing_bracket(self):
        raw = '{"filtered_ids": ["id1", "id2"], "topics": [{"type": "single"}]'
        result = validate_and_fix(raw, NESTED_SCHEMA)
        assert result["filtered_ids"] == ["id1", "id2"]


class TestSchemaValidation:
    """schema 校验：字段缺失和类型错误。"""

    def test_missing_required_field(self):
        raw = '{"title": "标题", "translation": "翻译"}'
        with pytest.raises(JsonValidationError) as exc_info:
            validate_and_fix(raw, SIMPLE_SCHEMA)
        assert "comment" in str(exc_info.value)

    def test_wrong_type_string_expected(self):
        raw = '{"title": 123, "translation": "翻译", "comment": "点评"}'
        with pytest.raises(JsonValidationError):
            validate_and_fix(raw, SIMPLE_SCHEMA)

    def test_wrong_type_array_expected(self):
        raw = '{"filtered_ids": "not_array", "topics": []}'
        with pytest.raises(JsonValidationError):
            validate_and_fix(raw, NESTED_SCHEMA)

    def test_wrong_type_number_expected(self):
        raw = '{"score": "not_number", "count": 10}'
        with pytest.raises(JsonValidationError):
            validate_and_fix(raw, NUMERIC_SCHEMA)

    def test_integer_accepts_int(self):
        """integer 类型接受 int 值。"""
        raw = '{"score": 85, "count": 10}'
        result = validate_and_fix(raw, NUMERIC_SCHEMA)
        assert result["count"] == 10


class TestInvalidInput:
    """第三级：完全无效输入。"""

    def test_completely_invalid(self):
        with pytest.raises(JsonValidationError) as exc_info:
            validate_and_fix("This is not JSON at all", SIMPLE_SCHEMA)
        assert exc_info.value.raw_response == "This is not JSON at all"

    def test_empty_string(self):
        with pytest.raises(JsonValidationError):
            validate_and_fix("", SIMPLE_SCHEMA)

    def test_partial_json_unrecoverable(self):
        with pytest.raises(JsonValidationError):
            validate_and_fix('{"title": "标题", "trans', SIMPLE_SCHEMA)


class TestEdgeCases:
    """边界情况。"""

    def test_extra_fields_allowed(self):
        """schema 之外的字段不影响校验。"""
        raw = '{"title": "标题", "translation": "翻译", "comment": "点评", "extra": 123}'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert result["extra"] == 123

    def test_null_value_for_optional(self):
        """schema 中未标 required 的字段为 null 不影响。"""
        schema = {
            "required": ["title"],
            "properties": {
                "title": {"type": "string"},
                "reason": {"type": "string"},
            },
        }
        raw = '{"title": "标题", "reason": null}'
        result = validate_and_fix(raw, schema)
        assert result["reason"] is None

    def test_unicode_content(self):
        raw = '{"title": "🔥 AI热点", "translation": "翻译内容", "comment": "点评"}'
        result = validate_and_fix(raw, SIMPLE_SCHEMA)
        assert "🔥" in result["title"]
