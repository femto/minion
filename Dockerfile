FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY minion/ ./minion/
COPY config/ ./config/

# Install package
RUN pip install --no-cache-dir -e .

# Create directories for config and cache
RUN mkdir -p /root/.minion/decay-cache

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command - interactive python
CMD ["python", "-c", "print('Minion ready. Run your scripts or use: python -m minion.cli')"]
