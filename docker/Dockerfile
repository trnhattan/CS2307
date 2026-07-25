FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app

FROM runtime AS backend

COPY --chown=app:app backend ./backend
COPY --chown=app:app scripts ./scripts

USER app

EXPOSE 8000

CMD ["python", "-m", "scripts.start_backend"]

FROM runtime AS frontend

COPY --chown=app:app frontend ./frontend
COPY --chown=app:app .streamlit ./.streamlit
COPY --chown=app:app scripts/__init__.py scripts/start_frontend.py ./scripts/

USER app

EXPOSE 8501

CMD ["python", "-m", "scripts.start_frontend"]
