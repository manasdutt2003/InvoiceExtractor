# Invoice Extractor

Upload an invoice image or PDF and either ask a question about it or pull out
its fields as structured JSON. Built with Streamlit and Google Gemini's
multimodal model.

## Features

- **Ask a question**: "What is the invoice number?", "Who is the vendor?"
- **Extract all fields**: invoice number, dates, vendor, customer, currency,
  subtotal, tax, total and line items, returned as JSON you can download
- Accepts JPG, PNG, WebP and PDF
- Uses Gemini's JSON response mode, so the structured output is valid JSON
  rather than text that has to be parsed

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then add your key
streamlit run app.py
```

Get a key from [Google AI Studio](https://aistudio.google.com/apikey).

On Streamlit Community Cloud, add `GOOGLE_API_KEY` under **Settings → Secrets**
instead of using a `.env` file.

## Notes

- Uploaded files are sent to the Gemini API and are not written to disk.
- Extraction is done by a language model. Check amounts against the original
  before using them for accounting.
