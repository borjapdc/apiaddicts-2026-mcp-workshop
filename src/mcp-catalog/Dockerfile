FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.11.14-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && useradd --uid 10001 --create-home workshop
COPY shared ./shared
COPY src/mcp-catalog/app ./app
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app PYTHONUNBUFFERED=1 PORT=8000
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=6s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]