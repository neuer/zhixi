import { expect, test } from "@playwright/test";
import { setupAuth } from "./helpers";

const mockDigest = {
  id: 1,
  digest_date: "2026-03-21",
  version: 1,
  status: "draft",
  summary: "今日 AI 动态摘要",
  item_count: 2,
  content_markdown: "# Test",
  created_at: "2026-03-21T06:00:00Z",
};

const mockItems = [
  {
    id: 10,
    item_type: "tweet",
    item_ref_id: 42,
    display_order: 0,
    is_pinned: false,
    is_excluded: false,
    snapshot_title: "GPT-5 发布",
    snapshot_translation: "翻译内容",
    snapshot_summary: null,
    snapshot_comment: "点评",
    snapshot_perspectives: null,
    snapshot_heat_score: 85.5,
    snapshot_author_name: "Sam",
    snapshot_author_handle: "sama",
    snapshot_tweet_url: null,
    snapshot_source_tweets: null,
    snapshot_topic_type: null,
    snapshot_tweet_time: null,
  },
  {
    id: 11,
    item_type: "topic",
    item_ref_id: 5,
    display_order: 1,
    is_pinned: false,
    is_excluded: false,
    snapshot_title: "AI 监管讨论",
    snapshot_translation: null,
    snapshot_summary: "多国监管",
    snapshot_comment: null,
    snapshot_perspectives: null,
    snapshot_heat_score: 72,
    snapshot_author_name: null,
    snapshot_author_handle: null,
    snapshot_tweet_url: null,
    snapshot_source_tweets: null,
    snapshot_topic_type: "aggregated",
    snapshot_tweet_time: null,
  },
  {
    id: 12,
    item_type: "tweet",
    item_ref_id: 99,
    display_order: 2,
    is_pinned: false,
    is_excluded: true,
    snapshot_title: "被剔除的条目",
    snapshot_translation: null,
    snapshot_summary: null,
    snapshot_comment: null,
    snapshot_perspectives: null,
    snapshot_heat_score: 10,
    snapshot_author_name: null,
    snapshot_author_handle: null,
    snapshot_tweet_url: null,
    snapshot_source_tweets: null,
    snapshot_topic_type: null,
    snapshot_tweet_time: null,
  },
];

const mockToday = {
  digest: mockDigest,
  items: mockItems,
  low_content_warning: false,
};

test.describe("Digest 今日内容", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("草稿概览与条目列表", async ({ page }) => {
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockToday),
      }),
    );

    await page.goto("/digest");
    await expect(page.getByText("草稿")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("今日 AI 动态摘要")).toBeVisible();
    // 2 条可见（第 3 条 is_excluded）
    await expect(page.getByText("条目列表（2条）")).toBeVisible();
    await expect(page.getByText("GPT-5 发布")).toBeVisible();
    await expect(page.getByText("@sama")).toBeVisible();
    await expect(page.getByText("聚合话题")).toBeVisible();
    // 剔除的条目不显示
    await expect(page.getByText("被剔除的条目")).not.toBeVisible();
  });

  test("无草稿时显示空态", async ({ page }) => {
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          digest: null,
          items: [],
          low_content_warning: false,
        }),
      }),
    );

    await page.goto("/digest");
    await expect(page.getByText("今日草稿尚未生成")).toBeVisible({
      timeout: 10000,
    });
  });

  test("低内容警告显示", async ({ page }) => {
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...mockToday, low_content_warning: true }),
      }),
    );

    await page.goto("/digest");
    await expect(page.getByText(/今日资讯较少/)).toBeVisible({
      timeout: 10000,
    });
  });

  test("发布操作", async ({ page }) => {
    let publishCalled = false;
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockToday),
      }),
    );
    await page.route("**/api/digest/mark-published", (route) => {
      publishCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "ok" }),
      });
    });

    await page.goto("/digest");
    await expect(page.getByRole("button", { name: "确认发布" })).toBeVisible({
      timeout: 10000,
    });
    await page.getByRole("button", { name: "确认发布" }).click();

    // Vant confirmDialog 确认按钮
    await expect(page.locator(".van-dialog__confirm")).toBeVisible({
      timeout: 3000,
    });
    await page.locator(".van-dialog__confirm").click();
    await page.waitForResponse("**/api/digest/mark-published", {
      timeout: 5000,
    });
    expect(publishCalled).toBe(true);
  });

  test("重新生成操作", async ({ page }) => {
    let regenerateCalled = false;
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockToday),
      }),
    );
    await page.route("**/api/digest/regenerate", (route) => {
      regenerateCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message: "ok",
          digest_id: 1,
          version: 2,
          item_count: 5,
          job_run_id: 1,
        }),
      });
    });

    await page.goto("/digest");
    await expect(page.getByRole("button", { name: "重新生成" })).toBeVisible({
      timeout: 10000,
    });
    await page.getByRole("button", { name: "重新生成" }).click();

    await expect(page.locator(".van-dialog__confirm")).toBeVisible({
      timeout: 3000,
    });
    await page.locator(".van-dialog__confirm").click();
    await page.waitForResponse("**/api/digest/regenerate", { timeout: 5000 });
    expect(regenerateCalled).toBe(true);
  });

  test("非 draft 状态不显示操作按钮", async ({ page }) => {
    const published = {
      ...mockToday,
      digest: { ...mockDigest, status: "published" },
    };
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(published),
      }),
    );

    await page.goto("/digest");
    await expect(page.getByText("已发布")).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByRole("button", { name: "确认发布" }),
    ).not.toBeVisible();
    await expect(
      page.getByRole("button", { name: "重新生成" }),
    ).not.toBeVisible();
  });

  test("点击条目跳转编辑页", async ({ page }) => {
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockToday),
      }),
    );

    await page.goto("/digest");
    await expect(page.getByText("GPT-5 发布")).toBeVisible({ timeout: 10000 });
    await page.getByText("GPT-5 发布").click();
    await expect(page).toHaveURL(/\/digest\/edit\/tweet\/42/, {
      timeout: 5000,
    });
  });
});
