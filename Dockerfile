FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY docs ./docs
COPY .env.example ./.env.example

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .[dev]

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "exception_ops.api.app:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
