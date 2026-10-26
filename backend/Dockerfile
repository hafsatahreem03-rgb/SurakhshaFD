FROM python:3.12-slim

# Tesseract OCR engine + English language data
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
COPY pytest.ini .

ENV DATABASE_URL=sqlite:////app/data/surakshafd.db \
    STORAGE_DIR=/app/data/uploads \
    SAMPLES_DIR=/app/sample_documents \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# Load the fictional demo data on first start, then run the API. Render sets PORT; Docker Compose uses 8000.
CMD ["sh", "-c", "python -m app.cli ensure-demo && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
