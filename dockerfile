FROM python:3.12-slim

WORKDIR /app

COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

COPY api.py .
COPY worker.py .

EXPOSE 5000


