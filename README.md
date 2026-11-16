# Invoice Extractor

Upload an invoice image or PDF and either ask a question about it or pull out
its fields as structured JSON. Built with Streamlit and Google Gemini's
multimodal model.

## Features

- **Ask a question**: "What is the invoice number?", "Who is the vendor?"
- **Extract all fields**: invoice number, dates, vendor, customer, currency,
  subtotal, tax, total and line items, returned as JSON you can download
- Accepts JPG, PNG, WebP and PDF, with a size limit checked before any API call
- Uses Gemini's JSON response mode, so the structured output is valid JSON
  rather than text that has to be parsed
- **Sanity checks**: numeric strings are converted to numbers when unambiguous,
  and the app warns if subtotal + tax does not equal the total or if line items
  do not add up to the subtotal. The extracted values are never changed to
  make them fit.

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

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GOOGLE_API_KEY` | none (required) | Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model name |
| `MAX_UPLOAD_MB` | `10` | Maximum upload size |
| `MAX_OUTPUT_TOKENS` | `4096` | Output token cap |
| `LOG_LEVEL` | `INFO` | Logging level |

## Docker

```bash
docker build -t invoice-extractor .
docker run -p 8501:8501 -e GOOGLE_API_KEY=your-key invoice-extractor
```

Then open http://localhost:8501.

## Tests

```bash
pip install pytest
python -m pytest -q
```

The tests use a fake model, so they need no API key or network.

## Project layout

- `app.py`: Streamlit UI
- `extractor.py`: validation, Gemini call, JSON parsing, consistency checks
- `tests/`: unit tests
- `docs/ARCHITECTURE.md`: design notes

## Notes

- Uploaded files are sent to the Gemini API and are not written to disk.
- Extraction is done by a language model. Check amounts against the original
  before using them for accounting.
