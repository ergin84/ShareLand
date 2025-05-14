FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    python3-dev \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL config path (optional but helps some builds)
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Set working directory
WORKDIR /app

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy source code
COPY . .

CMD ["python3", "manage.py", "runserver"]
