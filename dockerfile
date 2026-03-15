# api
# FROM python:3.12-slim AS builder

# USER root

# WORKDIR /app
# COPY req.txt .
# RUN pip install --user --no-cache-dir -r req.txt


# FROM python:3.12-slim
# WORKDIR /app

# RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# COPY --from=builder /root/.local /home/appuser/.local
# COPY api.py ./src/
# COPY logger_config.py ./src/
# RUN chown -R appuser:appgroup /app

# ENV PATH=/home/appuser/.local/bin:$PATH
# USER appuser

# EXPOSE 8000
# CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "--worker-tmp-dir", "/dev/shm", "src.api:app"]

# worker
FROM python:3.12-slim AS builder

USER root

WORKDIR /app
COPY req.txt .

RUN pip install --user --no-cache-dir -r req.txt

FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY worker.py ./src/
COPY logger_config.py ./src/

ENV PATH=/home/appuser/.local/bin:$PATH
USER appuser

CMD ["python", "-m", "src.worker"]