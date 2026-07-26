ARG PYTHON_BASE_IMAGE=python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
FROM ${PYTHON_BASE_IMAGE}

WORKDIR /app

ARG GIT_REVISION
RUN printf '%s\n' "${GIT_REVISION}" | grep -Eq '^[0-9a-f]{40}$'
LABEL org.opencontainers.image.revision="${GIT_REVISION}"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
