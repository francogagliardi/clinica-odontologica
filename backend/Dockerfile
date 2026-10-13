# ---- deps stage: resolve + install Python deps ----
FROM python:3.12-slim AS deps
WORKDIR /srv/api
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- production stage: lean, non-root, single process (R-08) ----
FROM python:3.12-slim AS production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home --shell /bin/false appuser
WORKDIR /srv/api
COPY --from=deps /usr/local /usr/local
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser alembic/ ./alembic/
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
