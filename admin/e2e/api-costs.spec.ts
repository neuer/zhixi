import { expect, test } from "@playwright/test";
import { setupAuth } from "./helpers";

const mockCosts = {
  today: {
    total_cost: 0.5678,
    by_service: [
      {
        service: "Claude",
        call_count: 10,
        total_tokens: 25000,
        estimated_cost: 0.45,
      },
      {
        service: "X API",
        call_count: 20,
        total_tokens: 0,
        estimated_cost: 0.1178,
      },
    ],
  },
  this_month: {
    total_cost: 12.3456,
    by_service: [
      {
        service: "Claude",
        call_count: 200,
        total_tokens: 500000,
        estimated_cost: 10.0,
      },
    ],
  },
};

const mockDaily = {
  days: [
    {
      date: "2026-03-21",
      total_cost: 0.5678,
      claude_cost: 0.45,
      x_cost: 0.1178,
      gemini_cost: 0,
    },
    {
      date: "2026-03-20",
      total_cost: 0.3,
      claude_cost: 0.3,
      x_cost: 0,
      gemini_cost: 0,
    },
  ],
};

test.describe("ApiCosts 成本监控", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await page.route("**/api/dashboard/api-costs", (route) => {
      if (route.request().url().includes("/daily")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockDaily),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockCosts),
      });
    });
    await page.route("**/api/dashboard/api-costs/daily", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDaily),
      }),
    );
  });

  test("今日成本数据渲染", async ({ page }) => {
    await page.goto("/costs");
    await expect(page.getByText("$0.5678").first()).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText("Claude").first()).toBeVisible();
    await expect(page.getByText("10次调用 · 25000 tokens")).toBeVisible();
    await expect(
      page.getByText("费用为估算值，实际费用以服务商账单为准"),
    ).toBeVisible();
  });

  test("本月 tab 切换", async ({ page }) => {
    await page.goto("/costs");
    await expect(page.getByText("$0.5678").first()).toBeVisible({
      timeout: 10000,
    });

    await page.getByRole("tab", { name: "本月" }).click();
    await expect(page.getByText("$12.3456")).toBeVisible({ timeout: 5000 });
  });

  test("30 天趋势渲染", async ({ page }) => {
    await page.goto("/costs");
    await expect(page.getByText("近 30 天趋势")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText("2026-03-21")).toBeVisible();
    await expect(page.getByText("2026-03-20")).toBeVisible();
  });

  test("无数据空态", async ({ page }) => {
    await page.route("**/api/dashboard/api-costs", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          today: { total_cost: 0, by_service: [] },
          this_month: { total_cost: 0, by_service: [] },
        }),
      }),
    );
    await page.route("**/api/dashboard/api-costs/daily", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ days: [] }),
      }),
    );

    await page.goto("/costs");
    await expect(page.getByText("今日暂无调用记录")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText("暂无成本记录")).toBeVisible();
  });
});
