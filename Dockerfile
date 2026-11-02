# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# Install the same declared runtime dependencies as the Python project.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Set Python path
ENV PYTHONPATH=/app/src

# Run the MCP server
CMD ["python", "-m", "mcp_internet.server"]
