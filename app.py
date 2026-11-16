"""Ask questions about an invoice image, or extract its fields as JSON,
using Google Gemini's multimodal model."""

from __future__ import annotations

import json
import logging
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("invoice_extractor")

# Imported after load_dotenv() so .env values (GEMINI_MODEL, MAX_UPLOAD_MB, ...) apply.
import extractor  # noqa: E402

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
    return extractor.build_model(api_key)


st.title("📄 Invoice Extractor")
st.caption(f"Upload an invoice and ask about it. Powered by {extractor.MODEL_NAME}.")

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
        file_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type or "image/jpeg"
        try:
            extractor.validate_upload(len(file_bytes), mime_type)
        except ValueError as error:
            st.error(str(error))
            st.stop()

        prompt = extractor.EXTRACTION_PROMPT if extract_json else question.strip()
        with st.spinner("Analyzing invoice with Gemini..."):
            try:
                answer = extractor.ask_gemini(
                    get_model(api_key), file_bytes, mime_type, prompt, extract_json
                )
            except Exception as error:
                logger.exception("Gemini request failed")
                st.error(f"Error: {error}")
                st.stop()

        st.success("Extracted information")
        if extract_json:
            try:
                data, warnings = extractor.normalize_invoice(
                    extractor.parse_json_reply(answer)
                )
            except (json.JSONDecodeError, extractor.ExtractionError):
                logger.warning("Model reply was not a usable JSON object")
                st.warning("The model did not return a valid invoice JSON object. Raw reply:")
                st.code(answer)
            else:
                for message in warnings:
                    st.warning(f"Check against the original: {message}")
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
