FROM python:3.12-slim

WORKDIR /app

COPY deploy/fontconfig/99-consultation-agent-fonts.conf /etc/fonts/conf.d/99-consultation-agent-fonts.conf

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fontconfig \
    fonts-noto-cjk \
    libreoffice-writer \
    && fc-cache -f \
    && fc-match -f '%{family}\n' 'Microsoft YaHei' | head -n 1 | grep -F 'Noto Sans CJK SC' \
    && rm -rf /var/lib/apt/lists/*

# chromium: 客户 PDF 的 HTML→PDF 回退渲染。
# libreoffice-writer: 客户 DOCX → PDF 的 Headless Writer 转换（主路径）。
# fontconfig + fonts-noto-cjk: DOCX 声明 Microsoft YaHei；Linux 容器不能分发该
# 专有字体，因此 LibreOffice 通过 fontconfig 稳定回退到 Noto Sans CJK SC，
# 避免中文方框/缺字；Word 内部图表也优先使用同一套 Noto CJK 字形。
    
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
