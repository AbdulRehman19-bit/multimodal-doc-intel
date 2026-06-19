FROM python:3.11-slim

# System deps for pdf2image (poppler) and torch
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (Docker cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create index storage dir
RUN mkdir -p /tmp/indexes

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]