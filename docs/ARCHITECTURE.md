# Architecture

## Overview

```
Browser -> app.py (Streamlit UI) -> extractor.py -> Gemini API
                  ^                      |
                  +-- warnings / JSON <--+
```

| File | Responsibility |
| --- | --- |
| `app.py` | UI only: API key lookup, file upload, mode selection, rendering results. |
| `extractor.py` | Upload validation, prompt, Gemini call, JSON parsing, number normalisation, consistency checks. No Streamlit imports. |
| `tests/test_extractor.py` | Unit tests for `extractor.py` using a fake model. |

## Request flow

1. The user uploads a file and picks a mode (question or full extraction).
2. `validate_upload` checks that the file is non-empty, within `MAX_UPLOAD_MB`, and one of JPG/PNG/WebP/PDF.
3. `ask_gemini` sends the prompt and the file bytes. In extraction mode it sets `response_mime_type=application/json`, with `temperature=0`.
4. In extraction mode, `parse_json_reply` parses the reply (tolerating a code fence). `normalize_invoice` converts unambiguous numeric strings to numbers and returns warnings.
5. The UI shows the JSON, any warnings, and a download button.

## Design decisions

- **Pure logic is separate from the UI.** Streamlit reruns the script on every interaction and is awkward to test. Keeping the logic in a plain module avoids that.
- **Lazy SDK import.** `build_model` imports `google.generativeai` on first use, so tests run without the SDK installed or an API key.
- **Checks warn but never fix.** If subtotal + tax != total, the value might be a misread or the invoice might really be that way. The app tells the user and leaves the data as the model returned it.
- **Ambiguous numbers are rejected.** A string like `1.234,50` could be read two ways, so `to_number` returns `None` and the app warns instead of guessing.
- **Uploads are processed in memory** and sent to the Gemini API. They are not written to disk by this app.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GOOGLE_API_KEY` | none (required) | Gemini API key (env, `.env` or Streamlit secrets). |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model name. |
| `MAX_UPLOAD_MB` | `10` | Reject larger uploads before calling the API. |
| `MAX_OUTPUT_TOKENS` | `4096` | Output token cap per request. |
| `LOG_LEVEL` | `INFO` | Python logging level. |

## Limitations

- Accuracy depends on the model and the document quality. The consistency checks catch some errors, not all.
- Each request handles one file and has no retry logic.
- No authentication or rate limiting. Put it behind your own access control if you deploy it publicly.
