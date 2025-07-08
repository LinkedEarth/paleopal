# Dockerfile for Isolated Python Execution Service
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TOKENIZERS_PARALLELISM=false

# Install system dependencies including OpenCL
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ocl-icd-opencl-dev \
    opencl-headers \
    clinfo \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements for execution service
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the execution service code
COPY isolated_execution_service.py .

# Create necessary directories
RUN mkdir -p data/plots

# Expose port for the execution service
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the isolated execution service
CMD ["python", "isolated_execution_service.py"] 