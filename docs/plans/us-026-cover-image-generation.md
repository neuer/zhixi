# US-026 封面图生成 实施计划

## Context

US-026 是项目唯一剩余的可选功能。需要集成 Google Gemini Imagen API 生成 AI 日报封面图。功能默认关闭，通过 system_config `enable_cover_generation=true` 开启。超时/失败使用默认封面，不阻塞主流程。

## 现有基础

- `app/clients/gemini_client.py` — 空壳
- `app/digest/cover_generator.py` — 空壳
- `app/digest/cover_prompts.py` — 空壳
- `DailyDigest.cover_image_path` 字段已存在
- `system_config` 已有 `enable_cover_generation`、`cover_generation_timeout` 配置
- `api_cost_log` 已支持 `service='gemini'`, `call_type='cover'`
- `pyproject.toml` 已有 `google-generativeai>=0.8`，**缺少 Pillow**
- Settings.GEMINI_API_KEY 已定义（默认空字符串）

## 实施步骤

### 步骤 1: 添加 Pillow 依赖

**文件**: `pyproject.toml`
- 添加 `"Pillow>=10.0"` 到 dependencies
- 运行 `uv sync --dev` 安装

### 步骤 2: 创建 GeminiImageResponse schema

**文件**: `app/schemas/client_types.py`
- 新增 `GeminiImageResponse(BaseModel)`，字段：`image_bytes: bytes`, `duration_ms: int`, `estimated_cost: float`
- 参照 ClaudeResponse 模式，不含 token 字段（图像生成无 token 概念）

### 步骤 3: 实现 GeminiClient

**文件**: `app/clients/gemini_client.py`
- 参照 `claude_client.py` 模式
- `GeminiAPIError(Exception)` 自定义异常
- `GeminiClient` 类：
  - `__init__(api_key: str, timeout: float = 30.0)` — 创建 `google.genai.Client(api_key=...)`
  - `async generate_image(prompt: str, timeout: float) -> GeminiImageResponse`：
    - 调用 `client.models.generate_images(model="imagen-3.0-generate-002", prompt=prompt, config={"number_of_images": 1, "aspect_ratio": "16:9"})`
    - 注意：google-generativeai SDK 的 generate_images 是同步 API，需要用 `asyncio.to_thread()` 包装
    - 返回 `GeminiImageResponse(image_bytes, duration_ms, estimated_cost)`
    - Imagen 3 定价：$0.04/image（标准模式）
- 模块级惰性单例 `get_gemini_client() -> GeminiClient | None`（GEMINI_API_KEY 为空时返回 None）

### 步骤 4: 实现封面图 Prompt

**文件**: `app/digest/cover_prompts.py`
- `COVER_PROMPT_TEMPLATE` 常量，与 R.1.7 一致
- `build_cover_prompt(top_titles: list[str], digest_date: date) -> str` 纯函数
  - `{top_headlines}` 取 heat_score 前 3 条 snapshot_title
  - `{date}` 英文日期格式 `"March 19, 2026"`

### 步骤 5: 实现封面图生成器

**文件**: `app/digest/cover_generator.py`
- `generate_cover_image(gemini_client, top_items, digest_date, timeout, db) -> str | None`
  - 纯函数模式（参照 summary_generator）
  - 调用 cover_prompts 构建 prompt
  - 调用 gemini_client.generate_image()
  - 用 Pillow 裁切/缩放至 900x383px
  - 保存到 `data/covers/cover_YYYYMMDD.png`
  - 记录 api_cost_log（service='gemini', call_type='cover'）
  - 超时/异常 → 使用默认封面 `data/default_cover.png`（如果存在）→ 返回路径或 None
  - 返回 cover_image_path 字符串

### 步骤 6: 集成到 DigestService

**文件**: `app/services/digest_service.py`
- 在 `generate_daily_digest()` 末尾（step 9 渲染 Markdown 之后）添加封面图生成
- 读取 system_config `enable_cover_generation`
  - 如果 enabled 且 GeminiClient 可用 → 调用 cover_generator
  - 设置 `digest.cover_image_path = result`
- 不阻塞：try-except 包裹，失败只 log warning

### 步骤 7: 添加手动生成路由

**文件**: `app/api/manual.py`
- `POST /api/manual/generate-cover`
  - 认证：`Depends(get_current_admin)`
  - 检查 `enable_cover_generation` → 未开启返回 400 "封面图功能未开启"
  - 检查 GEMINI_API_KEY 是否配置 → 未配置返回 400 "Gemini API Key 未配置"
  - 查找当日 is_current=True 的 digest → 不存在返回 404
  - 调用 cover_generator 生成封面图
  - 更新 digest.cover_image_path
  - 成功返回 `{"message": "封面图生成成功", "cover_path": "..."}`
  - 失败用 JSONResponse(500) 保证 DB 状态持久化

### 步骤 8: 创建默认封面图

- `data/default_cover.png` — 创建 900x383 纯色 PNG 作为默认封面（Pillow 生成）
- 注意：Dockerfile spec 中 `COPY data/default_cover.png data/` 但之前被跳过，现在需要创建

## 测试计划

### test_gemini_client.py
- Mock `google.genai.Client`
- 测试正常生成返回 GeminiImageResponse
- 测试 API 错误 → GeminiAPIError
- 测试超时处理

### test_cover_prompts.py
- 测试 prompt 模板格式化
- 测试空标题列表

### test_cover_generator.py
- Mock GeminiClient + Pillow
- 测试正常生成 → 文件保存 + cost_log 写入
- 测试超时 → 使用默认封面
- 测试异常 → 返回 None
- 测试 Pillow 缩放逻辑

### test_manual_generate_cover_api.py
- 测试功能未开启 → 400
- 测试 API Key 未配置 → 400
- 测试无草稿 → 404
- 测试正常生成 → 200 + cover_path
- 测试生成失败 → 500

### test_digest_service_cover.py
- 测试 enable_cover_generation=true 时调用 cover_generator
- 测试 enable_cover_generation=false 时跳过

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `pyproject.toml` | 修改：添加 Pillow 依赖 |
| `app/schemas/client_types.py` | 修改：添加 GeminiImageResponse |
| `app/clients/gemini_client.py` | 重写：GeminiClient 实现 |
| `app/digest/cover_prompts.py` | 重写：Prompt 模板 |
| `app/digest/cover_generator.py` | 重写：封面图生成逻辑 |
| `app/services/digest_service.py` | 修改：集成封面图生成 |
| `app/api/manual.py` | 修改：添加 generate-cover 路由 |
| `data/default_cover.png` | 新增：默认封面图 |
| `tests/test_gemini_client.py` | 新增 |
| `tests/test_cover_prompts.py` | 新增 |
| `tests/test_cover_generator.py` | 新增 |
| `tests/test_manual_generate_cover_api.py` | 新增 |
| `tests/test_digest_service_cover.py` | 新增 |

## 质量门禁

```bash
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pyright
uv run pytest
```

## 执行结果

### 交付物清单
| 文件 | 操作 | 行数 |
|------|------|------|
| `pyproject.toml` | 修改 | +3/-1 |
| `app/schemas/client_types.py` | 修改 | +8 |
| `app/clients/gemini_client.py` | 重写 | +98/-1 |
| `app/digest/cover_prompts.py` | 重写 | +35/-1 |
| `app/digest/cover_generator.py` | 重写 | +154/-1 |
| `app/services/digest_service.py` | 修改 | +19 |
| `app/api/manual.py` | 修改 | +76 |
| `data/default_cover.png` | 新增 | 二进制 |
| `tests/test_gemini_client.py` | 新增 | 120 |
| `tests/test_cover_prompts.py` | 新增 | 47 |
| `tests/test_cover_generator.py` | 新增 | 153 |
| `tests/test_digest_service_cover.py` | 新增 | 147 |
| `tests/test_manual_generate_cover_api.py` | 新增 | 104 |
| `docs/spec/user-stories.md` | 修改 | +1/-1 |

### 偏离项
| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 1 | 使用 `google-generativeai>=0.8` | 迁移到 `google-genai>=1.0` | `google-generativeai` 已弃用，`from google import genai` 只在新 SDK 可用 |
| 2 | pyright 报 `Image.LANCZOS` 错误 | 改用 `Image.Resampling.LANCZOS` | pyright 不识别旧式枚举访问 |
| 3 | 计划使用默认封面 fallback | 失败时返回 None | 简化逻辑，默认封面仅供 Docker/部署使用 |

### 问题与修复
| 问题 | 解决 |
|------|------|
| `google-generativeai` 包不支持 `from google import genai` | 迁移到 `google-genai>=1.0` 新 SDK |
| pyright 报 `image_bytes` 可能为 None | 添加类型窄化 + `type: ignore[union-attr]` |
| `data/` 在 .gitignore 中 | `git add -f data/default_cover.png` 强制追踪 |
| `asyncio.TimeoutError` → ruff UP041 | 改用内置 `TimeoutError` |

### 质量门禁
| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format | ✅ 135 files formatted |
| lint-imports | ✅ 4 contracts kept, 0 broken |
| pyright | ✅ 0 errors |
| pytest | ✅ 537 passed |

### PR 链接
https://github.com/neuer/zhixi/pull/28
