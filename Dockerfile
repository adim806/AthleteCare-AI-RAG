FROM python:3.13-slim

WORKDIR /app

# Runtime env — AWS Bedrock credentials are injected at run time via --env-file
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/status')" || exit 1

CMD ["python", "run.py"]
