# Single service: FastAPI serves API + built React workspace from app/static/build
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# System deps for pdfplumber (no extra build tools needed at runtime)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Frontend already built in repo (app/static/build). Rebuild only if node is present.
EXPOSE 8000
# VPS: 0.0.0.0 + env PORT/HOST override; local still works with same image
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
