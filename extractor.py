"""Core logic for the invoice extractor, independent of Streamlit.

Keeping this separate from the UI makes it unit-testable without a browser,
an API key or network access.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger("invoice_extractor")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _env_int(name: str, default: int) -> int:
    """Read a positive integer from the environment, falling back to default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Ignoring non-integer %s=%r", name, raw)
        return default
    if value <= 0:
        logger.warning("Ignoring non-positive %s=%r", name, raw)
        return default
    return value


MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 10)
MAX_OUTPUT_TOKENS = _env_int("MAX_OUTPUT_TOKENS", 4096)

ALLOWED_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "application/pdf"}
)

EXTRACTION_PROMPT = """Extract the fields below from this invoice and return
one JSON object with exactly these keys. Use null for anything that is not
visible on the invoice. Amounts must be numbers without currency symbols.

- invoice_number
- invoice_date (YYYY-MM-DD when the date is unambiguous)
- due_date
- vendor_name
- vendor_address
- customer_name
- currency (ISO code if it can be inferred)
- subtotal
- tax_amount
- total_amount
- line_items: list of {description, quantity, unit_price, amount}
"""

TOP_LEVEL_NUMERIC = ("subtotal", "tax_amount", "total_amount")
LINE_ITEM_NUMERIC = ("quantity", "unit_price", "amount")

# Tolerance when comparing sums, in currency units (rounding on invoices).
TOLERANCE = 0.011


class ExtractionError(RuntimeError):
    """Raised when the model returns nothing usable."""


def validate_upload(size_bytes: int, mime_type: str | None) -> None:
    """Raise ValueError if the file is empty, too large or an unsupported type."""
    if size_bytes <= 0:
        raise ValueError("The uploaded file is empty.")
    limit = MAX_UPLOAD_MB * 1024 * 1024
    if size_bytes > limit:
        raise ValueError(
            f"File is {size_bytes / 1024 / 1024:.1f} MB; the limit is {MAX_UPLOAD_MB} MB."
        )
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Unsupported file type {mime_type!r}. Use JPG, PNG, WebP or PDF."
        )


def parse_json_reply(text: str) -> Any:
    """Parse a model reply as JSON, tolerating a surrounding markdown code fence."""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1)
    return json.loads(cleaned)  # raises json.JSONDecodeError on bad input


_PLAIN_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_THOUSANDS_NUMBER = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


def to_number(value: Any) -> float | int | None:
    """Convert a value to a number, or return None if that is not unambiguous.

    Accepts numbers, and strings like "12.50", "$1,234.50" or "EUR 10".
    Formats such as "1.234,50" are ambiguous and are rejected rather than guessed.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None
    candidate = re.sub(r"[^\d,.\-]", "", value)
    if _PLAIN_NUMBER.match(candidate):
        return float(candidate)
    if _THOUSANDS_NUMBER.match(candidate):
        return float(candidate.replace(",", ""))
    return None


def normalize_invoice(data: Any) -> tuple[dict[str, Any], list[str]]:
    """Return (cleaned copy, warnings) for an extracted invoice.

    Numeric fields that arrive as strings are converted when unambiguous.
    Consistency checks only produce warnings; extracted values are never
    altered to make them fit.
    """
    warnings: list[str] = []
    if not isinstance(data, dict):
        raise ExtractionError("Expected a JSON object with invoice fields.")

    result: dict[str, Any] = dict(data)

    def convert(container: dict[str, Any], key: str, label: str) -> None:
        original = container.get(key)
        if original is None or isinstance(original, bool):
            if isinstance(original, bool):
                warnings.append(f"{label} is not a number: {original!r}")
            return
        if isinstance(original, (int, float)):
            return
        converted = to_number(original)
        if converted is None:
            warnings.append(f"Could not read {label} as a number: {original!r}")
        else:
            container[key] = converted

    for key in TOP_LEVEL_NUMERIC:
        convert(result, key, key)

    items = result.get("line_items")
    cleaned_items: list[Any] = []
    if isinstance(items, list):
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                item = dict(item)
                for key in LINE_ITEM_NUMERIC:
                    convert(item, key, f"line item {index} {key}")
            cleaned_items.append(item)
        result["line_items"] = cleaned_items
    elif items is not None:
        warnings.append("line_items is not a list.")

    subtotal = result.get("subtotal")
    tax = result.get("tax_amount")
    total = result.get("total_amount")
    nums = (int, float)
    if all(isinstance(v, nums) and not isinstance(v, bool) for v in (subtotal, tax, total)):
        if abs(subtotal + tax - total) > TOLERANCE:
            warnings.append(
                f"subtotal ({subtotal}) + tax ({tax}) does not equal total ({total})."
            )

    amounts = [
        item.get("amount")
        for item in cleaned_items
        if isinstance(item, dict)
    ]
    if (
        amounts
        and isinstance(subtotal, nums)
        and all(isinstance(a, nums) and not isinstance(a, bool) for a in amounts)
        and abs(sum(amounts) - subtotal) > TOLERANCE
    ):
        warnings.append(
            f"Line item amounts sum to {sum(amounts):.2f} but subtotal is {subtotal}."
        )

    return result, warnings


def ask_gemini(
    model: Any,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    as_json: bool,
) -> str:
    """Send the invoice and prompt to Gemini and return the text reply."""
    config: dict[str, Any] = {"max_output_tokens": MAX_OUTPUT_TOKENS, "temperature": 0}
    if as_json:
        # Ask the API for JSON directly instead of parsing it out of prose.
        config["response_mime_type"] = "application/json"

    logger.info(
        "Calling %s (mime=%s, bytes=%d, json=%s)",
        MODEL_NAME,
        mime_type,
        len(image_bytes),
        as_json,
    )
    response = model.generate_content(
        [prompt, {"mime_type": mime_type, "data": image_bytes}],
        generation_config=config,
    )
    try:
        return response.text.strip()
    except ValueError:
        # response.text raises when the reply was blocked or came back empty.
        reason = getattr(response, "prompt_feedback", None)
        logger.error("Gemini returned no text: %s", reason)
        raise ExtractionError(f"Gemini returned no text. {reason or ''}".strip())


def build_model(api_key: str) -> Any:
    """Configure the Gemini SDK and return a model (imported lazily)."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)
