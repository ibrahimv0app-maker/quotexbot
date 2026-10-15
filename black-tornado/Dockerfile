FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/qbot
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 qbot
COPY --chown=qbot:qbot app ./app
COPY --chown=qbot:qbot strategy_settings.json black_tornado_settings.json ./
USER qbot
CMD ["python", "-m", "app.main"]
