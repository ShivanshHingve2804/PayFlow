# Stage 1: builder
FROM python:3.11-slim AS builder

WORKDIR /build

RUN pip install --upgrade pip
COPY . .
RUN pip install --user .

# Stage 2: runtime
FROM python:3.11-slim

RUN useradd -m -U payflow

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /root/.local /home/payflow/.local
ENV PATH=/home/payflow/.local/bin:$PATH

# Copy application files
COPY . .
RUN chown -R payflow:payflow /app

USER payflow

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
