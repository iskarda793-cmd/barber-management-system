# ---- Base image ----
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Working directory inside the container
WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Run as a non-root user for security
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Flask app listens on port 5000 by default.
# Cloud platforms may override it with the PORT variable (Render sets PORT).
ENV PORT=5000
EXPOSE 5000

# Start the app with gunicorn (production-ready WSGI server)
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 60 app:app"]
