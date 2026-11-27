FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY ui ./ui
COPY config ./config
COPY deployment ./deployment
RUN useradd --uid 10001 --create-home appuser && chown -R appuser:appuser /app
USER appuser
CMD ["sh", "-c", "exec python -m uvicorn deployment.app:build --factory --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
