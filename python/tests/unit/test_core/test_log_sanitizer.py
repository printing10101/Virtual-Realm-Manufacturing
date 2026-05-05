import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.log_sanitizer import LogSanitizer


class TestProcessParameterSanitization:
    def test_sanitize_cutting_speed_by_key(self):
        sanitizer = LogSanitizer()
        data = {"cutting_speed": 1200}
        result = sanitizer.sanitize(data)
        assert result["cutting_speed"] == "[工艺参数已脱敏]"

    def test_sanitize_feed_rate_by_key(self):
        sanitizer = LogSanitizer()
        data = {"feed_rate": 0.25}
        result = sanitizer.sanitize(data)
        assert result["feed_rate"] == "[工艺参数已脱敏]"

    def test_sanitize_spindle_speed_by_key(self):
        sanitizer = LogSanitizer()
        data = {"spindle_speed": 3000}
        result = sanitizer.sanitize(data)
        assert result["spindle_speed"] == "[工艺参数已脱敏]"

    def test_sanitize_depth_of_cut_by_key(self):
        sanitizer = LogSanitizer()
        data = {"depth_of_cut": 2.5}
        result = sanitizer.sanitize(data)
        assert result["depth_of_cut"] == "[工艺参数已脱敏]"

    def test_sanitize_process_param_dict(self):
        sanitizer = LogSanitizer()
        data = {
            "cutting_speed": {
                "v_c": 150.0,
                "unit": "m/min",
                "material": "45钢"
            }
        }
        result = sanitizer.sanitize(data)
        assert result["cutting_speed"]["v_c"] == "[工艺参数已脱敏]"
        assert result["cutting_speed"]["unit"] == "m/min"
        assert result["cutting_speed"]["material"] == "45钢"

    def test_sanitize_chinese_pattern_cutting_speed(self):
        sanitizer = LogSanitizer()
        text = "切削速度: 1200rpm"
        result = sanitizer.sanitize(text)
        assert "1200" not in result
        assert "切削速度" in result
        assert "[工艺参数已脱敏]" in result

    def test_sanitize_chinese_pattern_feed_rate(self):
        sanitizer = LogSanitizer()
        text = "进给量: 0.25mm/rev"
        result = sanitizer.sanitize(text)
        assert "0.25" not in result
        assert "[工艺参数已脱敏]" in result

    def test_sanitize_english_pattern_cutting_speed(self):
        sanitizer = LogSanitizer()
        text = "cutting speed: 150 m/min"
        result = sanitizer.sanitize(text)
        assert "150" not in result
        assert "[工艺参数已脱敏]" in result


class TestFileContentSanitization:
    def test_sanitize_file_content_string(self):
        sanitizer = LogSanitizer()
        data = {"file_content": "CAD design content here"}
        result = sanitizer.sanitize(data)
        assert result["file_content"] == "[文件内容已脱敏 - 长度: 23字符]"

    def test_sanitize_cad_content(self):
        sanitizer = LogSanitizer()
        data = {"cad_content": "Some CAD data"}
        result = sanitizer.sanitize(data)
        assert "Some CAD data" not in result["cad_content"]
        assert "[文件内容已脱敏" in result["cad_content"]

    def test_sanitize_nc_code(self):
        sanitizer = LogSanitizer()
        data = {"nc_code": "G01 X100 Y200"}
        result = sanitizer.sanitize(data)
        assert "G01" not in result["nc_code"]
        assert "[文件内容已脱敏" in result["nc_code"]

    def test_sanitize_file_content_with_dict_metadata(self):
        sanitizer = LogSanitizer()
        data = {
            "file_content": {
                "type": "CAD",
                "size": "2.5MB",
                "format": "STEP"
            }
        }
        result = sanitizer.sanitize(data)
        assert "CAD" in result["file_content"]
        assert "2.5MB" in result["file_content"]
        assert "STEP" in result["file_content"]


class TestUserInputSanitization:
    def test_sanitize_short_description(self):
        sanitizer = LogSanitizer()
        data = {"description": "Short note"}
        result = sanitizer.sanitize(data)
        assert result["description"] == "Short note"

    def test_sanitize_long_description(self):
        sanitizer = LogSanitizer()
        long_text = "A" * 100
        data = {"description": long_text}
        result = sanitizer.sanitize(data)
        assert len(result["description"]) == 53
        assert result["description"] == "A" * 50 + "..."

    def test_sanitize_exactly_50_chars(self):
        sanitizer = LogSanitizer()
        text = "A" * 50
        data = {"description": text}
        result = sanitizer.sanitize(data)
        assert result["description"] == text

    def test_sanitize_51_chars(self):
        sanitizer = LogSanitizer()
        text = "A" * 51
        data = {"description": text}
        result = sanitizer.sanitize(data)
        assert result["description"] == "A" * 50 + "..."

    def test_sanitize_comment_field(self):
        sanitizer = LogSanitizer()
        data = {"comment": "This is a very long comment that exceeds the limit of fifty characters"}
        result = sanitizer.sanitize(data)
        assert result["comment"] == "This is a very long comment that exceeds the limit..."


class TestAPIKeySanitization:
    def test_sanitize_api_key(self):
        sanitizer = LogSanitizer()
        data = {"api_key": "sk_abcdefghijklmnop1234"}
        result = sanitizer.sanitize(data)
        assert result["api_key"] == "[已脱敏]1234"

    def test_sanitize_token(self):
        sanitizer = LogSanitizer()
        data = {"token": "abc123xyz789mnop"}
        result = sanitizer.sanitize(data)
        assert result["token"] == "[已脱敏]mnop"

    def test_sanitize_short_key(self):
        sanitizer = LogSanitizer()
        data = {"api_key": "abc"}
        result = sanitizer.sanitize(data)
        assert result["api_key"] == "[已脱敏]"

    def test_sanitize_bearer_token_pattern(self):
        sanitizer = LogSanitizer()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret"
        result = sanitizer.sanitize(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret" not in result
        assert "[已脱敏]" in result

    def test_sanitize_sk_key_pattern(self):
        sanitizer = LogSanitizer()
        text = "API Key: sk_abcdef1234567890abcdef1234567890"
        result = sanitizer.sanitize(text)
        assert "abcdef1234567890abcdef1234567890" not in result
        assert "[已脱敏]" in result


class TestNestedDataStructure:
    def test_sanitize_nested_dict(self):
        sanitizer = LogSanitizer()
        data = {
            "workflow": {
                "params": {
                    "cutting_speed": 1200,
                    "description": "Normal workflow"
                }
            }
        }
        result = sanitizer.sanitize(data)
        assert result["workflow"]["params"]["cutting_speed"] == "[工艺参数已脱敏]"
        assert result["workflow"]["params"]["description"] == "Normal workflow"

    def test_sanitize_list_in_dict(self):
        sanitizer = LogSanitizer()
        data = {
            "items": [
                {"api_key": "secret1234"},
                {"description": "Short"}
            ]
        }
        result = sanitizer.sanitize(data)
        assert result["items"][0]["api_key"] == "[已脱敏]1234"
        assert result["items"][1]["description"] == "Short"


class TestNonSensitiveData:
    def test_preserve_normal_data(self):
        sanitizer = LogSanitizer()
        data = {
            "task_id": "task_123",
            "status": "completed",
            "count": 42,
            "name": "Test Task"
        }
        result = sanitizer.sanitize(data)
        assert result == data

    def test_preserve_normal_string(self):
        sanitizer = LogSanitizer()
        text = "This is a normal log message without sensitive data"
        result = sanitizer.sanitize(text)
        assert result == text


class TestSpecialCharacters:
    def test_sanitize_with_special_chars(self):
        sanitizer = LogSanitizer()
        data = {"description": "Test\nwith\tnewlines and <special> chars"}
        result = sanitizer.sanitize(data)
        assert result["description"] == "Test\nwith\tnewlines and <special> chars"

    def test_sanitize_unicode(self):
        sanitizer = LogSanitizer()
        data = {"description": "中文描述测试"}
        result = sanitizer.sanitize(data)
        assert result["description"] == "中文描述测试"
