FROM python:3.12-slim

# Install system dependencies required by some Python packages (e.g. asyncpg, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry in an isolated location to avoid polluting the system site-packages
ENV POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

# Copy dependency manifests first to leverage Docker layer caching —
# dependencies are only re-installed when these files change.
COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root --no-interaction

# Copy the rest of the project after dependencies are installed
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]
