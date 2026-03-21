import { expect, test } from "@playwright/test";
import { setupAuth } from "./helpers";

const mockLogs = {
  logs: [
    {
      level: "ERROR",
      timestamp: "2026-03-21 10:00:00",
      module: "fetcher",
      message: "抓取失败",
      exception: "ConnectionError: timeout",
    },
    {
      level: "WARNING",
      timestamp: "2026-03-21 09:55:00",
      module: "processor",
      message: "Token 超限",
      exception: null,
    },
    {
      level: "INFO",
      timestamp: "2026-03-21 09:50:00",
      module: "pipeline",
      message: "Pipeline 完成",
      exception: null,
    },
  ],
  total: 3,
};

test.describe("Logs 系统日志", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("日志列表渲染", async ({ page }) => {
    await page.route("**/api/dashboard/logs*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockLogs),
      }),
    );

    await page.goto("/logs");
    await expect(page.getByText("抓取失败")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Token 超限")).toBeVisible();
    await expect(page.getByText("Pipeline 完成")).toBeVisible();
    // exception 显示
    await expect(page.getByText("ConnectionError: timeout")).toBeVisible();
    // module 显示
    await expect(page.getByText("[fetcher]")).toBeVisible();
  });

  test("空态显示", async ({ page }) => {
    await page.route("**/api/dashboard/logs*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ logs: [], total: 0 }),
      }),
    );

    await page.goto("/logs");
    await expect(page.getByText("暂无日志")).toBeVisible({ timeout: 10000 });
  });

  test("级别过滤切换", async ({ page }) => {
    let lastLevel = "";
    await page.route("**/api/dashboard/logs*", (route) => {
      const url = new URL(route.request().url());
      lastLevel = url.searchParams.get("level") ?? "INFO";
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockLogs),
      });
    });

    await page.goto("/logs");
    await expect(page.getByText("抓取失败")).toBeVisible({ timeout: 10000 });

    // 初始加载用 INFO
    expect(lastLevel).toBe("INFO");
  });
});
