import { expect, test } from "@playwright/test";
import { setupAuth } from "./helpers";

const mockAccount = {
  id: 1,
  twitter_handle: "elonmusk",
  twitter_user_id: "44196397",
  display_name: "Elon Musk",
  avatar_url: null,
  bio: "CEO of Tesla",
  followers_count: 150000000,
  weight: 1.5,
  is_active: true,
  last_fetch_at: "2026-03-20T10:00:00Z",
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-20T10:00:00Z",
};

test.describe("Accounts 大V账号管理", () => {
  test("空态显示引导文案", async ({ page }) => {
    await setupAuth(page);
    await page.route("**/api/accounts*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 100 }),
      }),
    );

    await page.goto("/accounts");
    await expect(page.getByText("暂无账号，点击右上角添加")).toBeVisible();
  });

  test("账号列表正确渲染", async ({ page }) => {
    await setupAuth(page);
    await page.route("**/api/accounts*", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [mockAccount],
            total: 1,
            page: 1,
            page_size: 100,
          }),
        });
      }
      return route.continue();
    });

    await page.goto("/accounts");
    await expect(page.getByText("共 1 个账号")).toBeVisible();
    await expect(page.getByText("@elonmusk")).toBeVisible();
    await expect(page.getByText("Elon Musk")).toBeVisible();
    await expect(page.getByText("1.5x")).toBeVisible();
    await expect(page.getByText("活跃")).toBeVisible();
  });

  test("添加账号弹窗交互", async ({ page }) => {
    await setupAuth(page);
    await page.route("**/api/accounts*", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [],
            total: 0,
            page: 1,
            page_size: 100,
          }),
        });
      }
      return route.continue();
    });

    await page.goto("/accounts");

    // 点击添加按钮
    await page.getByRole("button", { name: "添加" }).first().click();
    await expect(page.getByText("添加大V账号")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "用户名" })).toBeVisible();

    // 未填写时添加按钮禁用
    const addBtn = page.getByRole("button", { name: "添加" }).last();
    await expect(addBtn).toBeDisabled();

    // 填写用户名后启用
    await page.getByRole("textbox", { name: "用户名" }).fill("test_user");
    await expect(addBtn).toBeEnabled();
  });

  test("添加账号成功", async ({ page }) => {
    await setupAuth(page);

    let addCalled = false;
    await page.route("**/api/accounts*", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: addCalled ? [mockAccount] : [],
            total: addCalled ? 1 : 0,
            page: 1,
            page_size: 100,
          }),
        });
      }
      return route.continue();
    });
    await page.route("**/api/accounts", (route) => {
      if (route.request().method() === "POST") {
        addCalled = true;
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify(mockAccount),
        });
      }
      return route.continue();
    });

    await page.goto("/accounts");
    await page.getByRole("button", { name: "添加" }).first().click();
    await page.getByRole("textbox", { name: "用户名" }).fill("elonmusk");
    await page.getByRole("button", { name: "添加" }).last().click();

    // 添加成功后弹窗关闭、列表刷新
    await expect(page.getByText("添加成功")).toBeVisible();
    await expect(page.getByText("@elonmusk")).toBeVisible({ timeout: 5000 });
  });

  test("X API 不可用时降级为手动模式", async ({ page }) => {
    await setupAuth(page);
    await page.route("**/api/accounts*", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [],
            total: 0,
            page: 1,
            page_size: 100,
          }),
        });
      }
      return route.continue();
    });
    await page.route("**/api/accounts", (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 502,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "X API 不可用",
            allow_manual: true,
          }),
        });
      }
      return route.continue();
    });

    await page.goto("/accounts");
    await page.getByRole("button", { name: "添加" }).first().click();
    await page.getByRole("textbox", { name: "用户名" }).fill("test_user");
    await page.getByRole("button", { name: "添加" }).last().click();

    // 降级提示 + 手动模式字段出现
    await expect(page.getByText("X API 不可用，请手动填写信息")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "显示名" })).toBeVisible();
    await expect(page.getByRole("button", { name: "手动添加" })).toBeVisible();
  });

  test("左滑停用账号", async ({ page }) => {
    await setupAuth(page);
    let toggleCalled = false;
    await page.route("**/api/accounts*", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [mockAccount],
            total: 1,
            page: 1,
            page_size: 100,
          }),
        });
      }
      return route.continue();
    });
    await page.route(`**/api/accounts/${mockAccount.id}`, (route) => {
      if (route.request().method() === "DELETE") {
        toggleCalled = true;
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ message: "ok" }),
        });
      }
      return route.continue();
    });

    await page.goto("/accounts");
    await expect(page.getByText("@elonmusk")).toBeVisible({ timeout: 10000 });

    // 左滑按钮存在于 DOM（van-swipe-cell 的 right slot）
    const stopBtn = page.getByRole("button", { name: "停用" });
    await expect(stopBtn).toBeAttached();

    // 点击停用按钮触发确认弹窗
    await stopBtn.click({ force: true });
    await expect(page.locator(".van-dialog__confirm")).toBeVisible({
      timeout: 3000,
    });
    await page.locator(".van-dialog__confirm").click();
    await page.waitForResponse(`**/api/accounts/${mockAccount.id}`, {
      timeout: 5000,
    });
    expect(toggleCalled).toBe(true);
  });

  test("左滑删除账号", async ({ page }) => {
    await setupAuth(page);
    let deleteCalled = false;
    await page.route("**/api/accounts*", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [mockAccount],
            total: 1,
            page: 1,
            page_size: 100,
          }),
        });
      }
      return route.continue();
    });
    await page.route(`**/api/accounts/${mockAccount.id}`, (route) => {
      if (route.request().method() === "DELETE") {
        deleteCalled = true;
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ message: "ok" }),
        });
      }
      return route.continue();
    });

    await page.goto("/accounts");
    await expect(page.getByText("@elonmusk")).toBeVisible({ timeout: 10000 });

    // 删除按钮存在于 DOM
    const deleteBtn = page.getByRole("button", { name: "删除" });
    await expect(deleteBtn).toBeAttached();

    // 点击删除按钮触发确认弹窗
    await deleteBtn.click({ force: true });
    await expect(page.getByText("确定永久删除")).toBeVisible({ timeout: 3000 });
    await page.locator(".van-dialog__confirm").click();
    await page.waitForResponse(`**/api/accounts/${mockAccount.id}`, {
      timeout: 5000,
    });
    expect(deleteCalled).toBe(true);
  });

  test("点击账号打开编辑弹窗", async ({ page }) => {
    await setupAuth(page);
    await page.route("**/api/accounts*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [mockAccount],
          total: 1,
          page: 1,
          page_size: 100,
        }),
      }),
    );

    await page.goto("/accounts");
    await page.getByText("@elonmusk").click();

    // 编辑弹窗
    await expect(page.getByText("@elonmusk").last()).toBeVisible();
    await expect(page.getByText("粉丝数")).toBeVisible();
    await expect(page.getByText("150,000,000")).toBeVisible();
    await expect(page.getByRole("button", { name: "保存权重" })).toBeVisible();
    await expect(page.getByRole("button", { name: "停用账号" })).toBeVisible();
  });
});
