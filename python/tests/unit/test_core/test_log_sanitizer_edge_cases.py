import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.log_sanitizer import LogSanitizer


class TestExtremeLengthInputs:
    def test_very_long_description(self):
        sanitizer = LogSanitizer()
        text = "A" * 10000
        data = {"description": text}
        result = sanitizer.sanitize(data)
        assert len(result["description"]) == 53
        assert result["description"].endswith("...")

    def test_very_long_api_key(self):
        sanitizer = LogSanitizer()
        text = "sk_" + "a" * 1000
        data = {"api_key": text}
        result = sanitizer.sanitize(data)
        assert result["api_key"].startswith("[已脱敏]")
        assert len(result["api_key"]) <= 20

    def test_empty_string(self):
        sanitizer = LogSanitizer()
        data = {"description": ""}
        result = sanitizer.sanitize(data)
        assert result["description"] == ""

    def test_none_value(self):
        sanitizer = LogSanitizer()
        data = {"description": None}
        result = sanitizer.sanitize(data)
        assert result["description"] is None


class TestSpecialCharacters:
    def test_newlines_and_tabs(self):
        sanitizer = LogSanitizer()
        text = "Line1\nLine2\tLine3\r\nLine4"
        data = {"description": text}
        result = sanitizer.sanitize(data)
        assert "Line1" in result["description"]

    def test_unicode_characters(self):
        sanitizer = LogSanitizer()
        text = "中文描述测试日本語テスト"
        data = {"description": text}
        result = sanitizer.sanitize(data)
        assert result["description"] == text

    def test_emoji_in_description(self):
        sanitizer = LogSanitizer()
        text = "Test description with emoji 🎉🚀"
        data = {"description": text}
        result = sanitizer.sanitize(data)
        assert result["description"] == text

    def test_html_content(self):
        sanitizer = LogSanitizer()
        text = "<div>Some HTML content</div>"
        data = {"description": text}
        result = sanitizer.sanitize(data)
        assert result["description"] == text

    def test_json_string(self):
        sanitizer = LogSanitizer()
        text = '{"key": "value", "nested": {"a": 1}}'
        data = {"description": text}
        result = sanitizer.sanitize(data)
        assert result["description"] == text


class TestNestedDataStructures:
    def test_deeply_nested_dict(self):
        sanitizer = LogSanitizer()
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "api_key": "secret1234",
                        "normal": "value"
                    }
                }
            }
        }
        result = sanitizer.sanitize(data)
        assert result["level1"]["level2"]["level3"]["api_key"] == "[已脱敏]1234"
        assert result["level1"]["level2"]["level3"]["normal"] == "value"

    def test_mixed_list_types(self):
        sanitizer = LogSanitizer()
        data = {
            "items": [
                "string",
                123,
                {"api_key": "secret1234"},
                ["nested", {"cutting_speed": 1200}]
            ]
        }
        result = sanitizer.sanitize(data)
        assert result["items"][0] == "string"
        assert result["items"][1] == 123
        assert result["items"][2]["api_key"] == "[已脱敏]1234"
        assert result["items"][3][1]["cutting_speed"] == "[工艺参数已脱敏]"

    def test_empty_dict_and_list(self):
        sanitizer = LogSanitizer()
        data = {"empty_dict": {}, "empty_list": []}
        result = sanitizer.sanitize(data)
        assert result == data


class TestMultipleSensitivePatterns:
    def test_multiple_api_keys_in_text(self):
        sanitizer = LogSanitizer()
        text = "Key1: sk_abcdef1234567890, Key2: sk_xyz789abcdef1234567890"
        result = sanitizer.sanitize(text)
        assert "sk_abcdef1234567890" not in result
        assert "sk_xyz789abcdef1234567890" not in result
        assert result.count("[已脱敏]") >= 2

    def test_mixed_sensitive_data(self):
        sanitizer = LogSanitizer()
        data = {
            "cutting_speed": 1200,
            "api_key": "sk_secret1234567890abcdef",
            "description": "A" * 100,
            "file_content": "CAD content here",
            "normal_field": "normal_value"
        }
        result = sanitizer.sanitize(data)

        assert result["cutting_speed"] == "[工艺参数已脱敏]"
        assert "sk_secret1234567890abcdef" not in result["api_key"]
        assert result["description"] == "A" * 50 + "..."
        assert "CAD content here" not in result["file_content"]
        assert result["normal_field"] == "normal_value"

    def test_process_params_in_text_with_numbers(self):
        sanitizer = LogSanitizer()
        text = "切削速度: 1200rpm, 进给量: 0.25mm/rev, 主轴转速: 3000rpm"
        result = sanitizer.sanitize(text)
        assert "1200" not in result
        assert "0.25" not in result
        assert "3000" not in result
        assert result.count("[工艺参数已脱敏]") == 3


class TestDataTypePreservation:
    def test_integer_preserved(self):
        sanitizer = LogSanitizer()
        data = {"count": 42, "id": 123}
        result = sanitizer.sanitize(data)
        assert result["count"] == 42
        assert isinstance(result["count"], int)

    def test_float_preserved(self):
        sanitizer = LogSanitizer()
        data = {"ratio": 3.14, "percentage": 0.75}
        result = sanitizer.sanitize(data)
        assert result["ratio"] == 3.14
        assert isinstance(result["ratio"], float)

    def test_boolean_preserved(self):
        sanitizer = LogSanitizer()
        data = {"active": True, "deleted": False}
        result = sanitizer.sanitize(data)
        assert result["active"] is True
        assert result["deleted"] is False

    def test_string_preserved_when_not_sensitive(self):
        sanitizer = LogSanitizer()
        data = {"name": "John", "email": "john@example.com"}
        result = sanitizer.sanitize(data)
        assert result["name"] == "John"
        assert result["email"] == "john@example.com"


class TestEdgeCases:
    def test_single_character_api_key(self):
        sanitizer = LogSanitizer()
        data = {"api_key": "a"}
        result = sanitizer.sanitize(data)
        assert result["api_key"] == "[已脱敏]"

    def test_exactly_4_character_api_key(self):
        sanitizer = LogSanitizer()
        data = {"api_key": "abcd"}
        result = sanitizer.sanitize(data)
        assert result["api_key"] == "[已脱敏]"

    def test_exactly_5_character_api_key(self):
        sanitizer = LogSanitizer()
        data = {"api_key": "abcde"}
        result = sanitizer.sanitize(data)
        assert result["api_key"] == "[已脱敏]bcde"

    def test_process_param_with_zero_value(self):
        sanitizer = LogSanitizer()
        data = {"cutting_speed": 0}
        result = sanitizer.sanitize(data)
        assert result["cutting_speed"] == "[工艺参数已脱敏]"

    def test_process_param_with_negative_value(self):
        sanitizer = LogSanitizer()
        data = {"depth_of_cut": -1.5}
        result = sanitizer.sanitize(data)
        assert result["depth_of_cut"] == "[工艺参数已脱敏]"

    def test_custom_object_fallback(self):
        sanitizer = LogSanitizer()

        class CustomObject:
            def __str__(self):
                return "custom_object"

        data = {"custom": CustomObject()}
        result = sanitizer.sanitize(data)
        assert result["custom"] == "custom_object"
