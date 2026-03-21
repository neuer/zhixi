import { expect, test } from "@playwright/test";

const mockPreview = {
  digest: {
    id: 1,
    digest_date: "2026-03-21",
    version: 1,
    status: "draft",
    summary: "AI 日报",
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
      snapshot_translation: "翻译内容",
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
  content_markdown: "# 测试内容",
};

test.describe("Preview 预览", () => {
  test("登录态预览 — 正常渲染", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem(
        "zhixi_token",
        "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjk5OTk5OTk5OTl9.K1OA0LOhkn5tEQm8YCOqEIReFGKBsMC-NLslkz1qxYg",
      );
    });
    await page.route("**/api/digest/preview", (route) => {
      // 精确匹配不带 token 的 preview
      if (!route.request().url().includes("/preview/")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockPreview),
        });
      }
      return route.continue();
    });

    await page.goto("/preview");
    await expect(page.getByText("测试标题")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("返回")).toBeVisible();
  });

  test("登录态预览 — 无内容", async ({ page }) => {
    await page.route("**/api/digest/preview", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "无草稿" }),
      }),
    );

    await page.goto("/preview");
    await expect(page.getByText("暂无可预览的内容")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByRole("button", { name: "返回首页" })).toBeVisible();
  });

  test("签名链接模式 — 正常渲染", async ({ page }) => {
    await page.route("**/api/digest/preview/valid-token*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockPreview),
      }),
    );

    await page.goto("/preview?token=valid-token");
    await expect(page.getByText("测试标题")).toBeVisible({ timeout: 10000 });
    // token 模式不显示返回按钮
    await expect(page.getByText("返回")).not.toBeVisible();
  });

  test("签名链接模式 — 链接过期 403", async ({ page }) => {
    await page.route("**/api/digest/preview/expired-token*", (route) =>
      route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Expired" }),
      }),
    );

    await page.goto("/preview?token=expired-token");
    await expect(page.getByText("链接已失效或过期")).toBeVisible({
      timeout: 10000,
    });
    // token 模式下不显示"返回首页"按钮
    await expect(
      page.getByRole("button", { name: "返回首页" }),
    ).not.toBeVisible();
  });
});
