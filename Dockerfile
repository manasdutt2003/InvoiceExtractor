FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py extractor.py ./

# Run as an unprivileged user.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8501

# Pass the key at runtime: docker run -e GOOGLE_API_KEY=... -p 8501:8501 <image>
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
