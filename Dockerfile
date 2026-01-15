FROM python:3.13-alpine

# Install system dependencies including Node.js and npm for markdownlint-cli2
RUN apk add --no-cache gcc musl-dev linux-headers nodejs npm

# Install markdownlint-cli2 globally (required for fix_markdown_lint MCP tool)
RUN npm install -g markdownlint-cli2

# Set working directory
WORKDIR /app

# Copy all files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Run the Cortex MCP server
CMD ["python", "src/cortex/main.py"]
