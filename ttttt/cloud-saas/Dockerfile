FROM python:3.11-slim

WORKDIR /app

# Install standard tools needed for building dependencies if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's browser binaries and system dependencies natively
RUN playwright install --with-deps chromium

COPY app/ ./app/
COPY static/ ./static/
# Include the generated VAPID private key via environment variable instead of file

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
