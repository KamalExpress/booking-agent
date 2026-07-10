FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Setting PLAYWRIGHT_BROWSERS_PATH=0 prevents Playwright from downloading massive browsers during install
ENV PLAYWRIGHT_BROWSERS_PATH=0
RUN pip install --no-cache-dir -r requirements.txt

# Set executable path for Playwright to use the system Chromium
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

COPY app/ ./app/
COPY static/ ./static/
# Include the generated VAPID private key
COPY private_key.pem ./

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
