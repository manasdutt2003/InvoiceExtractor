"""Ask questions about an invoice image, or extract its fields as JSON,
using Google Gemini's multimodal model."""

from __future__ import annotations

import json
import os

import google.generativeai as genai
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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

st.set_page_config(page_title="Invoice Extractor", page_icon="📄", layout="centered")


def get_api_key() -> str | None:
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        pass  # no secrets.toml: normal for local runs
    return os.getenv("GOOGLE_API_KEY")


@st.cache_resource
def get_model(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)


def ask_gemini(model, image_bytes: bytes, mime_type: str, prompt: str, as_json: bool) -> str:
    """Send the invoice and prompt to Gemini and return the text reply."""
    config = {"max_output_tokens": 4096, "temperature": 0}
    if as_json:
        # Ask the API for JSON directly instead of parsing it out of prose.
        config["response_mime_type"] = "application/json"

    response = model.generate_content(
        [prompt, {"mime_type": mime_type, "data": image_bytes}],
        generation_config=config,
    )
    try:
        return response.text.strip()
    except ValueError:
        # response.text raises when the reply was blocked or came back empty.
        reason = getattr(response, "prompt_feedback", None)
        raise RuntimeError(f"Gemini returned no text. {reason or ''}".strip())


st.title("📄 Invoice Extractor")
st.caption(f"Upload an invoice and ask about it. Powered by {MODEL_NAME}.")

api_key = get_api_key()
if not api_key:
    st.warning(
        "No API key found. Set `GOOGLE_API_KEY` in a `.env` file, as an "
        "environment variable, or in Streamlit secrets."
    )
    st.stop()

uploaded_file = st.file_uploader("Upload invoice", type=["jpg", "jpeg", "png", "webp", "pdf"])
mode = st.radio(
    "What do you want?",
    ("Ask a question", "Extract all fields as JSON"),
    horizontal=True,
)
question = ""
if mode == "Ask a question":
    question = st.text_input("Your question", placeholder="What is the invoice number?")

if uploaded_file and uploaded_file.type != "application/pdf":
    st.image(uploaded_file, caption="Uploaded invoice", use_container_width=True)

if st.button("Extract Information", type="primary"):
    extract_json = mode == "Extract all fields as JSON"
    if not uploaded_file:
        st.warning("Please upload an invoice first.")
    elif not extract_json and not question.strip():
        st.warning("Please enter a question.")
    else:
        prompt = EXTRACTION_PROMPT if extract_json else question.strip()
        with st.spinner("Analyzing invoice with Gemini..."):
            try:
                answer = ask_gemini(
                    get_model(api_key),
                    uploaded_file.getvalue(),
                    uploaded_file.type or "image/jpeg",
                    prompt,
                    extract_json,
                )
            except Exception as error:
                st.error(f"Error: {error}")
                st.stop()

        st.success("Extracted information")
        if extract_json:
            try:
                data = json.loads(answer)
            except json.JSONDecodeError:
                st.warning("The model did not return valid JSON. Raw reply:")
                st.code(answer)
            else:
                st.json(data)
                st.download_button(
                    "Download JSON",
                    json.dumps(data, indent=2),
                    file_name="invoice.json",
                    mime="application/json",
                )
        else:
            st.write(answer)

st.markdown("---")
st.caption("Built with the Google Gemini API and Streamlit. Always verify extracted amounts against the original document.")
