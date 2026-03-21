import { expect, test } from "@playwright/test";
import { setupAuth } from "./helpers";

const mockHistoryItems = [
  {
    id: 1,
    digest_date: "2026-03-21",
    version: 1,
    status: "draft",
    summary: null,
    item_count: 8,
    published_at: null,
    created_at: "2026-03-21T06:00:00Z",
  },
  {
    id: 2,
    digest_date: "2026-03-20",
    version: 2,
    status: "published",
    summary: "AI 日报",
    item_count: 10,
    published_at: "2026-03-20T12:00:00Z",
    created_at: "2026-03-20T06:00:00Z",
  },
];

test.describe("History 推送历史", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("列表正常渲染", async ({ page }) => {
    await page.route("**/api/history*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: mockHistoryItems,
          total: 2,
          page: 1,
          page_size: 20,
        }),
      }),
    );

    await page.goto("/history");
    await expect(page.getByText("8条 · v1")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("10条 · v2")).toBeVisible();
    await expect(page.getByText("草稿")).toBeVisible();
    await expect(page.getByText("已发布")).toBeVisible();
  });

  test("空态显示", async ({ page }) => {
    await page.route("**/api/history*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 }),
      }),
    );

    await page.goto("/history");
    await expect(page.getByText("暂无历史记录")).toBeVisible({
      timeout: 10000,
    });
  });

  test("点击进入详情页", async ({ page }) => {
    await page.route("**/api/history?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: mockHistoryItems,
          total: 2,
          page: 1,
          page_size: 20,
        }),
      }),
    );
    await page.route("**/api/history/1", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          digest: {
            id: 1,
            digest_date: "2026-03-21",
            version: 1,
            status: "draft",
            summary: null,
            item_count: 8,
            content_markdown: "# 测试",
            created_at: "2026-03-21T06:00:00Z",
          },
          items: [],
        }),
      }),
    );

    await page.goto("/history");
    await expect(page.getByText("8条 · v1")).toBeVisible({ timeout: 10000 });
    await page.getByText("8条 · v1").click();
    await expect(page).toHaveURL(/\/history\/1/, { timeout: 5000 });
  });
});

test.describe("HistoryDetail 历史详情", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("正常加载详情", async ({ page }) => {
    await page.route("**/api/history/1", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          digest: {
            id: 1,
            digest_date: "2026-03-21",
            version: 1,
            status: "draft",
            summary: "测试摘要",
            item_count: 1,
            content_markdown: "# 测试",
            created_at: "2026-03-21T06:00:00Z",
          },
          items: [
            {
              id: 10,
              item_type: "tweet",
              item_ref_id: 42,
              display_order: 0,
              is_pinned: false,
              is_excluded: false,
              snapshot_title: "测试标题",
              snapshot_translation: "翻译",
              snapshot_summary: null,
              snapshot_comment: "点评",
              snapshot_perspectives: null,
              snapshot_heat_score: 80,
              snapshot_author_name: "Test",
              snapshot_author_handle: "test",
              snapshot_tweet_url: "https://x.com/test/1",
              snapshot_source_tweets: null,
              snapshot_topic_type: null,
              snapshot_tweet_time: null,
            },
          ],
        }),
      }),
    );

    await page.goto("/history/1");
    await expect(page.getByText("测试标题")).toBeVisible({ timeout: 10000 });
  });

  test("无效 ID 显示错误", async ({ page }) => {
    await page.goto("/history/abc");
    await expect(page.getByText("无效的记录 ID")).toBeVisible({
      timeout: 10000,
    });
  });

  test("404 显示记录不存在", async ({ page }) => {
    await page.route("**/api/history/999", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not found" }),
      }),
    );

    await page.goto("/history/999");
    await expect(page.getByText("记录不存在")).toBeVisible({ timeout: 10000 });
  });
});
