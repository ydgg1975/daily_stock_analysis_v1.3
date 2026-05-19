# ===================================
# Aguzixuanguzhinengfenxixitong - Docker jingxiang
# ===================================
# duojieduangoujian：qianduandabao + houduanyunxing

FROM node:20-slim AS web-builder

WORKDIR /app/apps/dsa-web

COPY apps/dsa-web/package.json apps/dsa-web/package-lock.json ./
RUN npm ci

COPY apps/dsa-web/ ./
RUN npm run build

# Pin to bookworm: wkhtmltopdf was removed from Debian testing (2025)
FROM python:3.11-slim-bookworm

# shezhigongzuomulu
WORKDIR /app

# shezhishiquweishanghai
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# anzhuangxitongyilai（wkhtmltopdf han wkhtmltoimage，yongyu Markdown zhuantupian Issue #289）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    gosu \
    wkhtmltopdf \
    fontconfig \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# chuangjianfei root yonghu (UID 1000)
RUN groupadd -g 1000 dsa && \
    useradd -u 1000 -g dsa -m dsa

# fuzhiyilaiwenjian
COPY requirements.txt .

# anzhuang Python yilai
RUN pip install --no-cache-dir -r requirements.txt

# fuzhiyingyongdaima
COPY *.py ./
COPY api/ ./api/
COPY data_provider/ ./data_provider/
COPY bot/ ./bot/
COPY src/ ./src/
COPY strategies/ ./strategies/
COPY --from=web-builder /app/static ./static/
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# quebaoshujumulucunzaibingshouquangei non-root yonghu
RUN mkdir -p /app/data /app/logs /app/reports && \
    chown -R dsa:dsa /app && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

# shezhihuanjingbianliangmorenzhi
ENV PYTHONUNBUFFERED=1
ENV LOG_DIR=/app/logs
ENV DATABASE_PATH=/app/data/stock_analysis.db
# Web/API service
ENV WEBUI_HOST=0.0.0.0
ENV API_PORT=8000

# baolu API duankou
EXPOSE 8000

# shujujuan（chijiuhuashuju）
VOLUME ["/app/data", "/app/logs", "/app/reports"]

# jiankangjiancha（FastAPI moshi）
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || curl -f http://localhost:8000/health \
    || python -c "import sys; sys.exit(0)"

# qidongrukouxianxiufu bind mount muluquanxian，zaijiangquanwei dsa zhixingyingyong；
# wendanghua docker-compose exec minglingxuxianshishiyong -u dsa，bimianshoudongjinchengxieru root-owned wenjian。
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# morenmingling（kebeifugai）
CMD ["python", "main.py", "--schedule"]
