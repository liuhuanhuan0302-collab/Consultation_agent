FROM python:3.12-slim

WORKDIR /app

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
    
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

COPY --chown=app:app . .

RUN mkdir -p /app/data && chown -R app:app /app/data

ENV HOME=/home/app \
    XDG_CACHE_HOME=/tmp/.cache

USER app

EXPOSE 8000

CMD ["sh", "scripts/start_backend.sh"]
