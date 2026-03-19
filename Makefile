.PHONY: gen gen-openapi lint lint-backend lint-frontend test dev setup

# 统一生成命令（P2 之后可用）
gen: gen-openapi

gen-openapi:
	@echo "== 导出 OpenAPI =="
	uv run python -c "import json; from app.main import app; from fastapi.openapi.utils import get_openapi; print(json.dumps(get_openapi(title=app.title, version=app.version, routes=app.routes), ensure_ascii=False, indent=2))" > openapi.json
	@echo "== 生成 TS 客户端 =="
	cd packages/openapi-client && bunx @hey-api/openapi-ts
	@rm openapi.json
	@echo "生成完成"

# 质量门禁
lint: lint-backend lint-frontend

lint-backend:
	uv run ruff check .
	uv run ruff format --check .
	uv run lint-imports
	uv run pyright

lint-frontend:
	@test -f admin/package.json && (cd admin && bunx biome check . && bunx vue-tsc --noEmit) || echo "跳过前端检查（admin/ 不存在）"

test:
	uv run pytest

# 本地开发
dev:
	@echo "后端: uvicorn app.main:app --reload --port 8000"
	@echo "前端: cd admin && bun dev"

# 首次初始化
setup:
	uv sync --dev
	@test -f admin/package.json && (cd admin && bun install) || true
	@test -f packages/openapi-client/package.json && (cd packages/openapi-client && bun install) || true
	cp -n .env.example .env || true
	git config core.hooksPath .githooks
	@echo "初始化完成，请编辑 .env 填入 API Key"
