# Stage 1: Build React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve API + built React workspace
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user and persistent data dir before copying files with --chown
RUN useradd -m -u 1000 screenos && \
    mkdir -p /app/data && \
    chown -R screenos:screenos /app/data

# Copy application files and built frontend with correct ownership
COPY --chown=screenos:screenos . .
COPY --from=frontend-builder --chown=screenos:screenos /build/app/static/build /app/app/static/build

USER screenos
EXPOSE 8000

# VPS: 0.0.0.0 + env PORT/HOST override; local still works with same image
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
