"""
Тесты для покрытия модуля utils
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import re
from datetime import datetime

# Импортируем модули utils для покрытия
import utils.logger
import utils.diff
import utils.encoders
import utils.extract_text
import utils.generate_slug


class TestUtilsLogger:
    """Тесты для utils.logger"""

    def test_logger_import(self):
        """Тест импорта логгера"""
        from utils.logger import root_logger
        assert root_logger is not None

    def test_logger_configuration(self):
        """Тест конфигурации логгера"""
        from utils.logger import root_logger
        assert hasattr(root_logger, 'handlers')
        assert hasattr(root_logger, 'level')


class TestUtilsDiff:
    """Тесты для utils.diff"""

    def test_diff_import(self):
        """Тест импорта diff"""
        from utils.diff import get_diff, apply_diff
        assert get_diff is not None
        assert apply_diff is not None

    def test_get_diff_same_texts(self):
        """Тест get_diff для одинаковых текстов"""
        from utils.diff import get_diff
        result = get_diff("  hello   world", "  hello   world")
        assert len(result) == 0  # Для идентичных текстов разницы нет

    def test_get_diff_different_texts(self):
        """Тест get_diff с разными текстами"""
        from utils.diff import get_diff
        original = "hello world"
        modified = "hello new world"
        result = get_diff(original, modified)
        assert len(result) > 0
        assert any(line.startswith('+') for line in result)

    def test_get_diff_empty_texts(self):
        """Тест get_diff с пустыми текстами"""
        from utils.diff import get_diff
        result = get_diff("", "")
        assert result == []

    def test_apply_diff(self):
        """Тест apply_diff"""
        from utils.diff import apply_diff
        original = "hello world"
        diff = ["  hello", "+ new", "  world"]
        result = apply_diff(original, diff)
        assert "new" in result


class TestUtilsEncoders:
    """Тесты для utils.encoders"""

    def test_encoders_import(self):
        """Тест импорта encoders"""
        from utils.encoders import default_json_encoder, orjson_dumps, orjson_loads
        assert default_json_encoder is not None
        assert orjson_dumps is not None
        assert orjson_loads is not None

    def test_default_json_encoder_datetime(self):
        """Тест default_json_encoder с datetime"""
        from utils.encoders import default_json_encoder
        dt = datetime(2023, 1, 1, 12, 0, 0)
        result = default_json_encoder(dt)
        assert isinstance(result, str)
        assert "2023-01-01T12:00:00" in result

    def test_default_json_encoder_unknown_type(self):
        """Тест default_json_encoder с несериализуемым типом"""
        from utils.encoders import default_json_encoder
        import pytest

        class UnserializableClass:
            def __json__(self):
                raise TypeError("Unsupported type")

        with pytest.raises(TypeError):
            default_json_encoder(UnserializableClass())

    def test_orjson_dumps(self):
        """Тест orjson_dumps"""
        from utils.encoders import orjson_dumps
        data = {"key": "value"}
        result = orjson_dumps(data)
        assert isinstance(result, bytes)
        assert b"key" in result

    def test_orjson_loads(self):
        """Тест orjson_loads"""
        from utils.encoders import orjson_loads
        data = b'{"key": "value"}'
        result = orjson_loads(data)
        assert result == {"key": "value"}

    def test_json_encoder_class(self):
        """Тест JSONEncoder класса"""
        from utils.encoders import JSONEncoder
        encoder = JSONEncoder()
        data = {"key": "value"}
        result = encoder.encode(data)
        assert isinstance(result, str)
        assert "key" in result

    def test_fast_json_functions(self):
        """Тест быстрых JSON функций"""
        from utils.encoders import fast_json_dumps, fast_json_loads
        data = {"key": "value"}
        json_str = fast_json_dumps(data)
        result = fast_json_loads(json_str)
        assert result == data


class TestUtilsExtractText:
    """Тесты для utils.extract_text"""

    def test_extract_text_import(self):
        """Тест импорта extract_text"""
        from utils.extract_text import extract_text, wrap_html_fragment
        assert extract_text is not None
        assert wrap_html_fragment is not None

    def test_extract_text_from_html_simple(self):
        """Тест extract_text с простым HTML"""
        from utils.extract_text import extract_text
        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <p>Hello world</p>
        </body>
        </html>
        """
        result = extract_text(html)
        assert "Hello world" in result, f"Результат: {result}"

    def test_extract_text_from_html_complex(self):
        """Тест extract_text с комплексным HTML"""
        from utils.extract_text import extract_text
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
        </head>
        <body>
            <h1>Title</h1>
            <p>Paragraph with <strong>bold</strong> text</p>
            <ul><li>Item 1</li><li>Item 2</li></ul>
        </body>
        </html>
        """
        result = extract_text(html)
        assert "Title" in result, f"Результат: {result}"
        assert "Paragraph with bold text" in result, f"Результат: {result}"
        assert "Item 1" in result, f"Результат: {result}"
        assert "Item 2" in result, f"Результат: {result}"

    def test_extract_text_from_html_empty(self):
        """Тест extract_text с пустым HTML"""
        from utils.extract_text import extract_text
        result = extract_text("")
        assert result == ""

    def test_extract_text_from_html_none(self):
        """Тест extract_text с None"""
        from utils.extract_text import extract_text
        result = extract_text(None)
        assert result == ""

    def test_wrap_html_fragment(self):
        """Тест wrap_html_fragment"""
        from utils.extract_text import wrap_html_fragment
        fragment = "<p>Test</p>"
        result = wrap_html_fragment(fragment)
        assert "<!DOCTYPE html>" in result
        assert "<html>" in result
        assert "<p>Test</p>" in result

    def test_wrap_html_fragment_full_html(self):
        """Тест wrap_html_fragment с полным HTML"""
        from utils.extract_text import wrap_html_fragment
        full_html = "<!DOCTYPE html><html><body><p>Test</p></body></html>"
        result = wrap_html_fragment(full_html)
        assert result == full_html


class TestUtilsGenerateSlug:
    """Тесты для utils.generate_slug"""

    def test_generate_slug_import(self):
        """Тест импорта generate_slug"""
        from utils.generate_slug import replace_translit, generate_unique_slug
        assert replace_translit is not None
        assert generate_unique_slug is not None

    def test_replace_translit_simple(self):
        """Тест replace_translit с простым текстом"""
        from utils.generate_slug import replace_translit
        result = replace_translit("hello")
        assert result == "hello"

    def test_replace_translit_with_special_chars(self):
        """Тест replace_translit со специальными символами"""
        from utils.generate_slug import replace_translit
        result = replace_translit("hello.world")
        assert result == "hello-world"

    def test_replace_translit_with_cyrillic(self):
        """Тест replace_translit с кириллицей"""
        from utils.generate_slug import replace_translit
        result = replace_translit("привет")
        assert result == "privet"  # Корректная транслитерация слова "привет"

    def test_replace_translit_empty(self):
        """Тест replace_translit с пустой строкой"""
        from utils.generate_slug import replace_translit
        result = replace_translit("")
        assert result == ""

    def test_replace_translit_none(self):
        """Тест replace_translit с None"""
        from utils.generate_slug import replace_translit
        result = replace_translit(None)
        assert result == ""

    def test_replace_translit_with_numbers(self):
        """Тест replace_translit с числами"""
        from utils.generate_slug import replace_translit
        result = replace_translit("test123")
        assert "123" in result

    def test_replace_translit_multiple_spaces(self):
        """Тест replace_translit с множественными пробелами"""
        from utils.generate_slug import replace_translit
        result = replace_translit("hello   world")
        assert "hello" in result
        assert "world" in result

    @patch('utils.generate_slug.local_session')
    def test_generate_unique_slug(self, mock_session):
        """Тест generate_unique_slug с моком сессии"""
        from utils.generate_slug import generate_unique_slug
        mock_session.return_value.__enter__.return_value.query.return_value.where.return_value.first.return_value = None
        result = generate_unique_slug("test")
        assert isinstance(result, str)
        assert len(result) > 0
