# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and static files
COPY server.py .
COPY index.html .
COPY script.js .
COPY style.css .

# Create downloads directory
RUN mkdir -p /app/downloads

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV DEBUG=False

# Run the Flask app
CMD ["python", "server.py"]
