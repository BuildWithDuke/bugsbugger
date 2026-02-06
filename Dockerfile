FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY bugsbugger/ ./bugsbugger/

# Create data directory
RUN mkdir -p /data

# Set environment variables
ENV DATABASE_PATH=/data/bugsbugger.db
ENV LOG_LEVEL=INFO

# Run the bot
CMD ["python", "-m", "bugsbugger.main"]
