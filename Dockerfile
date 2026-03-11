FROM python:3.13-alpine

# Install system build dependencies for Cortex
RUN apk add --no-cache gcc musl-dev linux-headers

# Set working directory
WORKDIR /app

# Copy all files
COPY . /app

# Install Python dependencies from pyproject.toml (single source of truth)
RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

# Run the Cortex MCP server
CMD ["python", "src/cortex/main.py"]
