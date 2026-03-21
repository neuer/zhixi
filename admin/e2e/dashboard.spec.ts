import { expect, test } from "@playwright/test";
import { setupAuth } from "./helpers";

const mockOverview = {
  pipeline_status: { status: "completed" },
  digest_status: {
    status: "draft",
    item_count: 8,
    version: 2,
    low_content_warning: false,
  },
  today_cost: {
    total_cost: 0.1234,
    by_service: [
      {
        service: "Claude",
        call_count: 5,
        total_tokens: 12000,
        estimated_cost: 0.1,
      },
      {
        service: "X API",
        call_count: 10,
        total_tokens: 0,
        estimated_cost: 0.0234,
      },
    ],
  },
  recent_7_days: [
    { date: "2026-03-21", item_count: 8, version: 2, status: "draft" },
    { date: "2026-03-20", item_count: 10, version: 1, status: "published" },
  ],
  alerts: [],
};

test.describe("Dashboard 首页", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("正常数据渲染", async ({ page }) => {
    await page.route("**/api/dashboard/overview", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockOverview),
      }),
    );

    await page.goto("/dashboard");
    await expect(page.getByText("智曦管理后台")).toBeVisible();
    await expect(page.getByText("$0.1234")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Claude")).toBeVisible();
    await expect(page.getByText("8条 v2")).toBeVisible();
  });

  test("有告警时显示告警条", async ({ page }) => {
    const withAlerts = {
      ...mockOverview,
      alerts: [{ job_type: "pipeline", error_message: "抓取失败" }],
    };
    await page.route("**/api/dashboard/overview", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(withAlerts),
      }),
    );

    await page.goto("/dashboard");
    await expect(page.getByText("[pipeline] 抓取失败")).toBeVisible({
      timeout: 10000,
    });
  });

  test("低内容警告显示", async ({ page }) => {
    const withWarning = {
      ...mockOverview,
      digest_status: {
        ...mockOverview.digest_status,
        low_content_warning: true,
        item_count: 2,
      },
    };
    await page.route("**/api/dashboard/overview", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(withWarning),
      }),
    );

    await page.goto("/dashboard");
    await expect(page.getByText("今日资讯较少（2条）")).toBeVisible({
      timeout: 10000,
    });
  });

  test("加载失败显示错误态", async ({ page }) => {
    await page.route("**/api/dashboard/overview", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "服务器错误" }),
      }),
    );

    await page.goto("/dashboard");
    await expect(page.getByText("加载失败，下拉刷新重试")).toBeVisible({
      timeout: 10000,
    });
  });

  test("导航跳转正确", async ({ page }) => {
    await page.route("**/api/dashboard/overview", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockOverview),
      }),
    );
    // mock accounts API 防止跳转后报错
    await page.route("**/api/accounts*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 100 }),
      }),
    );

    await page.goto("/dashboard");
    await expect(page.getByText("审核今日内容")).toBeVisible({
      timeout: 10000,
    });

    // 大V管理跳转
    await page.getByText("大V管理").click();
    await expect(page).toHaveURL("/accounts", { timeout: 5000 });
  });

  test("无数据时显示空态", async ({ page }) => {
    const empty = {
      ...mockOverview,
      today_cost: { total_cost: 0, by_service: [] },
      recent_7_days: [],
    };
    await page.route("**/api/dashboard/overview", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(empty),
      }),
    );

    await page.goto("/dashboard");
    await expect(page.getByText("暂无调用记录")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText("暂无推送记录")).toBeVisible();
  });
});
