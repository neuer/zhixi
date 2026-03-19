# 项目目录结构

> 本文件为唯一的目录结构参考。与其他文档冲突时以此为准。

```
zhixi/
├── README.md                     # 完整中文 README
├── pyproject.toml                # Python 依赖 + ruff/pyright 配置（uv 管理）
├── uv.lock                       # uv 锁定文件
├── .env.example
├── .gitignore
├── alembic.ini                   # 放在项目根目录（非 alembic/ 子目录）
├── Dockerfile                    # 多阶段构建（bun 构建前端 + Python 运行）
├── docker-compose.yml            # web + scheduler + caddy 三容器
├── Caddyfile
├── crontab                       # supercronic 调度配置
├── Makefile                      # 统一构建命令（make gen 等）
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml                # GitHub Actions CI（后端+前端并行）
│   └── pull_request_template.md  # PR 模板
│
├── .githooks/
│   └── pre-commit                # ruff + biome 快速检查
│
├── docs/
│   ├── spec/                     # 项目规范（唯一事实源）
│   └── plans/                    # 实施计划（按 US 编号命名，永久保留）
│
├── alembic/                      # 数据库迁移
│   ├── env.py                    # 用 engine.sync_engine 执行迁移
│   └── versions/
│
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI 入口（路由注册、SPA 静态文件挂载、CORS）
│   ├── cli.py                    # Typer CLI（pipeline/backup/cleanup/unlock，asyncio.run 桥接）
│   ├── config.py                 # 配置（env + DB）+ get_today_digest_date() + get_fetch_window()
│   ├── database.py               # 异步引擎、AsyncSession、WAL pragma、get_db()
│   ├── auth.py                   # JWT + 预览 token 生成/验证 + 登录限流器
│   ├── crud.py                   # 通用 CRUD（async，禁止业务逻辑）
│   │
│   ├── models/                   # SQLAlchemy 模型（__init__.py 集中注册给 Alembic）
│   │   ├── __init__.py
│   │   ├── account.py
│   │   ├── tweet.py
│   │   ├── topic.py
│   │   ├── digest.py
│   │   ├── config.py
│   │   ├── fetch_log.py
│   │   ├── job_run.py
│   │   ├── digest_item.py
│   │   └── api_cost_log.py
│   │
│   ├── schemas/                  # Pydantic 类型定义
│   │   ├── __init__.py
│   │   ├── fetcher_types.py      # RawTweet, FetchResult, TweetType
│   │   ├── client_types.py       # ClaudeResponse
│   │   ├── processor_types.py    # AnalysisResult, ProcessResult
│   │   ├── digest_types.py       # ReorderInput
│   │   ├── publisher_types.py    # PublishResult
│   │   └── report_types.py
│   │
│   ├── clients/                  # 外部 API 客户端
│   │   ├── __init__.py
│   │   ├── claude_client.py
│   │   ├── gemini_client.py
│   │   └── notifier.py
│   │
│   ├── fetcher/                  # M1 数据采集
│   │   ├── __init__.py           # 暴露 get_fetcher() 工厂函数
│   │   ├── base.py               # BaseFetcher 抽象基类
│   │   ├── x_api.py              # XApiFetcher 实现
│   │   ├── third_party.py        # 空壳 + TODO
│   │   └── tweet_classifier.py
│   │
│   ├── processor/                # M2 AI 加工
│   │   ├── __init__.py
│   │   ├── analyzer.py
│   │   ├── analyzer_prompts.py   # 全局分析 Prompt（见 prompts.md R.1.2）
│   │   ├── batch_merger.py
│   │   ├── merger_prompts.py     # 多批去重 Prompt（见 prompts.md R.1.5b）
│   │   ├── translator.py
│   │   ├── translator_prompts.py # 单条/聚合/Thread Prompt（见 prompts.md R.1.3-R.1.5）
│   │   ├── heat_calculator.py
│   │   └── json_validator.py
│   │
│   ├── digest/                   # M3 草稿组装
│   │   ├── __init__.py
│   │   ├── summary_generator.py
│   │   ├── summary_prompts.py    # 导读 Prompt（见 prompts.md R.1.6）
│   │   ├── cover_generator.py
│   │   ├── cover_prompts.py      # 封面图 Prompt（见 prompts.md R.1.7）
│   │   └── renderer.py           # Markdown 渲染（见 prompts.md R.2）
│   │
│   ├── publisher/                # M4 内容发布
│   │   ├── __init__.py
│   │   ├── wechat_client.py      # MVP 空壳，raise NotImplementedError
│   │   ├── manual_publisher.py
│   │   └── templates/
│   │       └── simple.md
│   │
│   ├── api/                      # 路由（无业务逻辑）
│   │   ├── __init__.py
│   │   ├── deps.py               # 依赖工厂（get_*_service）
│   │   ├── auth.py
│   │   ├── setup.py
│   │   ├── accounts.py
│   │   ├── digest.py
│   │   ├── settings.py
│   │   ├── dashboard.py
│   │   ├── history.py
│   │   └── manual.py
│   │
│   └── services/                 # 编排层
│       ├── __init__.py
│       ├── fetch_service.py
│       ├── process_service.py
│       ├── digest_service.py
│       ├── publish_service.py
│       ├── backup_service.py
│       └── notification_service.py
│
├── packages/
│   └── openapi-client/           # 从 OpenAPI 生成的 TS 客户端
│       ├── package.json
│       ├── openapi-ts.config.ts  # @hey-api/openapi-ts 配置
│       └── src/
│           └── gen/              # 生成物，禁止手动修改
│
├── admin/                        # Vue 3 + TypeScript 前端
│   ├── package.json
│   ├── bun.lock
│   ├── tsconfig.json             # TypeScript 配置
│   ├── tsconfig.node.json        # Node 环境 TS 配置（vite.config.ts 用）
│   ├── env.d.ts                  # Vue 类型声明（/// <reference types="vite/client" />）
│   ├── biome.json                # biome lint/格式化配置
│   ├── vite.config.ts            # 开发代理 /api → localhost:8000
│   └── src/
│       ├── App.vue
│       ├── router/index.ts
│       ├── views/
│       │   ├── Login.vue
│       │   ├── Setup.vue
│       │   ├── Dashboard.vue
│       │   ├── Accounts.vue
│       │   ├── Digest.vue
│       │   ├── DigestEdit.vue
│       │   ├── History.vue
│       │   ├── HistoryDetail.vue
│       │   ├── Settings.vue
│       │   └── Preview.vue
│       ├── components/
│       │   ├── TopicCard.vue
│       │   ├── TweetCard.vue
│       │   ├── ArticlePreview.vue
│       │   ├── HeatBadge.vue
│       │   └── AddTweetModal.vue
│       └── api/index.ts          # axios 基础配置（JWT 拦截、错误处理）
│
├── data/
│   ├── zhixi.db
│   ├── covers/
│   ├── backups/
│   ├── logs/
│   └── default_cover.png
│
└── tests/                        # pytest + pytest-asyncio
    ├── conftest.py               # 内存 DB fixture、HTTP client fixture
    ├── fixtures/                 # LLM mock 响应数据
    │   ├── analyzer/             # 全局分析 mock JSON
    │   └── translator/           # 逐条加工 mock JSON
    ├── test_fetcher.py
    ├── test_tweet_classifier.py
    ├── test_analyzer.py
    ├── test_json_validator.py
    ├── test_heat_calculator.py
    ├── test_translator.py
    ├── test_digest.py
    ├── test_publisher.py
    ├── test_api.py
    └── test_backup.py
```
