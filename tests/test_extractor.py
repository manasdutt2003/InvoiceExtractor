import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import extractor  # noqa: E402


# --- validate_upload -------------------------------------------------------

def test_validate_upload_accepts_png():
    extractor.validate_upload(1000, "image/png")


def test_validate_upload_rejects_empty():
    with pytest.raises(ValueError):
        extractor.validate_upload(0, "image/png")


def test_validate_upload_rejects_too_large():
    too_big = extractor.MAX_UPLOAD_MB * 1024 * 1024 + 1
    with pytest.raises(ValueError):
        extractor.validate_upload(too_big, "application/pdf")


def test_validate_upload_rejects_unknown_type():
    with pytest.raises(ValueError):
        extractor.validate_upload(10, "text/plain")
    with pytest.raises(ValueError):
        extractor.validate_upload(10, None)


# --- parse_json_reply ------------------------------------------------------

def test_parse_plain_json():
    assert extractor.parse_json_reply('{"a": 1}') == {"a": 1}


def test_parse_fenced_json():
    assert extractor.parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        extractor.parse_json_reply("not json")


# --- to_number -------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [(5, 5), (2.5, 2.5), ("12.50", 12.5), ("$1,234.50", 1234.5), ("EUR 10", 10.0)],
)
def test_to_number_valid(value, expected):
    assert extractor.to_number(value) == expected


@pytest.mark.parametrize("value", ["1.234,50", "abc", None, True, [1]])
def test_to_number_rejects_ambiguous_or_invalid(value):
    assert extractor.to_number(value) is None


# --- normalize_invoice -----------------------------------------------------

def test_normalize_converts_string_amounts_without_mutating_input():
    raw = {"subtotal": "100.00", "tax_amount": "10.00", "total_amount": "110.00"}
    cleaned, warnings = extractor.normalize_invoice(raw)
    assert cleaned["total_amount"] == 110.0
    assert raw["total_amount"] == "110.00"
    assert warnings == []


def test_normalize_warns_when_total_does_not_add_up():
    _, warnings = extractor.normalize_invoice(
        {"subtotal": 100, "tax_amount": 10, "total_amount": 150}
    )
    assert any("does not equal total" in w for w in warnings)


def test_normalize_warns_when_line_items_do_not_match_subtotal():
    data = {
        "subtotal": 100,
        "line_items": [{"amount": 40}, {"amount": 40}],
    }
    _, warnings = extractor.normalize_invoice(data)
    assert any("Line item amounts" in w for w in warnings)


def test_normalize_keeps_nulls_without_warning():
    cleaned, warnings = extractor.normalize_invoice({"subtotal": None, "line_items": None})
    assert cleaned["subtotal"] is None
    assert warnings == []


def test_normalize_warns_on_unreadable_number():
    _, warnings = extractor.normalize_invoice({"total_amount": "1.234,50"})
    assert any("total_amount" in w for w in warnings)


def test_normalize_rejects_non_object():
    with pytest.raises(extractor.ExtractionError):
        extractor.normalize_invoice([1, 2, 3])


# --- ask_gemini ------------------------------------------------------------

class FakeResponse:
    def __init__(self, text=None):
        self._text = text
        self.prompt_feedback = "blocked"

    @property
    def text(self):
        if self._text is None:
            raise ValueError("no text")
        return self._text


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_content(self, parts, generation_config):
        self.calls.append((parts, generation_config))
        return self.response


def test_ask_gemini_requests_json_mode_and_strips_text():
    model = FakeModel(FakeResponse("  {\"a\": 1}  "))
    out = extractor.ask_gemini(model, b"x", "image/png", "prompt", as_json=True)
    assert out == '{"a": 1}'
    config = model.calls[0][1]
    assert config["response_mime_type"] == "application/json"
    assert config["temperature"] == 0


def test_ask_gemini_plain_mode_has_no_json_mime():
    model = FakeModel(FakeResponse("INV-1"))
    extractor.ask_gemini(model, b"x", "image/png", "q", as_json=False)
    assert "response_mime_type" not in model.calls[0][1]


def test_ask_gemini_raises_when_blocked():
    model = FakeModel(FakeResponse(None))
    with pytest.raises(extractor.ExtractionError):
        extractor.ask_gemini(model, b"x", "image/png", "q", as_json=False)
