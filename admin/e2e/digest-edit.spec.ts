import { expect, test } from "@playwright/test";
import { setupAuth } from "./helpers";

const mockTweetItem = {
  id: 10,
  item_type: "tweet",
  item_ref_id: 42,
  display_order: 0,
  is_pinned: false,
  is_excluded: false,
  snapshot_title: "GPT-5 发布了",
  snapshot_translation: "OpenAI 今日发布 GPT-5，性能全面提升",
  snapshot_summary: null,
  snapshot_comment: "这是 AI 领域的一大步",
  snapshot_perspectives: null,
  snapshot_heat_score: 85.5,
  snapshot_author_name: "Sam Altman",
  snapshot_author_handle: "sama",
  snapshot_tweet_url: "https://x.com/sama/status/123",
  snapshot_source_tweets: null,
  snapshot_topic_type: null,
  snapshot_tweet_time: "2026-03-21T08:00:00Z",
};

const mockTopicItem = {
  id: 11,
  item_type: "topic",
  item_ref_id: 5,
  display_order: 1,
  is_pinned: true,
  is_excluded: false,
  snapshot_title: "AI 监管新规讨论",
  snapshot_translation: null,
  snapshot_summary: "多国政府加速 AI 监管立法",
  snapshot_comment: "监管是必要的",
  snapshot_perspectives: '[{"author":"@test","viewpoint":"支持"}]',
  snapshot_heat_score: 72.3,
  snapshot_author_name: null,
  snapshot_author_handle: null,
  snapshot_tweet_url: null,
  snapshot_source_tweets: null,
  snapshot_topic_type: "aggregated",
  snapshot_tweet_time: null,
};

const mockTodayResponse = {
  digest: {
    id: 1,
    digest_date: "2026-03-21",
    version: 1,
    status: "draft",
    summary: "今日 AI 动态",
    item_count: 2,
    content_markdown: "# 测试",
    created_at: "2026-03-21T06:00:00Z",
  },
  items: [mockTweetItem, mockTopicItem],
  low_content_warning: false,
};

test.describe("DigestEdit 内容编辑", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockTodayResponse),
      }),
    );
  });

  test("推文类型 — 显示翻译字段，不显示摘要/观点", async ({ page }) => {
    await page.goto("/digest/edit/tweet/42");

    // 等待数据加载完成
    await expect(page.getByText("推文")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("@sama")).toBeVisible();
    await expect(page.getByText("🔥 86")).toBeVisible();

    // 标题在表单字段中
    const titleField = page.getByRole("textbox", { name: "标题" });
    await expect(titleField).toHaveValue("GPT-5 发布了");

    // 推文类型有翻译字段
    await expect(page.getByRole("textbox", { name: "翻译" })).toBeVisible();
    // 无摘要/观点字段
    await expect(page.getByRole("textbox", { name: "摘要" })).not.toBeVisible();
  });

  test("聚合话题 — 显示摘要/观点，不显示翻译", async ({ page }) => {
    await page.goto("/digest/edit/topic/5");

    await expect(page.getByText("聚合话题")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("置顶")).toBeVisible();

    // 标题
    const titleField = page.getByRole("textbox", { name: "标题" });
    await expect(titleField).toHaveValue("AI 监管新规讨论");

    // 聚合话题有摘要和观点
    await expect(page.getByRole("textbox", { name: "摘要" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "各方观点" })).toBeVisible();
    // 无翻译字段
    await expect(page.getByRole("textbox", { name: "翻译" })).not.toBeVisible();
  });

  test("编辑并保存", async ({ page }) => {
    let savedPayload: Record<string, unknown> | null = null;
    await page.route("**/api/digest/item/tweet/42", (route) => {
      if (route.request().method() === "PUT") {
        savedPayload = route.request().postDataJSON();
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...mockTweetItem,
            snapshot_title: savedPayload?.title ?? mockTweetItem.snapshot_title,
          }),
        });
      }
      return route.continue();
    });
    // Mock digest/today for the back navigation
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockTodayResponse),
      }),
    );

    await page.goto("/digest/edit/tweet/42");

    // 等待表单加载
    const titleField = page.getByRole("textbox", { name: "标题" });
    await expect(titleField).toHaveValue("GPT-5 发布了", { timeout: 10000 });

    // 修改标题
    await titleField.clear();
    await titleField.fill("GPT-5 正式发布");

    await page.getByRole("button", { name: "保存修改" }).click();

    // 保存成功后 router.back()，验证 API 被调用且 payload 正确
    await page.waitForResponse("**/api/digest/item/tweet/42", {
      timeout: 5000,
    });
    expect(savedPayload).toBeTruthy();
    expect(savedPayload?.title).toBe("GPT-5 正式发布");
  });

  test("没有修改时提示无变更", async ({ page }) => {
    await page.goto("/digest/edit/tweet/42");

    // 等待表单加载
    await expect(page.getByRole("textbox", { name: "标题" })).toHaveValue(
      "GPT-5 发布了",
      {
        timeout: 10000,
      },
    );

    await page.getByRole("button", { name: "保存修改" }).click();
    await expect(page.getByText("没有修改")).toBeVisible();
  });

  test("剔除条目", async ({ page }) => {
    let excludeCalled = false;
    await page.route("**/api/digest/exclude/tweet/42", (route) => {
      excludeCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "已剔除" }),
      });
    });

    await page.goto("/digest/edit/tweet/42");

    // 等待加载
    await expect(page.getByRole("button", { name: "剔除条目" })).toBeVisible({
      timeout: 10000,
    });

    await page.getByRole("button", { name: "剔除条目" }).click();
    await page.getByRole("button", { name: "确认" }).click();

    // 验证 exclude API 被调用（保存后 router.back() 导致 toast 消失）
    await page.waitForResponse("**/api/digest/exclude/tweet/42", {
      timeout: 5000,
    });
    expect(excludeCalled).toBe(true);
  });

  test("非 draft 状态不可编辑", async ({ page }) => {
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...mockTodayResponse,
          digest: { ...mockTodayResponse.digest, status: "published" },
        }),
      }),
    );

    await page.goto("/digest/edit/tweet/42");

    await expect(page.getByText("当前草稿非 draft 状态，不可编辑")).toBeVisible(
      {
        timeout: 10000,
      },
    );
    await expect(
      page.getByRole("button", { name: "保存修改" }),
    ).not.toBeVisible();
  });

  test("只读模式下各方观点渲染为可读列表", async ({ page }) => {
    const topicWithPerspectives = {
      ...mockTopicItem,
      snapshot_perspectives: JSON.stringify([
        {
          author: "Sam Altman",
          handle: "sama",
          viewpoint: "AGI 就在眼前",
        },
        {
          author: "Yann LeCun",
          handle: "ylecun",
          viewpoint: "自回归不是答案",
        },
      ]),
    };
    await page.route("**/api/digest/today", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...mockTodayResponse,
          digest: { ...mockTodayResponse.digest, status: "published" },
          items: [mockTweetItem, topicWithPerspectives],
        }),
      }),
    );

    await page.goto("/digest/edit/topic/5");

    // 等待加载
    await expect(page.getByText("各方观点")).toBeVisible({ timeout: 10000 });

    // 应渲染可读列表，而非 JSON 原文
    await expect(page.getByText("Sam Altman")).toBeVisible();
    await expect(page.getByText("@sama")).toBeVisible();
    await expect(page.getByText("AGI 就在眼前")).toBeVisible();
    await expect(page.getByText("Yann LeCun")).toBeVisible();
    await expect(page.getByText("自回归不是答案")).toBeVisible();

    // 不应出现 JSON 语法字符
    await expect(page.getByText('"viewpoint"')).not.toBeVisible();
  });

  test("条目不存在时显示错误", async ({ page }) => {
    await page.goto("/digest/edit/tweet/9999");
    await expect(page.getByText("条目不存在")).toBeVisible({ timeout: 10000 });
  });
});
