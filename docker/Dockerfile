# ===================================
# A股自选股智能分析系统 - Docker 镜像
# ===================================
# 多阶段构建：前端打包 + 后端运行

FROM node:20-slim AS web-builder
WORKDIR /app
COPY apps/dsa-web/package*.json ./apps/dsa-web/
RUN cd apps/dsa-web && npm install --registry=https://registry.npmmirror.com
COPY apps/dsa-web ./apps/dsa-web
RUN cd apps/dsa-web && npm run build

FROM python:3.10-slim
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -g 1000 dsa && \
    useradd -u 1000 -g dsa -m dsa && \
    chown -R dsa:dsa /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 复制前端静态资源
COPY --from=web-builder /app/static ./static

# 确保数据和日志目录存在并具有正确权限
RUN mkdir -p data logs reports && chown -R dsa:dsa data logs reports

# 切换到非 root 用户
USER dsa

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || curl -f http://localhost:8000/health \
    || python -c "import sys; sys.exit(0)"

# 默认命令（可被覆盖）
CMD ["python", "main.py", "--schedule"]
