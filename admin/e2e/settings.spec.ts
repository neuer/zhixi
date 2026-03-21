import { expect, test } from "@playwright/test";
import { setupAuth } from "./helpers";

const mockSettings = {
  push_time: "09:30",
  push_days: [1, 2, 3, 4, 5],
  top_n: 10,
  min_articles: 1,
  publish_mode: "manual",
  enable_cover_generation: false,
  cover_generation_timeout: 30,
  notification_webhook_url: "",
  db_size_mb: 12,
  last_backup_at: "2026-03-20T08:00:00Z",
};

const mockSecrets = {
  items: [
    {
      key: "x_api_bearer_token",
      label: "X API",
      configured: true,
      masked: "****abc",
      source: "env",
    },
    {
      key: "anthropic_api_key",
      label: "Claude API",
      configured: false,
      masked: "",
      source: "none",
    },
  ],
};

test.describe("Settings 系统设置", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await page.route("**/api/settings", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockSettings),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "ok" }),
      });
    });
    await page.route("**/api/settings/secrets-status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSecrets),
      }),
    );
  });

  test("加载并显示配置数据", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByText("09:30")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("12 MB")).toBeVisible();
  });

  test("密钥列表渲染", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByText("X API")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("环境变量").first()).toBeVisible();
    await expect(page.getByText("Claude API")).toBeVisible();
    // 未配置的密钥显示"配置"按钮
    await expect(
      page.getByRole("button", { name: "配置", exact: true }),
    ).toBeVisible();
  });

  test("保存配置", async ({ page }) => {
    let saveCalled = false;
    await page.route("**/api/settings", (route) => {
      if (route.request().method() === "PUT") {
        saveCalled = true;
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ message: "ok" }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await expect(page.getByRole("button", { name: "保存配置" })).toBeVisible({
      timeout: 10000,
    });
    await page.getByRole("button", { name: "保存配置" }).click();

    await page.waitForResponse(
      (r) =>
        r.url().includes("/api/settings") && r.request().method() === "PUT",
      { timeout: 5000 },
    );
    expect(saveCalled).toBe(true);
  });

  test("API 状态检测", async ({ page }) => {
    await page.route("**/api/settings/api-status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          x_api: { status: "ok", latency_ms: 120 },
          claude_api: { status: "error", latency_ms: null },
          gemini_api: null,
          wechat_api: null,
        }),
      }),
    );

    await page.goto("/settings");
    await expect(
      page.getByRole("button", { name: "检测 API 状态" }),
    ).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: "检测 API 状态" }).click();
    await expect(page.getByText("正常")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("异常")).toBeVisible();
    await expect(page.getByText("120ms")).toBeVisible();
  });

  test("封面图开关条件显示", async ({ page }) => {
    await page.goto("/settings");
    // 初始未启用，超时秒数不显示
    await expect(page.getByText("封面图生成")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("封面图超时")).not.toBeVisible();
  });
});
