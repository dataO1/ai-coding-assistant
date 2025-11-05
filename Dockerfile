FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY requirements.txt .
COPY agent_network.py .
COPY config.py .
COPY main.py .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create state directory
RUN mkdir -p /var/lib/agent-network/vectordb

# Non-root user
RUN useradd -m agent-network
USER agent-network

# Default command
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
