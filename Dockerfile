# Stage 1: 构建前端
FROM node:20-slim AS frontend-builder
RUN npm install -g bun
WORKDIR /app
COPY packages/openapi-client/package.json packages/openapi-client/
COPY admin/package.json admin/bun.lock admin/
WORKDIR /app/admin
RUN bun install --frozen-lockfile
COPY packages/openapi-client/ /app/packages/openapi-client/
COPY admin/ .
RUN bun run build

# Stage 2: 运行环境
FROM python:3.12-slim

WORKDIR /app

# 安装 supercronic + uv
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 \
    -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

# Python 依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 复制代码
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY crontab .

# 复制前端构建产物
COPY --from=frontend-builder /app/admin/dist admin/dist/

# 创建数据目录
RUN mkdir -p data/covers data/backups data/logs

EXPOSE 8000
