# Multi-stage / Production Dockerfile for Sutra Engine
FROM python:3.12-slim-bookworm

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOST=0.0.0.0 \
    PORT=8010

# Install system dependencies: pandoc, curl, fontconfig, tar
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    curl \
    tar \
    ca-certificates \
    fontconfig \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Install Tectonic (modern, standalone, self-contained LaTeX engine)
ARG TECTONIC_VERSION=0.15.0
RUN curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/tectonic \
    && tectonic --version

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy source code and assets
COPY . /app

# Install sutra package in editable/module mode
RUN pip install --no-cache-dir -e .

# Create directory for persistent runtime data
RUN mkdir -p /app/build /app/build/temp /app/build/projects /app/build/journals

# Expose port
EXPOSE 8010

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8010/ || exit 1

# Start Sutra Press web server
CMD ["python", "run_web.py"]
