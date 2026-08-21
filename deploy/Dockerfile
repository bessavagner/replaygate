# syntax=docker/dockerfile:1

# --- stage 1: build the SPA -------------------------------------------------
FROM node:24-alpine AS frontend
WORKDIR /build
COPY src/frontend/package.json src/frontend/package-lock.json ./
# A full install on purpose: tailwindcss and daisyui are devDependencies and the
# CSS build needs them. Never add --omit=dev here.
RUN npm ci
COPY src/frontend/ ./
RUN npm run build

# --- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REPLAYGATE_FIXTURES=/app/fixtures \
    REPLAYGATE_FRONTEND=/app/frontend \
    PORT=8080
WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/replaygate ./src/replaygate
RUN pip install --no-cache-dir '.[dashboard]'

COPY --from=frontend /build/dist ./frontend

# The demo dataset is generated, not committed: `record` is deterministic and
# fully offline, so the image always ships something real to look at.
RUN replaygate record support_happy /app/fixtures/support_happy \
 && replaygate record booking_happy /app/fixtures/booking_happy \
 && replaygate record booking_books_without_confirm_regression /app/fixtures/booking_regression

# The one fixture that carries a real recorded judge verdict, so the demo shows
# judge chips. Recorded once against Anthropic; replayed offline forever after.
COPY fixtures/support_happy_judged /app/fixtures/support_happy_judged

EXPOSE 8080
CMD ["sh", "-c", "replaygate dashboard serve --host 0.0.0.0 --port ${PORT}"]
