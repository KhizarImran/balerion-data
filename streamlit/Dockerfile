FROM python:3.11-slim

WORKDIR /app

ENV DATA_DIR=/app/data

# Install deps first (cached layer)
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

# Copy app
COPY app.py .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.fileWatcherType=none", \
     "--browser.gatherUsageStats=false"]
