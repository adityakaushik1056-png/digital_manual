# Use a stable Python version
FROM python:3.11-slim

# Install system dependencies required by Pillow and Postgres
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    python3-tk \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose port (Render will set $PORT)
EXPOSE 10000

# Start command (use $PORT for flexibility)
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT"]

