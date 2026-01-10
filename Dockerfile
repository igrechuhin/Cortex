FROM python:3.13-alpine

# Install system dependencies
RUN apk add --no-cache gcc musl-dev linux-headers

# Set working directory
WORKDIR /app

# Copy all files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Run the Cortex MCP server
CMD ["python", "src/cortex/main.py"]
